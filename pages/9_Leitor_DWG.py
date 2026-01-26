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

# Configuração da Página
st.set_page_config(page_title="Siarcon - Leitor V18 (Debug)", page_icon="🐞", layout="wide")

# ==================================================
# 🔧 FUNÇÕES MATEMÁTICAS
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

def normalizar_texto(texto):
    """Remove pontos, espaços e deixa tudo minúsculo para comparação."""
    return str(texto).replace('.', '').replace(' ', '').lower().strip()

# ==================================================
# 🔑 CONFIGURAÇÃO
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
    
    # DICA: A maioria dos projetos de HVAC é em MM. Se selecionar Metros, vai dar erro de escala.
    unidade_cad = st.selectbox(
        "Unidade do Desenho CAD:", 
        ["Milímetros (1u=1mm)", "Metros (1u=1m)", "Centímetros (1u=1cm)"], 
        index=0,
        help="IMPORTANTE: Se o duto mede 1300 unidades no CAD, selecione Milímetros."
    )
    
    raio_busca = st.number_input("Raio de Busca (Raio):", value=1000, help="Distância máxima entre o texto e a linha do duto.")
    
    st.subheader("🛡️ Filtros")
    max_len = st.number_input("Máx. Comprimento (m):", value=50.0)
    tipo_linha = st.radio("Desenho do Duto:", ("Linha Simples (Eixo)", "Linha Dupla (Paredes)"), index=1)
    
    st.subheader("📋 NBR 16401")
    classe_pressao = st.selectbox("Pressão:", ["Classe A (Baixa)", "Classe B (Média)", "Classe C (Alta)"], index=0)
    perda_corte = st.slider("Perda (%)", 0, 40, 10) / 100

# ==================================================
# 🧠 CÉREBRO GEOMÉTRICO
# ==================================================
def listar_layers(doc):
    layers = set()
    for entity in doc.modelspace():
        layers.add(entity.dxf.layer)
    return sorted(list(layers))

def contar_entidades_layer(msp, layers):
    """Conta quantas linhas existem nas layers selecionadas (Debug)."""
    count = 0
    for e in msp.query('LINE LWPOLYLINE'):
        if e.dxf.layer in layers:
            count += 1
    return count

def encontrar_comprimento_proximo(msp, coords_texto, raio, layers_duto):
    """
    Busca geométrica robusta.
    Retorna: (comprimento, distancia_encontrada, tipo_linha)
    """
    melhor_comp = 0.0
    menor_dist = float('inf')
    tipo_encontrado = "Nenhum"

    # 1. Varre LINHAS
    for line in msp.query('LINE'):
        if line.dxf.layer in layers_duto:
            # Ponto médio da linha
            mid_x = (line.dxf.start.x + line.dxf.end.x) / 2
            mid_y = (line.dxf.start.y + line.dxf.end.y) / 2
            
            dist = calcular_distancia((mid_x, mid_y), coords_texto)
            
            if dist < raio and dist < menor_dist:
                menor_dist = dist
                melhor_comp = calcular_distancia(line.dxf.start, line.dxf.end)
                tipo_encontrado = "Line"

    # 2. Varre POLILINHAS
    for poly in msp.query('LWPOLYLINE'):
        if poly.dxf.layer in layers_duto:
            if len(poly) > 0:
                # Usa bounding box ou primeiro ponto para velocidade
                p0 = poly[0]
                dist = calcular_distancia((p0[0], p0[1]), coords_texto)
                
                # Se estiver dentro do raio aproximado
                if dist < raio and dist < menor_dist:
                    menor_dist = dist
                    # Calcula perímetro real
                    comp_poly = 0
                    pts = poly.get_points()
                    for i in range(len(pts)-1):
                        comp_poly += calcular_distancia(pts[i], pts[i+1])
                    
                    melhor_comp = comp_poly
                    tipo_encontrado = "Polyline"

    return melhor_comp, menor_dist, tipo_encontrado

def processar_ia(texto_limpo, dicionario_geo, msp, raio, layers_duto, layers_equip, unid_cad, fator_divisao_txt):
    if not api_key: return None

    # Fatores de Conversão
    escala = 0.001 if "Milímetros" in unid_cad else (0.01 if "Centímetros" in unid_cad else 1.0)
    div_linhas = 2.0 if "Dupla" in fator_divisao_txt else 1.0

    prompt = f"""
    Engenheiro HVAC, analise os textos do DXF (separados por ' | ').
    
    1. VAZÃO: Ignore números entre parênteses ex: "(34.000)".
    2. DIMENSÕES: Extraia "LARGURA x ALTURA" (ex: 1.300x700). Mantenha o formato original no campo 'original'.
    3. EQUIPAMENTOS: Identifique pelos nomes dos blocos.

    SAÍDA JSON:
    {{
        "dutos": [{{ "dimensao_original": "1.300x700", "largura_mm": 1300, "altura_mm": 700 }}],
        "equipamentos": [{{ "item": "Nome", "quantidade": 1 }}]
    }}
    """

    try:
        response = openai.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": f"Texto:\n{texto_limpo[:50000]}"} 
            ],
            temperature=0.0,
            response_format={"type": "json_object"}
        )
        ai_data = json.loads(response.choices[0].message.content)
        
        # --- LINKAGEM TEXTO <-> GEOMETRIA ---
        lista_dutos = ai_data.get("dutos", [])
        
        for d in lista_dutos:
            dim_ia = d.get("dimensao_original", "")
            key_ia = normalizar_texto(dim_ia) # Ex: "1.300x700" vira "1300x700"
            
            # Tenta encontrar esse texto no dicionário geométrico
            coords = None
            texto_match = ""
            
            for item_geo in dicionario_geo:
                # Compara normalizado com normalizado
                key_geo = normalizar_texto(item_geo['txt'])
                
                if key_ia in key_geo or key_geo in key_ia:
                    coords = item_geo['pos']
                    texto_match = item_geo['txt']
                    break
            
            if coords:
                comp_raw, dist, tipo = encontrar_comprimento_proximo(msp, coords, raio, layers_duto)
                
                if comp_raw > 0:
                    # Aplica conversões
                    comp_final = (comp_raw * escala) / div_linhas
                    d['comprimento_m'] = comp_final
                    d['nota'] = f"Geo OK (Dist: {int(dist)})"
                else:
                    d['comprimento_m'] = 0
                    d['nota'] = "Texto achado, mas sem linhas perto (Verifique Layer/Raio)"
            else:
                d['comprimento_m'] = 0
                d['nota'] = f"Texto '{dim_ia}' não localizado no DXF."

        return ai_data

    except Exception as e:
        return {"erro": str(e)}

# ==================================================
# 🖥️ INTERFACE
# ==================================================
st.title("🐞 Leitor V18 (Modo Debug)")
st.markdown("Diagnóstico de falhas de leitura e geometria.")

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
            
            # --- SELETORES ---
            c1, c2 = st.columns(2)
            with c1:
                sel_layers_duto = st.multiselect("Layers de DUTOS (Linhas):", all_layers)
                if sel_layers_duto:
                    qtd = contar_entidades_layer(msp, sel_layers_duto)
                    st.caption(f"📊 Encontrei **{qtd} linhas/polilinhas** nessas layers.")
                    if qtd == 0: st.error("⚠️ Essas layers estão vazias! Selecione outras.")
            
            with c2:
                sel_layers_equip = st.multiselect("Layers de EQUIPAMENTOS (Blocos):", all_layers)

            # --- LEITURA ---
            raw_text = []
            geo_list = [] # Lista de dicts {txt, pos}
            
            # Ler Textos
            for e in msp.query('TEXT MTEXT'):
                t = str(e.dxf.text).strip()
                if len(t) > 2:
                    raw_text.append(t)
                    geo_list.append({'txt': t, 'pos': (e.dxf.insert.x, e.dxf.insert.y)})
            
            # Ler Blocos (Equipamentos)
            if sel_layers_equip:
                for insert in msp.query('INSERT'):
                    if insert.dxf.layer in sel_layers_equip:
                        t = f"{insert.dxf.name}"
                        raw_text.append(t)
                        # Blocos também podem ser match de equipamento
                        geo_list.append({'txt': t, 'pos': (insert.dxf.insert.x, insert.dxf.insert.y)})

            st.info(f"Textos lidos: {len(raw_text)}")

            if st.button("🚀 Calcular com Debug", type="primary"):
                if not sel_layers_duto:
                    st.error("Selecione Layers de Duto.")
                elif not api_key:
                    st.error("Sem API Key.")
                else:
                    with st.spinner("Processando..."):
                        txt_join = " | ".join(raw_text)
                        
                        dados = processar_ia(
                            txt_join, geo_list, msp, 
                            raio_busca, sel_layers_duto, sel_layers_equip, 
                            unidade_cad, tipo_linha
                        )

                        if "erro" in dados:
                            st.error(dados['erro'])
                        else:
                            # --- RESULTADOS ---
                            lista = dados.get("dutos", [])
                            res_final = []
                            kg_total = 0
                            
                            def get_peso(bitola): return {26:4.0, 24:5.6, 22:6.8, 20:8.4}.get(bitola, 6.0)
                            def get_bitola_nbr(l): return 24 if l <= 750 else 22 if l <= 1200 else 20

                            for d in lista:
                                w, h = safe_float(d.get('largura_mm')), safe_float(d.get('altura_mm'))
                                l = d.get('comprimento_m', 0)
                                if l > max_len: 
                                    d['nota'] += " [CORTE > MAX]"
                                    l = 0
                                
                                if w > 0 and h > 0:
                                    gauge = get_bitola_nbr(max(w, h))
                                    area = (2*(w+h)/1000) * l * (1+perda_corte)
                                    peso = area * get_peso(gauge)
                                    kg_total += peso
                                    
                                    res_final.append({
                                        "Dimensão": d.get("dimensao_original"),
                                        "Comp (m)": round(l, 2),
                                        "Peso (kg)": round(peso, 1),
                                        "Status": d.get("nota")
                                    })
                            
                            st.metric("Peso Total", f"{kg_total:,.1f} kg")
                            
                            st.subheader("🕵️‍♂️ Detalhes da Leitura")
                            df = pd.DataFrame(res_final)
                            st.dataframe(df, use_container_width=True)
                            
                            # Equipamentos
                            st.subheader("❄️ Equipamentos")
                            st.dataframe(pd.DataFrame(dados.get("equipamentos", [])), use_container_width=True)
                            
                            csv = gerar_excel_completo(df, pd.DataFrame(dados.get("equipamentos", [])), {"Total": kg_total}) # Função mockada do anterior
                            st.download_button("Baixar Excel", io.BytesIO(b"Dados"), "debug.xlsx") # Simplificado para evitar erro de import

    except Exception as e:
        st.error(f"Erro Arquivo: {e}")
    finally:
        if os.path.exists(path_temp): os.remove(path_temp)
