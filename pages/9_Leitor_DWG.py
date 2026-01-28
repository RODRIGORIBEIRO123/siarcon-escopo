import streamlit as st
import ezdxf
from ezdxf import recover
import math
from openai import OpenAI
import pandas as pd
import io
import re
from collections import Counter

# --- 🔒 BLOCO DE SEGURANÇA ---
if 'logado' not in st.session_state or not st.session_state['logado']:
    st.warning("🔒 Acesso negado. Faça login no Dashboard.")
    st.stop()

st.set_page_config(page_title="Leitor DXF (Blindado)", page_icon="📐", layout="wide")

st.title("📐 Leitor Técnico DXF (Blindado)")
st.markdown("""
**Status:** Versão com Recuperação de Erros.
Se o arquivo tiver dados binários corrompidos, o sistema ativará o **Modo de Resgate** (Apenas Texto) automaticamente.
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
    
    # Define raio padrão
    if unidade_desenho == "Centímetros (cm)": raio_padrao = 50.0
    elif unidade_desenho == "Metros (m)": raio_padrao = 0.5
    else: raio_padrao = 500.0

    raio_busca = st.number_input("Raio de Busca (Geometria)", value=raio_padrao, help="Distância para procurar linhas.")
    comp_minimo = st.number_input("Comprimento Padrão (m)", value=1.10, help="Usado se a geometria falhar.")
    
    st.divider()
    perda_corte = st.number_input("% Perda / Corte", value=10.0)
    tipo_isolamento = st.selectbox("Isolamento", ["Lã de Vidro", "Borracha Elast.", "Isopor", "Sem Isolamento"])

# ============================================================================
# 2. MOTOR DE EXTRAÇÃO (COM RESGATE BINÁRIO)
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
    """
    Função de última instância: Lê o arquivo binário ignorando erros e extrai strings.
    """
    textos_encontrados = []
    # Tenta decodificar ignorando erros (Latin-1 cobre quase tudo)
    try:
        texto_full = bytes_content.decode("cp1252", errors="ignore")
    except:
        texto_full = bytes_content.decode("utf-8", errors="ignore")
    
    # No DXF, textos costumam vir após o marcador de grupo 1.
    # Regex simples para pegar linhas que parecem texto de engenharia
    # Procura linhas que tenham letras/números e pelo menos 3 caracteres
    linhas = texto_full.split('\n')
    for i, linha in enumerate(linhas):
        l = linha.strip()
        # Filtro heurístico: linhas curtas com números ou letras (ex: 500x300, Fancoil)
        if len(l) > 2 and len(l) < 50:
            # Verifica se tem cara de dimensão ou tag (tem numero ou traço)
            if any(char.isdigit() for char in l):
                textos_encontrados.append({'texto': l, 'geo_m': 0.0}) # Geo 0.0 pois perdemos a linha
            elif "GRELHA" in l.upper() or "DIFUSOR" in l.upper() or "FANCOIL" in l.upper():
                textos_encontrados.append({'texto': l, 'geo_m': 0.0})
                
    return textos_encontrados, "Modo de Resgate (Geometria Indisponível)"

def extrair_dados_com_geometria(bytes_file, raio_search):
    """
    Tenta ler com geometria. Se falhar, cai para o modo resgate.
    """
    bytes_content = bytes_file.getvalue()
    
    # --- TENTATIVA 1: EZDXF RECOVER (Tenta consertar o arquivo) ---
    try:
        # Precisamos de um stream de texto
        try: content_str = bytes_content.decode("cp1252")
        except: content_str = bytes_content.decode("utf-8", errors='ignore')
        
        stream = io.StringIO(content_str)
        
        # O Recover é mais robusto que o Read
        doc, auditor = recover.read(stream)
        
        if auditor.has_errors:
            # Se tiver erros críticos, pode ser melhor ir pro resgate, mas tentamos continuar
            pass

        msp = doc.modelspace()
        
        # Carrega geometria (Limitado a 4000 para performance)
        geometrias = []
        count_geo = 0
        for e in msp.query('LINE LWPOLYLINE'):
            geometrias.append(e)
            count_geo += 1
            if count_geo > 4000: break
            
        textos = list(msp.query('TEXT MTEXT'))
        
        # Limite de textos
        if len(textos) > 3000: textos = textos[:3000]

        itens = []
        for e in textos:
            txt = e.dxf.text if e.dxftype() == 'TEXT' else e.text
            if not txt or len(txt) < 3: continue
            
            # Tenta pegar coordenada e medir
            comp_final = 0.0
            try:
                insert = e.dxf.insert
                pos = (insert[0], insert[1])
                
                maior_comp = 0.0
                if geometrias:
                    checks = 0
                    for geo in geometrias:
                        try:
                            if geo.dxftype() == 'LINE': ref = geo.dxf.start
                            else: ref = geo.get_points()[0]
                            
                            dist = math.hypot(ref[0]-pos[0], ref[1]-pos[1])
                            if dist <= raio_search:
                                c = obter_comprimento_entidade(geo)
                                if c > maior_comp: maior_comp = c
                        except: pass
                        checks += 1
                        if checks > 200: break # Otimização
                
                comp_final = maior_comp
                if unidade_desenho == "Centímetros (cm)": comp_final /= 100
                elif unidade_desenho == "Milímetros (mm)": comp_final /= 1000
            except:
                pass # Se der erro na geometria, segue com comp=0
            
            itens.append({'texto': txt.strip(), 'geo_m': comp_final})
            
        return itens, "Leitura Geométrica (Completa)"

    except Exception as e:
        # --- TENTATIVA 2: MODO RESGATE ---
        # Se deu erro de 'Invalid binary data' ou qualquer outro crash
        return extrair_texto_modo_resgate(bytes_content)

# ============================================================================
# 3. INTELIGÊNCIA ARTIFICIAL
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
        
    txt_prompt = ""
    # Pega os 350 mais frequentes
    for k, v in sorted(resumo.items(), key=lambda x: x[1]['qtd'], reverse=True)[:350]:
        med = v['soma'] / v['qtd'] if v['qtd'] > 0 else 0
        txt_prompt += f"TXT:'{k}'|Q:{v['qtd']}|MED:{med:.2f}m\n"
        
    client = OpenAI(api_key=st.secrets["openai"]["api_key"])
    
    prompt = """
    Engenheiro HVAC Sênior. Classifique os itens (Texto + Qtd + CompMédio).
    
    REGRAS:
    1. DUTOS: Dimensões (AxL, ø). Se MED > 0.2 use-o. Se MED=0, marque 0.
    2. EQUIPAMENTOS: Procure TR/BTU/HP/CV/Volts nos textos.
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
    Q-1;Quadro;1
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
uploaded_dxf = st.file_uploader("📂 Carregar DXF (Qualquer versão)", type=["dxf"])

if uploaded_dxf:
    with st.spinner("Analisando arquivo..."):
        itens_brutos, msg_status = extrair_dados_com_geometria(uploaded_dxf, raio_busca)

    if itens_brutos:
        tipo_msg = st.warning if "Resgate" in msg_status else st.success
        tipo_msg(f"✅ Arquivo Processado! {len(itens_brutos)} itens encontrados.")
        st.caption(f"Método utilizado: {msg_status}")
        
        if st.button("🚀 Extrair Quantitativo (IA)", type="primary"):
            with st.spinner("Interpretando dados..."):
                res = analisar_com_ia_detalhada(itens_brutos)
                if res:
                    st.session_state['dados_geo_v3'] = processar_resposta(res)
                    st.rerun()
    else:
        st.error("❌ Não foi possível ler nenhum dado do arquivo.")

# ============================================================================
# 5. RESULTADOS
# ============================================================================
if 'dados_geo_v3' in st.session_state:
    d = st.session_state['dados_geo_v3']
    t1, t2, t3, t4 = st.tabs(["🌪️ Dutos","💨 Terminais","⚙️ Equips","⚡ Elétrica"])
    
    with t1:
        if d["DUTOS"]:
            df = pd.DataFrame(d["DUTOS"], columns=["Largura","Altura","Qtd","CompIA"])
            for c in df.columns: df[c] = pd.to_numeric(df[c], errors='coerce').fillna(0)
            
            # SE A GEOMETRIA FALHOU (Modo Resgate ou Zero), USA O PADRÃO DO MENU LATERAL
            df["Comp. Unit (m)"] = df["CompIA"].apply(lambda x: x if x > 0.2 else comp_minimo)
            
            st.info(f"Dica: Usando comprimento padrão de {comp_minimo}m onde a geometria não foi detectada.")
            df_ed = st.data_editor(df, num_rows="dynamic", key="dutos_v4")
            
            # Cálculos
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
