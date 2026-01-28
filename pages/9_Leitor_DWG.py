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

st.set_page_config(page_title="Leitor DXF (Filtro Inteligente)", page_icon="📐", layout="wide")

st.title("📐 Leitor Técnico DXF (Com Filtro Anti-Ruído)")
st.markdown("""
**Melhoria:** Adicionado um "Pente Fino" que ignora lixo do CAD (layers, coordenadas) e foca apenas em textos que parecem **Medidas (AxL)** ou **Tags (FC-01)**.
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
# 2. FUNÇÕES DE FILTRAGEM (O SEGREDO DO SUCESSO)
# ============================================================================

def eh_texto_de_engenharia(texto):
    """
    Retorna True apenas se o texto parecer uma medida de duto ou tag de equipamento.
    Filtra 99% do lixo do DXF.
    """
    t = texto.upper().strip()
    if len(t) < 2 or len(t) > 40: return False
    
    # 1. Padrão Duto Retangular (Num x Num) ex: 300x200, 30x20
    # Aceita 'X' ou 'x'. Deve ter numeros dos dois lados.
    if re.search(r'\d+\s*[xX]\s*\d+', t): return True
    
    # 2. Padrão Diâmetro (ø200, diam 200)
    if 'ø' in t or '%%C' in t or 'DIAM' in t: return True
    
    # 3. Padrão Tag de Equipamento (Letras-Numeros) ex: FC-01, VZ-02, Q-01
    if re.search(r'[A-Z]{1,5}\s*-\s*\d+', t): return True
    
    # 4. Palavras Chave Específicas
    keywords = ["GRELHA", "DIFUSOR", "VENEZIANA", "DAMPER", "FANCOIL", "SPLIT", "CHILLER", "QUADRO", "DDC", "TR", "BTU", "HP", "CV"]
    if any(k in t for k in keywords): return True
    
    return False

# ============================================================================
# 3. MOTOR DE EXTRAÇÃO
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
    """Modo Bruto com Filtro Inteligente"""
    itens = []
    try: texto_full = bytes_content.decode("cp1252", errors="ignore")
    except: texto_full = bytes_content.decode("utf-8", errors="ignore")
    
    linhas = texto_full.split('\n')
    for l in linhas:
        l = l.strip()
        # APLICA O FILTRO IMEDIATAMENTE
        if eh_texto_de_engenharia(l):
            itens.append({'texto': l, 'geo_m': 0.0})
                
    return itens, "Modo Resgate (Filtro Ativado)"

def extrair_dados_com_geometria(bytes_file, raio_search):
    bytes_content = bytes_file.getvalue()
    
    try:
        try: content_str = bytes_content.decode("cp1252")
        except: content_str = bytes_content.decode("utf-8", errors='ignore')
        
        stream = io.StringIO(content_str)
        doc, auditor = recover.read(stream)
        msp = doc.modelspace()
        
        # Carrega geometria (Limitado)
        geometrias = []
        for i, e in enumerate(msp.query('LINE LWPOLYLINE')):
            if i > 5000: break
            geometrias.append(e)
            
        textos = list(msp.query('TEXT MTEXT'))
        
        # Se tiver muitos textos, não limita mais cegamente. FILTRA PRIMEIRO.
        itens = []
        count_processados = 0
        
        progresso = st.progress(0, text="Filtrando textos de engenharia...")
        total = len(textos)

        for idx, e in enumerate(textos):
            if idx % 500 == 0: progresso.progress(min(100, int(idx/total*100)))
            
            txt = e.dxf.text if e.dxftype() == 'TEXT' else e.text
            if not txt: continue
            
            # FILTRO PENTE FINO AQUI TAMBÉM
            if not eh_texto_de_engenharia(txt): continue
            
            # Se passou no filtro, tenta medir
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
                        if c_check > 200: break
                
                comp_final = maior
                if unidade_desenho == "Centímetros (cm)": comp_final /= 100
                elif unidade_desenho == "Milímetros (mm)": comp_final /= 1000
            except: pass
            
            itens.append({'texto': txt.strip(), 'geo_m': comp_final})
            count_processados += 1
            # Limite de segurança apenas para itens ÚTEIS
            if count_processados > 4000: break
            
        progresso.empty()
        return itens, "Leitura Geométrica (Filtro Ativado)"

    except Exception as e:
        return extrair_texto_modo_resgate(bytes_content)

# ============================================================================
# 4. INTELIGÊNCIA ARTIFICIAL
# ============================================================================
def analisar_com_ia_detalhada(lista_itens):
    if "openai" not in st.secrets: st.error("Sem chave API"); return None
    
    # Agrupa e calcula médias
    resumo = {}
    for item in lista_itens:
        t = item['texto']
        if t not in resumo: resumo[t] = {'qtd': 0, 'soma': 0.0}
        resumo[t]['qtd'] += 1
        resumo[t]['soma'] += item['geo_m']
        
    txt_prompt = ""
    # Agora mandamos TUDO que passou no filtro (pois já limpamos o lixo)
    # Mas limitamos a 400 itens para caber no prompt
    itens_filtrados = sorted(resumo.items(), key=lambda x: x[1]['qtd'], reverse=True)[:400]
    
    if not itens_filtrados: return "VAZIO"

    for k, v in itens_filtrados:
        med = v['soma'] / v['qtd'] if v['qtd'] > 0 else 0
        txt_prompt += f"TXT:'{k}'|Q:{v['qtd']}|MED:{med:.2f}m\n"
        
    client = OpenAI(api_key=st.secrets["openai"]["api_key"])
    
    prompt = """
    Engenheiro HVAC. Classifique os itens JÁ FILTRADOS.
    
    REGRAS:
    1. DUTOS: Dimensões (AxL, ø). Se MED > 0.2 use-o.
    2. EQUIPAMENTOS: Tag, Tipo, Detalhes (TR/BTU/HP).
    3. TERMINAIS: Grelhas, Difusores.
    
    SAÍDA CSV (;):
    ---DUTOS---
    Largura;Altura;Qtd;CompMedio
    500;400;10;1.20
    
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
            temperature=0.0
        )
        return r.choices[0].message.content
    except Exception as e: st.error(e); return None

def processar_resposta(r):
    if r == "VAZIO": return None
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
# 5. INTERFACE
# ============================================================================
uploaded_dxf = st.file_uploader("📂 Carregar DXF (Filtro Ativado)", type=["dxf"])

if uploaded_dxf:
    with st.spinner("Lendo arquivo e aplicando Filtro Pente-Fino..."):
        itens_brutos, msg_status = extrair_dados_com_geometria(uploaded_dxf, raio_busca)

    if itens_brutos and len(itens_brutos) > 0:
        # Mostra quantos itens UTEIS sobraram
        st.success(f"✅ Arquivo Processado! {len(itens_brutos)} itens RELEVANTES encontrados (Lixo removido).")
        st.caption(f"Método: {msg_status}")
        
        if st.button("🚀 Extrair Quantitativo (IA)", type="primary"):
            with st.spinner("Interpretando dados..."):
                res = analisar_com_ia_detalhada(itens_brutos)
                if res and res != "VAZIO":
                    st.session_state['dados_geo_v4'] = processar_resposta(res)
                    st.rerun()
                else:
                    st.warning("A IA não encontrou itens conhecidos na lista filtrada.")
    else:
        st.error("❌ Nenhum texto de engenharia (medidas, tags) encontrado.")
        st.info("O filtro removeu todo o conteúdo pois parecia lixo de CAD (coordenadas, layers). Verifique se o DXF contém textos como '500x300' ou 'FC-01'.")

# ============================================================================
# 6. RESULTADOS
# ============================================================================
if 'dados_geo_v4' in st.session_state:
    d = st.session_state['dados_geo_v4']
    if not d: st.stop()

    t1, t2, t3, t4 = st.tabs(["🌪️ Dutos","💨 Terminais","⚙️ Equips","⚡ Elétrica"])
    
    with t1:
        if d["DUTOS"]:
            df = pd.DataFrame(d["DUTOS"], columns=["Largura","Altura","Qtd","CompIA"])
            for c in df.columns: df[c] = pd.to_numeric(df[c], errors='coerce').fillna(0)
            
            df["Comp. Unit (m)"] = df["CompIA"].apply(lambda x: x if x > 0.2 else comp_minimo)
            
            st.info(f"Comprimento Padrão usado onde geometria falhou: {comp_minimo}m")
            df_ed = st.data_editor(df, num_rows="dynamic", key="dutos_v5")
            
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
        else: st.warning("Nenhum duto encontrado na lista filtrada.")

    with t2:
        if d["TERMINAIS"]: st.data_editor(pd.DataFrame(d["TERMINAIS"], columns=["Item","Qtd"]), num_rows="dynamic")
        else: st.info("Vazio")

    with t3:
        if d["EQUIPAMENTOS"]: st.data_editor(pd.DataFrame(d["EQUIPAMENTOS"], columns=["Tag","Tipo","Detalhe","Qtd"]), num_rows="dynamic")
        else: st.info("Vazio")

    with t4:
        if d["ELETRICA"]: st.data_editor(pd.DataFrame(d["ELETRICA"], columns=["Tag","Desc","Qtd"]), num_rows="dynamic")
        else: st.info("Vazio")
