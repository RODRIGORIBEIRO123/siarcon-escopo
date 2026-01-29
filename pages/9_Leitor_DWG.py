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
import numpy as np

# --- 🔒 SEGURANÇA ---
if 'logado' not in st.session_state or not st.session_state['logado']:
    st.warning("🔒 Acesso negado. Faça login no Dashboard.")
    st.stop()

st.set_page_config(page_title="Leitor DXF (Smart Measure)", page_icon="📐", layout="wide")

st.title("📐 Leitor de Dutos Inteligente (V21)")
st.markdown("""
**Novo Algoritmo de Medição:**
O sistema usa a medida do texto (ex: **500**x300) para encontrar as paredes do duto desenhadas com essa largura e medir o comprimento exato do trecho até a próxima conexão.
""")

# ============================================================================
# 1. CONFIGURAÇÕES
# ============================================================================
with st.sidebar:
    st.header("⚙️ Calibração")
    
    # Fundamental para a lógica funcionar
    unidade_desenho = st.selectbox(
        "Unidade do Desenho CAD:", 
        ["Milímetros (1u=1mm)", "Centímetros (1u=1cm)", "Metros (1u=1m)"], 
        index=0,
        help="Se a cota diz 500 e a distância no CAD é 500, use Milímetros."
    )
    
    st.info("Ajuste de Tolerância:")
    tolerancia_largura = st.slider("Tolerância na Largura (%)", 1, 20, 10, help="Quanto o desenho pode variar da medida escrita? (Ex: Texto 500, Desenho 505).")
    
    st.divider()
    st.subheader("🛡️ Travas")
    raio_busca = st.number_input("Raio de Busca (mm)", value=1500)
    
    st.subheader("📋 NBR 16401")
    classe_pressao = st.selectbox("Classe Pressão", ["Classe A (Baixa)", "Classe B (Média)", "Classe C (Alta)"])
    perda_corte = st.number_input("% Perda / Corte", value=10.0)
    tipo_isolamento = st.selectbox("Isolamento", ["Lã de Vidro", "Borracha Elast.", "Isopor", "Sem Isolamento"])

# ============================================================================
# 2. MOTOR GEOMÉTRICO AVANÇADO (Detecta Paredes Paralelas)
# ============================================================================
def get_midpoint(p1, p2):
    return ((p1[0]+p2[0])/2, (p1[1]+p2[1])/2)

def dist_sq(p1, p2):
    return (p1[0]-p2[0])**2 + (p1[1]-p2[1])**2

def get_line_angle(start, end):
    return math.degrees(math.atan2(end.y - start.y, end.x - start.x)) % 180

def get_line_length(start, end):
    return math.hypot(end.x - start.x, end.y - start.y)

def ler_geometria_inteligente(msp, coords_texto, dimensoes_texto, layers_duto, escala_unidade):
    """
    Tenta encontrar linhas paralelas espaçadas pela largura ou altura do duto.
    """
    linhas_candidatas = []
    
    # 1. Coletar linhas próximas na layer certa
    for e in msp.query('LINE'):
        if e.dxf.layer in layers_duto:
            mid = get_midpoint(e.dxf.start, e.dxf.end)
            # Check de raio rápido
            if abs(mid[0] - coords_texto[0]) > raio_busca: continue
            if abs(mid[1] - coords_texto[1]) > raio_busca: continue
            
            d = math.hypot(mid[0]-coords_texto[0], mid[1]-coords_texto[1])
            if d <= raio_busca:
                linhas_candidatas.append(e)

    if not linhas_candidatas: return 0.0, "Nenhuma linha perto"

    # 2. Tentar casar Largura ou Altura com pares de linhas paralelas
    # Converter dimensões do texto para unidade do CAD
    dims_no_cad = [d / escala_unidade for d in dimensoes_texto] # ex: [500, 300]
    
    melhor_comprimento = 0.0
    match_encontrado = False

    # Compara linha A com linha B
    for i in range(len(linhas_candidatas)):
        l1 = linhas_candidatas[i]
        ang1 = get_line_angle(l1.dxf.start, l1.dxf.end)
        len1 = get_line_length(l1.dxf.start, l1.dxf.end)
        
        for j in range(i + 1, len(linhas_candidatas)):
            l2 = linhas_candidatas[j]
            ang2 = get_line_angle(l2.dxf.start, l2.dxf.end)
            len2 = get_line_length(l2.dxf.start, l2.dxf.end)
            
            # Devem ser paralelas (angulo proximo)
            if abs(ang1 - ang2) > 5: continue
            
            # Calcula distancia entre as linhas paralelas
            # Pega mid de L1 e projeta em L2? Simplificação: Distancia entre centros
            mid1 = get_midpoint(l1.dxf.start, l1.dxf.end)
            mid2 = get_midpoint(l2.dxf.start, l2.dxf.end)
            dist_entre_linhas = math.hypot(mid1[0]-mid2[0], mid1[1]-mid2[1])
            
            # Verifica se essa distancia bate com Largura ou Altura (com tolerância)
            for d_target in dims_no_cad:
                min_val = d_target * (1 - (tolerancia_largura/100))
                max_val = d_target * (1 + (tolerancia_largura/100))
                
                if min_val <= dist_entre_linhas <= max_val:
                    # BINGO! Achamos as paredes do duto.
                    # O comprimento do trecho é a média do comprimento das paredes
                    comp_medio = (len1 + len2) / 2
                    if comp_medio > melhor_comprimento:
                        melhor_comprimento = comp_medio
                        match_encontrado = True
    
    if match_encontrado:
        return melhor_comprimento, "Geometria Casada (Paredes)"
    
    # 3. Fallback: Se não achou paredes paralelas, pega a linha mais longa próxima (Eixo)
    # Assume que a linha mais longa perto do texto é o eixo ou uma parede isolada
    max_len = 0
    for l in linhas_candidatas:
        c = get_line_length(l.dxf.start, l.dxf.end)
        if c > max_len: max_len = c
        
    return max_len, "Linha Simples (Maior Prox.)"


# ============================================================================
# 3. INTELIGÊNCIA ARTIFICIAL + GEOMETRIA
# ============================================================================
def processar_ia_com_geo(texto_limpo, dicionario_geo, msp, layers_duto, unid_cad):
    if not api_key: return None

    # Fatores
    escala = 1.0
    if "Milímetros" in unid_cad: escala = 0.001
    elif "Centímetros" in unid_cad: escala = 0.01

    prompt = f"""
    Engenheiro HVAC. Analise texto DXF (separado por ' | ').
    
    1. IGNORE VAZÕES entre parênteses "(1500)".
    2. EXTRAIA DIMENSÕES "Largura x Altura" (ex: 500x400).
    3. EXTRAIA EQUIPAMENTOS (Fancoil, Split, Grelha).

    SAÍDA JSON:
    {{
        "dutos": [{{ "dimensao_original": "500x400", "largura_mm": 500, "altura_mm": 400 }}],
        "equipamentos": [{{ "item": "Nome", "quantidade": 1 }}]
    }}
    """

    try:
        response = openai.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": f"Texto:\n{texto_limpo[:60000]}"} 
            ],
            temperature=0.0,
            response_format={"type": "json_object"}
        )
        ai_data = json.loads(response.choices[0].message.content)
        
        # PÓS-PROCESSAMENTO GEOMÉTRICO
        lista_dutos = ai_data.get("dutos", [])
        
        for d in lista_dutos:
            dim_str = d.get("dimensao_original", "")
            w = d.get("largura_mm", 0)
            h = d.get("altura_mm", 0)
            
            # Encontrar texto no desenho
            # Procura texto exato ou aproximado
            coords = None
            key_ia = dim_str.replace('.','').replace(' ','').strip()
            
            for g in dicionario_geo['textos']:
                key_cad = g['txt'].replace('.','').replace(' ','').strip()
                if key_ia in key_cad:
                    coords = g['pos']
                    break
            
            if coords and w > 0:
                # Chama a nova função de Paredes Paralelas
                comp_cad, status = ler_geometria_inteligente(msp, coords, [w, h], layers_duto, 1.0 if "Milímetros" in unid_cad else (1000 if "Metros" in unid_cad else 10))
                
                # Converte para Metros
                d['comprimento_m'] = comp_cad * escala
                d['nota'] = status
            else:
                d['comprimento_m'] = 0
                d['nota'] = "Texto não localizado"

        return ai_data

    except Exception as e:
        return {"erro": str(e)}

# ============================================================================
# 4. INTERFACE E RESULTADOS
# ============================================================================
uploaded_dxf = st.file_uploader("📂 Carregar DXF", type=["dxf"])

def listar_layers(doc):
    return sorted(list(set([layer.dxf.name for layer in doc.layers])))

# ... (Funções de Excel e Bitola NBR mantidas do anterior, omitidas aqui para brevidade mas devem estar no arquivo) ...
def calcular_peso_chapa(bitola):
    pesos = {26: 4.00, 24: 5.60, 22: 6.80, 20: 8.40, 18: 10.50}
    return pesos.get(int(bitola), 6.0)

def definir_bitola_nbr(maior_lado_mm, classe_txt):
    if "Classe A" in classe_txt: return 24 if maior_lado_mm <= 750 else 22 if maior_lado_mm <= 1200 else 20
    elif "Classe B" in classe_txt: return 24 if maior_lado_mm <= 600 else 22 if maior_lado_mm <= 1000 else 20
    else: return 24 if maior_lado_mm <= 250 else 22 if maior_lado_mm <= 500 else 20

def gerar_excel_final(df_dutos, df_equip, resumo):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        if not df_dutos.empty: df_dutos.to_excel(writer, sheet_name='Dutos', index=False)
        if not df_equip.empty: df_equip.to_excel(writer, sheet_name='Equipamentos', index=False)
    output.seek(0)
    return output

if uploaded_dxf:
    with st.spinner("Lendo arquivo..."):
        # Salva temp
        path_temp = tempfile.NamedTemporaryFile(delete=False, suffix=".dxf").name
        uploaded_dxf.seek(0)
        with open(path_temp, "wb") as f: f.write(uploaded_dxf.getbuffer())
        
        try:
            try: doc = ezdxf.readfile(path_temp)
            except: doc, auditor = recover.readfile(path_temp)
            
            msp = doc.modelspace()
            all_layers = listar_layers(doc)
            
            # SELETORES
            c1, c2 = st.columns(2)
            sel_layers_duto = c1.multiselect("Layer das LINHAS de Dutos:", all_layers)
            sel_layers_equip = c2.multiselect("Layer de BLOCOS (Equip):", all_layers)
            
            # EXTRAÇÃO
            raw_text = []
            geo_dict = {'textos': []}
            
            for e in msp.query('TEXT MTEXT'):
                t = str(e.dxf.text).strip()
                if len(t) > 2 and "LAYER" not in t.upper():
                    raw_text.append(t)
                    geo_dict['textos'].append({'txt': t, 'pos': (e.dxf.insert.x, e.dxf.insert.y)})
            
            if sel_layers_equip:
                for b in msp.query('INSERT'):
                    if b.dxf.layer in sel_layers_equip:
                         raw_text.append(b.dxf.name)

            st.info(f"Textos lidos: {len(raw_text)}")

            if st.button("🚀 Calcular (Medição por Paredes)", type="primary"):
                if not sel_layers_duto or not api_key:
                    st.error("Selecione Layers e API Key.")
                else:
                    with st.spinner("Procurando paredes paralelas conforme largura dos dutos..."):
                        txt_join = " | ".join(raw_text)
                        dados = processar_ia(txt_join, geo_dict, msp, raio_busca, sel_layers_duto, sel_layers_equip, unidade_desenho, 1.0)
                        
                        if "erro" in dados: st.error(dados['erro'])
                        else:
                            st.session_state['res_geo'] = dados
                            st.rerun()

        except Exception as e: st.error(f"Erro: {e}")
        finally: 
            if os.path.exists(path_temp): os.remove(path_temp)

if 'res_geo' in st.session_state:
    d = st.session_state['res_geo']
    t1, t2, t3, t4 = st.tabs(["🌪️ Dutos","💨 Terminais","⚙️ Equips","⚡ Elétrica"])
    
    with t1:
        if d["dutos"]:
            df = pd.DataFrame(d["dutos"])
            # Filtra e converte
            for c in ["largura_mm", "altura_mm", "comprimento_m"]: 
                 if c in df.columns: df[c] = pd.to_numeric(df[c], errors='coerce').fillna(0)
            
            # TABELA EDITÁVEL
            st.info("Valide os comprimentos medidos pelo robô.")
            df_ed = st.data_editor(df, num_rows="dynamic")
            
            # CÁLCULOS FINAIS
            df_ed["Perímetro"] = (2*df_ed["largura_mm"] + 2*df_ed["altura_mm"])/1000
            df_ed["Área (m²)"] = df_ed["Perímetro"] * df_ed["comprimento_m"]
            
            # Bitolas
            df_ed["Bitola"] = df_ed["largura_mm"].apply(lambda x: definir_bitola_nbr(x, classe_pressao))
            df_ed["Peso (kg)"] = df_ed.apply(lambda r: r["Área (m²)"] * calcular_peso_chapa(r["Bitola"]), axis=1)
            
            fator = 1 + (perda_corte/100)
            tot_area = (df_ed["Área (m²)"] * fator).sum()
            tot_peso = (df_ed["Peso (kg)"] * fator).sum()
            
            c1, c2, c3 = st.columns(3)
            c1.metric("Área Total", f"{tot_area:,.2f} m²")
            c2.metric("Peso Total", f"{tot_peso:,.0f} kg")
            c3.metric("Isolamento", f"{tot_area:,.2f} m²" if tipo_isolamento != "Sem Isolamento" else "-")
            
            # Excel
            xlsx = gerar_excel_final(df_ed, pd.DataFrame(d.get("equipamentos", [])), {"Peso": tot_peso})
            st.download_button("📥 Baixar Excel", xlsx, "Levantamento_V21.xlsx")
            
    with t3:
        if d["equipamentos"]: st.dataframe(pd.DataFrame(d["equipamentos"]))
