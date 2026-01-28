import streamlit as st
import ezdxf
from ezdxf import recover
import math
from openai import OpenAI
import pandas as pd
import io
import re
from collections import Counter

# --- 🔒 SEGURANÇA ---
if 'logado' not in st.session_state or not st.session_state['logado']:
    st.warning("🔒 Acesso negado. Faça login no Dashboard.")
    st.stop()

st.set_page_config(page_title="Leitor DXF (Modo Arrastão)", page_icon="📐", layout="wide")

st.title("📐 Leitor Técnico DXF (Modo IA Pura)")
st.markdown("""
**Estratégia:** Esta versão captura TODO texto curto encontrado no desenho e deixa a IA filtrar o que é engenharia.
Isso garante que nada seja perdido por filtros rígidos.
""")

# ============================================================================
# 1. CONFIGURAÇÕES
# ============================================================================
with st.sidebar:
    st.header("⚙️ Configurações")
    classe_pressao = st.selectbox("Classe de Pressão", ["Classe A (Baixa)", "Classe B (Média)", "Classe C (Alta)", "Classe D (Especial)"])
    
    st.divider()
    st.subheader("📏 Calibração")
    unidade_desenho = st.selectbox("Unidade do Desenho", ["Centímetros (cm)", "Metros (m)", "Milímetros (mm)"])
    
    if unidade_desenho == "Centímetros (cm)": raio_padrao = 50.0
    elif unidade_desenho == "Metros (m)": raio_padrao = 0.5
    else: raio_padrao = 500.0

    raio_busca = st.number_input("Raio de Busca (Geometria)", value=raio_padrao)
    comp_minimo = st.number_input("Comprimento Padrão (m)", value=1.10)
    
    st.divider()
    perda_corte = st.number_input("% Perda / Corte", value=10.0)
    tipo_isolamento = st.selectbox("Isolamento", ["Lã de Vidro", "Borracha Elast.", "Isopor", "Sem Isolamento"])

# ============================================================================
# 2. MOTOR DE EXTRAÇÃO (SEM FILTRO)
# ============================================================================

def calcular_distancia(p1, p2):
    return math.hypot(p2[0] - p1[0], p2[1] - p1[1])

def obter_comprimento_entidade(entity):
    try:
        if entity.dxftype() == 'LINE':
            return calcular_distancia(entity.dxf.start, entity.dxf.end)
        elif entity.dxftype() == 'LWPOLYLINE':
            pts = entity.get_points()
            if entity.closed: 
                max_seg = 0
                for i in range(len(pts) - 1):
                    s = calcular_distancia(pts[i], pts[i+1])
                    if s > max_seg: max_seg = s
                return max_seg
            else: 
                comp = 0
                for i in range(len(pts) - 1): comp += calcular_distancia(pts[i], pts[i+1])
                return comp
    except: return 0
    return 0

def extrair_texto_modo_resgate(bytes_content):
    """Lê tudo o que parece texto curto, sem regex complexo."""
    itens = []
    try: texto_full = bytes_content.decode("cp1252", errors="ignore")
    except: texto_full = bytes_content.decode("utf-8", errors="ignore")
    
    linhas = texto_full.split('\n')
    for l in linhas:
        l = l.strip()
        # Filtro MÍNIMO: Apenas ignora linhas vazias ou gigantes (códigos binários)
        if len(l) > 1 and len(l) < 60:
            # Pega tudo. A IA que se vire.
            itens.append({'texto': l, 'geo_m': 0.0})
                
    return itens, "Modo Resgate (Texto Bruto)"

def extrair_dados_com_geometria(bytes_file, raio_search):
    bytes_content = bytes_file.getvalue()
    
    try:
        try: content_str = bytes_content.decode("cp1252")
        except: content_str = bytes_content.decode("utf-8", errors='ignore')
        
        stream = io.StringIO(content_str)
        doc, auditor = recover.read(stream)
        msp = doc.modelspace()
        
        geometrias = []
        # Aumentei o limite de geometria para tentar achar mais linhas
        for i, e in enumerate(msp.query('LINE LWPOLYLINE')):
            if i > 8000: break
            geometrias.append(e)
            
        textos = list(msp.query('TEXT MTEXT'))
        
        itens = []
        count_processados = 0
        
        progresso = st.progress(0, text="Lendo textos...")
        total = len(textos)

        for idx, e in enumerate(textos):
            if idx % 500 == 0: progresso.progress(min(100, int(idx/total*100)))
            
            txt = e.dxf.text if e.dxftype() == 'TEXT' else e.text
            if not txt: continue
            
            t_clean = txt.strip()
            # Filtro apenas de tamanho, para não pegar blocos de nota gigantes
            if len(t_clean) < 2 or len(t_clean) > 60: continue
            
            # Tenta medir
            comp_final = 0.0
            try:
                insert = e.dxf.insert
                pos = (insert[0], insert[1])
                maior = 0.0
                if geometrias:
                    c_check = 0
                    for geo in geometrias:
                        try:
                            if geo.dxftype()=='LINE': ref=geo.dxf.start
                            else: ref=geo.get_points()[0]
                            if abs(ref[0]-pos[0]) > raio_search*2: continue
                            if math.hypot(ref[0]-pos[0], ref[1]-pos[1]) <= raio_search:
                                c = obter_comprimento_entidade(geo)
                                if c > maior: maior = c
                        except: pass
                        c_check += 1
                        if c_check > 300: break
                
                comp_final = maior
                if unidade_desenho == "Centímetros (cm)": comp_final /= 100
                elif unidade_desenho == "Milímetros (mm)": comp_final /= 1000
            except: pass
            
            itens.append({'texto': t_clean, 'geo_m': comp_final})
            count_processados += 1
            # Aumentei o limite de segurança
            if count_processados > 6000: break
            
        progresso.empty()
        return itens, "Leitura Padrão"

    except Exception as e:
        return extrair_texto_modo_resgate(bytes_content)

# ============================================================================
# 3. INTELIGÊNCIA ARTIFICIAL (SELEÇÃO INTELIGENTE)
# ============================================================================
def analisar_com_ia_detalhada(lista_itens):
    if "openai" not in st.secrets: st.error("Sem chave API"); return None
    
    # Agrupa
    resumo = {}
    for item in lista_itens:
        t = item['texto']
        if t not in resumo: resumo[t] = {'qtd': 0, 'soma': 0.0}
        resumo[t]['qtd'] += 1
        resumo[t]['soma'] += item['geo_m']
        
    # ORDENAÇÃO INTELIGENTE PARA A IA
    # Em vez de mandar só os mais frequentes, priorizamos o que PARECE duto
    def score_prioridade(texto):
        t = texto.upper()
        # Se tiver X no meio de numeros (300x200), ganha prioridade máxima
        if re.search(r'\d[xX]\d', t): return 1000
        if "FC-" in t or "TAG" in t: return 800
        return 1 # Texto comum
        
    itens_ordenados = sorted(resumo.items(), key=lambda x: (score_prioridade(x[0]), x[1]['qtd']), reverse=True)
    
    # Pega os Top 450 itens mais "interessantes"
    txt_prompt = ""
    for k, v in itens_ordenados[:450]:
        med = v['soma'] / v['qtd'] if v['qtd'] > 0 else 0
        txt_prompt += f"TXT:'{k}'|Q:{v['qtd']}|MED:{med:.2f}m\n"
        
    client = OpenAI(api_key=st.secrets["openai"]["api_key"])
    
    prompt = """
    Você é um Engenheiro HVAC Sênior. 
    Recebi uma lista SUJA de textos do CAD. Sua missão é GARIMPAR o que é útil.
    
    IGNORE: Coordenadas, nomes de layers (A-WALL), códigos estranhos, nomes de ambientes.
    
    EXTRAIA APENAS:
    1. DUTOS: Textos numéricos como '500x300', '30x20', 'ø200'.
    2. EQUIPAMENTOS: Tags (FC-01, VZ-01) e Detalhes (5TR, 12000BTU).
    3. TERMINAIS: Grelhas (G-), Difusores.
    
    SAÍDA CSV (;):
    ---DUTOS---
    Largura;Altura;Qtd;CompMedio
    500;300;10;1.20
    
    ---EQUIPAMENTOS---
    Tag;Tipo;Detalhes;Qtd
    FC-1;Fancoil;5TR;2
    
    ---TERMINAIS---
    Item;Qtd
    Grelha 600x600;5
    
    ---ELETRICA---
    Tag;Desc;Qtd
    """
    
    try:
        r = client.chat.completions.create(
            model="gpt-4o", 
            messages=[{"role":"system","content":prompt},{"role":"user","content":txt_prompt}], 
            temperature=0.1
        )
        return r.choices[0].message.content
    except Exception as e: st.error(e); return None

def processar_resposta(r):
    if not r: return None
    blocos = {"DUTOS":[],"TERMINAIS":[],"EQUIPAMENTOS":[],"ELETRICA":[]}
    atual = None
    for l in r.split('\n'):
        l = l.strip()
        if "---DUTOS" in l: atual="DUTOS"; continue
        if "---TERM" in l: atual="TERMINAIS"; continue
        if "---EQUI" in l: atual="EQUIPAMENTOS"; continue
        if "---ELET" in l: atual="ELETRICA"; continue
        if atual and ";" in l and "Largura" not in l and "Tag" not in l: 
            blocos[atual].append(l.split(';'))
    return blocos

# ============================================================================
# 4. INTERFACE
# ============================================================================
uploaded_dxf = st.file_uploader("📂 Carregar DXF", type=["dxf"])

if uploaded_dxf:
    with st.spinner("Lendo arquivo bruto..."):
        itens_brutos, msg_status = extrair_dados_com_geometria(uploaded_dxf, raio_busca)

    if itens_brutos and len(itens_brutos) > 0:
        st.success(f"✅ Arquivo Lido! {len(itens_brutos)} textos encontrados.")
        st.caption(f"Status: {msg_status}")
        
        if st.button("🚀 Extrair Quantitativo (IA)", type="primary"):
            with st.spinner("Garimpando dados de engenharia..."):
                res = analisar_com_ia_detalhada(itens_brutos)
                if res:
                    st.session_state['dados_geo_v5'] = processar_resposta(res)
                    st.rerun()
    else:
        st.error("❌ O arquivo parece vazio de textos legíveis.")

# ============================================================================
# 5. RESULTADOS
# ============================================================================
if 'dados_geo_v5' in st.session_state:
    d = st.session_state['dados_geo_v5']
    if not d: st.stop()

    t1, t2, t3, t4 = st.tabs(["🌪️ Dutos","💨 Terminais","⚙️ Equips","⚡ Elétrica"])
    
    with t1:
        if d["DUTOS"]:
            try:
                df = pd.DataFrame(d["DUTOS"], columns=["Largura","Altura","Qtd","CompIA"])
                for c in df.columns: df[c] = pd.to_numeric(df[c], errors='coerce').fillna(0)
                
                df["Comp. Unit (m)"] = df["CompIA"].apply(lambda x: x if x > 0.2 else comp_minimo)
                
                df_ed = st.data_editor(df, num_rows="dynamic", key="dutos_v6")
                
                df_ed["Perímetro"] = (2*df_ed["Largura"] + 2*df_ed["Altura"])/1000
                df_ed["Total (m)"] = df_ed["Qtd"] * df_ed["Comp. Unit (m)"]
                df_ed["Área (m²)"] = df_ed["Perímetro"] * df_ed["Total (m)"]
                
                fator = 1 + (perda_corte/100)
                area = (df_ed["Área (m²)"] * fator).sum()
                
                c1, c2, c3 = st.columns(3)
                c1.metric("Área Total", f"{area:,.2f} m²")
                c2.metric("Peso (~5.6kg/m²)", f"{area*5.6:,.0f} kg")
                isol = f"{area:,.2f} m²" if tipo_isolamento != "Sem Isolamento" else "-"
                c3.metric("Isolamento", isol)
                st.dataframe(df_ed)
            except Exception as e:
                st.error("Erro na tabela. Tente recarregar.")
        else: st.warning("Nenhum duto encontrado.")

    with t2:
        if d["TERMINAIS"]: st.data_editor(pd.DataFrame(d["TERMINAIS"], columns=["Item","Qtd"]), num_rows="dynamic")
        else: st.info("Vazio")

    with t3:
        if d["EQUIPAMENTOS"]: st.data_editor(pd.DataFrame(d["EQUIPAMENTOS"], columns=["Tag","Tipo","Detalhe","Qtd"]), num_rows="dynamic")
        else: st.info("Vazio")

    with t4:
        if d["ELETRICA"]: st.data_editor(pd.DataFrame(d["ELETRICA"], columns=["Tag","Desc","Qtd"]), num_rows="dynamic")
        else: st.info("Vazio")
