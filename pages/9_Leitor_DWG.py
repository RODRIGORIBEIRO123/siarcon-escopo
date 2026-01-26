import streamlit as st
import ezdxf
from ezdxf import recover
import pandas as pd
import os
import tempfile
import openai
import json
import io
import re
import math
from collections import Counter

# Configuração da Página
st.set_page_config(page_title="Siarcon - Leitor Técnico V17", page_icon="🏗️", layout="wide")

# ==================================================
# 🔧 FUNÇÕES AUXILIARES
# ==================================================
def safe_float(valor):
    try:
        if valor is None: return 0.0
        val_str = str(valor).upper().replace('MM', '').strip().replace(',', '.')
        nums = re.findall(r"[-+]?\d*\.\d+|\d+", val_str)
        if nums: return float(nums[0])
        return 0.0
    except:
        return 0.0

def calcular_distancia(p1, p2):
    return math.sqrt((p1[0] - p2[0])**2 + (p1[1] - p2[1])**2)

# ==================================================
# 🔑 CONFIGURAÇÃO (SIDEBAR)
# ==================================================
api_key_sistema = st.secrets.get("OPENAI_API_KEY", None)

with st.sidebar:
    st.title("⚙️ Configuração")
    if api_key_sistema:
        openai.api_key = api_key_sistema
        api_key = api_key_sistema
        st.success("🔑 Chave Segura Ativa")
    else:
        api_key = st.text_input("API Key (OpenAI):", type="password")
        if api_key: openai.api_key = api_key

    st.divider()
    st.subheader("📐 Geometria")
    unidade_cad = st.selectbox("Unidade do CAD:", ["Milímetros (1u=1mm)", "Metros (1u=1m)"], index=0)
    raio_busca = st.number_input("Raio de Busca (Busca linha perto do texto):", value=600, help="Se o texto está no meio do duto, qual a distância até a borda?")
    
    st.subheader("🛡️ Filtros")
    max_len = st.number_input("Máx. Comprimento (m):", value=20.0)
    fator_divisao = st.radio("Tipo de Linha do Duto:", ("Linha Simples (Eixo)", "Linha Dupla (Paredes)"), index=1, help="Se o duto é desenhado com 2 linhas (paredes), dividimos o comprimento achado por 2.")
    
    st.subheader("📋 NBR 16401")
    classe_pressao = st.selectbox("Pressão:", ["Classe A (Baixa)", "Classe B (Média)", "Classe C (Alta)"], index=0)
    perda_corte = st.slider("Perda (%)", 0, 40, 10) / 100

# ==================================================
# 🧠 CÉREBRO
# ==================================================
def listar_layers(doc):
    layers = set()
    for entity in doc.modelspace():
        layers.add(entity.dxf.layer)
    return sorted(list(layers))

def ler_geometria_layer(msp, coords_texto, raio, layers_duto):
    """Mede linhas e polilinhas APENAS nas layers selecionadas próximas ao texto."""
    comprimento_total = 0.0
    linhas_encontradas = 0
    
    # 1. LINHAS (LINE)
    for line in msp.query('LINE'):
        if line.dxf.layer in layers_duto:
            mid = ((line.dxf.start.x + line.dxf.end.x)/2, (line.dxf.start.y + line.dxf.end.y)/2)
            dist = calcular_distancia(mid, coords_texto)
            
            if dist <= raio:
                l = calcular_distancia(line.dxf.start, line.dxf.end)
                comprimento_total += l
                linhas_encontradas += 1

    # 2. POLILINHAS (LWPOLYLINE)
    for poly in msp.query('LWPOLYLINE'):
        if poly.dxf.layer in layers_duto:
            if len(poly) > 0:
                # Usa o primeiro ponto como referência de proximidade
                p0 = poly[0] 
                dist = calcular_distancia((p0[0], p0[1]), coords_texto)
                
                if dist <= raio:
                    # Calcula perímetro
                    pts = poly.get_points()
                    l_poly = 0
                    for i in range(len(pts)-1):
                        l_poly += calcular_distancia(pts[i], pts[i+1])
                    comprimento_total += l_poly
                    linhas_encontradas += 1
                    
    return comprimento_total, linhas_encontradas

def extrair_blocos_equipamentos(msp, layers_equip):
    """Busca blocos (INSERT) que podem ser equipamentos."""
    equipamentos = []
    
    for insert in msp.query('INSERT'):
        if insert.dxf.layer in layers_equip:
            nome_bloco = insert.dxf.name
            # Tenta achar atributos dentro do bloco (Tags)
            attribs = []
            if insert.attribs:
                for att in insert.attribs:
                    attribs.append(att.dxf.text)
            
            texto_desc = f"{nome_bloco} {' '.join(attribs)}"
            equipamentos.append(texto_desc)
            
    return equipamentos

def processar_ia(texto_limpo, dados_geo, msp, raio, layers_duto, layers_equip, unid_cad, div_fator):
    if not api_key: return None

    # Fator CAD
    fator_escala = 0.001 if "Milímetros" in unid_cad else 1.0
    divisor = 2.0 if "Dupla" in div_fator else 1.0

    prompt = f"""
    Você é um Engenheiro HVAC.
    1. Analise o texto extraído (separado por ' | ').
    2. IGNORE VAZÕES entre parênteses ex: "(34.000)".
    3. EXTRAIA DIMENSÕES (ex: "1300x700").
    4. EXTRAIA EQUIPAMENTOS baseados nos nomes de blocos fornecidos.

    LISTA DE BLOCOS ENCONTRADOS NO CAD:
    {dados_geo['blocos_encontrados'][:100]} (Amostra)

    SAÍDA JSON:
    {{
        "dutos": [{{ "dimensao_original": "1300x700", "largura_mm": 1300, "altura_mm": 700 }}],
        "equipamentos": [{{ "item": "Nome do Bloco/Equip", "quantidade": 1 }}]
    }}
    """

    try:
        response = openai.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": f"Texto:\n{texto_limpo[:40000]}"} 
            ],
            temperature=0.0,
            response_format={"type": "json_object"}
        )
        result = json.loads(response.choices[0].message.content)
        
        # --- PÓS-PROCESSAMENTO MATEMÁTICO ---
        lista_dutos = result.get("dutos", [])
        
        for d in lista_dutos:
            dim = d.get("dimensao_original", "")
            
            # Achar coordenada do texto dessa dimensão
            coords = None
            for item in dados_geo['textos']:
                if item['txt'] in dim:
                    coords = item['pos']
                    break
            
            if coords:
                comp_raw, qtd_linhas = ler_geometria_layer(msp, coords, raio, layers_duto)
                # Aplica correções (Escala e Linha Dupla)
                comp_final = (comp_raw * fator_escala) / divisor
                
                if comp_final > 0:
                    d['comprimento_m'] = comp_final
                    d['nota'] = f"Geometria: {qtd_linhas} linhas somadas na layer."
                else:
                    d['comprimento_m'] = 0
                    d['nota'] = "Nenhuma linha encontrada na Layer selecionada dentro do raio."
            else:
                d['comprimento_m'] = 0
                d['nota'] = "Texto não localizado espacialmente."

        return result

    except Exception as e:
        return {"erro": str(e)}

# ==================================================
# 🖥️ INTERFACE
# ==================================================
st.title("🏗️ Leitor V17: Seletor de Layers")
st.markdown("Para funcionar, você **PRECISA** indicar em quais Layers estão os Dutos e os Equipamentos.")

arquivo = st.file_uploader("Upload DXF", type=["dxf"])

if arquivo:
    st.divider()
    path_temp = tempfile.NamedTemporaryFile(delete=False, suffix=".dxf").name
    arquivo.seek(0)
    with open(path_temp, "wb") as f: f.write(arquivo.getbuffer())

    try:
        try: doc = ezdxf.readfile(path_temp)
        except: doc, auditor = recover.readfile(path_temp)

        if doc:
            msp = doc.modelspace()
            all_layers = listar_layers(doc)
            
            # --- SELETORES DE LAYER (CRUCIAL) ---
            c1, c2 = st.columns(2)
            with c1:
                st.info("📂 Onde estão as LINHAS dos Dutos?")
                sel_layers_duto = st.multiselect(
                    "Selecione Layers de Dutos:", 
                    all_layers,
                    help="Escolha as layers que contém as linhas laterais dos dutos (ex: AR-DUTO, M-DUCT)."
                )
            with c2:
                st.info("❄️ Onde estão os EQUIPAMENTOS?")
                sel_layers_equip = st.multiselect(
                    "Selecione Layers de Equipamentos:", 
                    all_layers,
                    help="Escolha layers de blocos (ex: AR-EQTO, AR-BLOCO)."
                )

            # Extração de Texto e Blocos
            raw_text = []
            dados_geo = {'textos': [], 'blocos_encontrados': []}
            
            # 1. Ler Textos
            for e in msp.query('TEXT MTEXT'):
                t = str(e.dxf.text).strip()
                if len(t) > 2 and "LAYER" not in t.upper():
                    raw_text.append(t)
                    dados_geo['textos'].append({'txt': t, 'pos': (e.dxf.insert.x, e.dxf.insert.y)})
            
            # 2. Ler Blocos (se layers selecionadas)
            if sel_layers_equip:
                blocos = extrair_blocos_equipamentos(msp, sel_layers_equip)
                dados_geo['blocos_encontrados'] = blocos
                # Adiciona blocos ao texto para a IA ler
                raw_text.extend(blocos)

            st.write(f"🔍 Encontrados: {len(raw_text)} textos e {len(dados_geo['blocos_encontrados'])} blocos.")

            if st.button("🚀 Calcular com Layers Selecionadas", type="primary"):
                if not sel_layers_duto:
                    st.error("⚠️ Selecione pelo menos uma Layer de Duto!")
                elif not api_key:
                    st.error("⚠️ Sem API Key.")
                else:
                    with st.spinner("Mapeando Layers e Geometria..."):
                        txt_completo = " | ".join(raw_text)
                        
                        dados = processar_ia(
                            txt_completo, dados_geo, msp, 
                            raio_busca, sel_layers_duto, sel_layers_equip, 
                            unidade_cad, fator_divisao
                        )

                        if "erro" in dados:
                            st.error(dados['erro'])
                        else:
                            # RESULTADOS E TABELAS
                            lista_dutos = dados.get("dutos", [])
                            res_dutos = []
                            kg_total = 0
                            
                            # Funções de cálculo de peso (simplificadas aqui)
                            def get_peso(bitola): return {26:4.0, 24:5.6, 22:6.8, 20:8.4}.get(bitola, 6.0)
                            def get_bitola(l): return 24 if l <= 750 else 22 if l <= 1200 else 20
                            
                            for d in lista_dutos:
                                w, h = safe_float(d.get('largura_mm')), safe_float(d.get('altura_mm'))
                                l = d.get('comprimento_m', 0)
                                
                                if l > max_len: l = 0 # Trava
                                
                                if w > 0 and h > 0:
                                    gauge = get_bitola(max(w, h))
                                    area = (2*(w+h)/1000) * l * (1+perda_corte)
                                    peso = area * get_peso(gauge)
                                    kg_total += peso
                                    
                                    res_dutos.append({
                                        "Dim": f"{int(w)}x{int(h)}", "Comp(m)": round(l, 2),
                                        "Peso(kg)": round(peso, 1), "Obs": d.get("nota")
                                    })
                            
                            # Exibição
                            st.metric("Peso Total Estimado", f"{kg_total:,.1f} kg")
                            
                            t1, t2 = st.tabs(["Dutos", "Equipamentos"])
                            with t1: st.dataframe(pd.DataFrame(res_dutos), use_container_width=True)
                            with t2: st.dataframe(pd.DataFrame(dados.get("equipamentos", [])), use_container_width=True)

    except Exception as e:
        st.error(f"Erro no DXF: {e}")
    finally:
        if os.path.exists(path_temp): os.remove(path_temp)
