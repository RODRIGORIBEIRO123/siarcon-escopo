import streamlit as st
import ezdxf
import math
from openai import OpenAI
import pandas as pd
import io
from collections import Counter
import time

# --- 🔒 BLOCO DE SEGURANÇA ---
if 'logado' not in st.session_state or not st.session_state['logado']:
    st.warning("🔒 Acesso negado. Faça login no Dashboard.")
    st.stop()

st.set_page_config(page_title="Leitor DXF (Geométrico)", page_icon="📐", layout="wide")

st.title("📐 Leitor Técnico DXF + Geometria (Heavy Duty)")
st.markdown("""
**Instrução para arquivos pesados (>10MB):** O sistema analisa textos e geometrias. 
Se o arquivo for muito grande, a análise será limitada aos primeiros 3.000 itens para evitar travamento.
""")

# ============================================================================
# 1. CONFIGURAÇÕES
# ============================================================================
with st.sidebar:
    st.header("⚙️ Configurações")
    classe_pressao = st.selectbox(
        "Classe de Pressão", 
        ["Classe A (Baixa)", "Classe B (Média)", "Classe C (Alta)", "Classe D (Especial)"]
    )
    
    st.divider()
    st.subheader("📏 Calibração")
    unidade_desenho = st.selectbox(
        "Unidade do Desenho", 
        ["Centímetros (cm)", "Metros (m)", "Milímetros (mm)"]
    )
    
    # Define raio padrão baseado na unidade
    if unidade_desenho == "Centímetros (cm)":
        raio_padrao = 50.0
    elif unidade_desenho == "Metros (m)":
        raio_padrao = 0.5
    else:
        raio_padrao = 500.0

    raio_busca = st.number_input(
        "Raio de Busca (Geometria)", 
        value=raio_padrao, 
        help="Distância para procurar linhas ao redor do texto."
    )
    comp_minimo = st.number_input("Comprimento Mínimo (m)", value=1.0)
    
    st.divider()
    perda_corte = st.number_input("% Perda / Corte", value=10.0)
    tipo_isolamento = st.selectbox(
        "Isolamento", 
        ["Lã de Vidro", "Borracha Elast.", "Isopor", "Sem Isolamento"]
    )

# ============================================================================
# 2. MOTOR GEOMÉTRICO OTIMIZADO
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
                # Se for retângulo, pega o maior lado
                max_seg = 0
                for i in range(len(pts) - 1):
                    s = calcular_distancia(pts[i], pts[i+1])
                    if s > max_seg: 
                        max_seg = s
                return max_seg
            else: 
                # Soma segmentos
                comp = 0
                for i in range(len(pts) - 1): 
                    comp += calcular_distancia(pts[i], pts[i+1])
                return comp
    except: 
        return 0
    return 0

def extrair_dados_com_geometria(bytes_file, raio_search):
    itens_encontrados = []
    log_erro = "Sucesso"
    
    try:
        # Tenta decodificar
        try: 
            content = bytes_file.getvalue().decode("cp1252")
        except: 
            try: 
                content = bytes_file.getvalue().decode("utf-8", errors='ignore')
            except: 
                return [], "Erro Fatal de Codificação (Arquivo Binário?)"

        stream = io.StringIO(content)
        doc = ezdxf.read(stream)
        msp = doc.modelspace()
        
        # OTIMIZAÇÃO: Carrega geometria apenas se necessário e limita quantidade
        geometrias = []
        # Pega no máximo 5000 linhas para não estourar memória
        for i, e in enumerate(msp.query('LINE LWPOLYLINE')):
            if i > 5000: 
                break 
            geometrias.append(e)
            
        if not geometrias:
            log_erro = "Aviso: Nenhuma linha/polilinha encontrada. Modo somente texto."

        # Barra de progresso para o usuário ver
        progresso = st.progress(0, text="Lendo textos...")
        
        textos = list(msp.query('TEXT MTEXT'))
        total_textos = len(textos)
        
        if total_textos == 0:
            return [], "Nenhum objeto de texto (TEXT/MTEXT) encontrado no DXF."

        # LIMITADOR DE SEGURANÇA
        limite_analise = 3000
        if total_textos > limite_analise:
            st.toast(f"⚠️ Arquivo gigante! Analisando apenas os primeiros {limite_analise} textos.", icon="⚠️")
            textos = textos[:limite_analise]

        for idx, e in enumerate(textos):
            # Atualiza barra a cada 100 itens
            if idx % 100 == 0: 
                progresso.progress(int((idx / len(textos)) * 100), text=f"Medindo item {idx}/{len(textos)}...")

            txt = e.dxf.text if e.dxftype() == 'TEXT' else e.text
            if not txt or len(txt) < 3: 
                continue
            
            # Coordenada
            try:
                insert = e.dxf.insert
                pos = (insert[0], insert[1])
            except: 
                continue
            
            # Busca geométrica local
            maior_comp = 0.0
            
            # Só busca geometria se tivermos geometrias carregadas
            if geometrias:
                count_check = 0
                for geo in geometrias:
                    # Otimização extrema: Check rápido de distância Manhattan antes de Pitágoras
                    try:
                        if geo.dxftype() == 'LINE': 
                            ref = geo.dxf.start
                        else: 
                            ref = geo.get_points()[0]
                        
                        if abs(ref[0] - pos[0]) > raio_search * 2: continue
                        if abs(ref[1] - pos[1]) > raio_search * 2: continue

                        dist = math.hypot(ref[0] - pos[0], ref[1] - pos[1])
                        if dist <= raio_search:
                            c = obter_comprimento_entidade(geo)
                            if c > maior_comp: 
                                maior_comp = c
                    except: 
                        pass
                    
                    count_check += 1
                    if count_check > 500: break # Safety break
            
            # Normaliza unidade
            comp_final = maior_comp
            if unidade_desenho == "Centímetros (cm)": 
                comp_final /= 100
            elif unidade_desenho == "Milímetros (mm)": 
                comp_final /= 1000
            
            itens_encontrados.append({'texto': txt.strip(), 'geo_m': comp_final})
            
        progresso.empty()
        return itens_encontrados, log_erro

    except Exception as e:
        return [], f"Erro no processamento: {str(e)}"

# ============================================================================
# 3. INTELIGÊNCIA ARTIFICIAL
# ============================================================================
def analisar_com_ia_detalhada(lista_itens):
    if "openai" not in st.secrets: 
        st.error("Sem chave API")
        return None
    
    # Agrupa
    resumo = {}
    for item in lista_itens:
        t = item['texto']
        if t not in resumo: 
            resumo[t] = {'qtd': 0, 'soma': 0.0}
        resumo[t]['qtd'] += 1
        resumo[t]['soma'] += item['geo_m']
        
    txt_prompt = ""
    # Pega os 300 mais frequentes
    for k, v in sorted(resumo.items(), key=lambda x: x[1]['qtd'], reverse=True)[:300]:
        med = v['soma'] / v['qtd'] if v['qtd'] > 0 else 0
        txt_prompt += f"TXT:'{k}'|Q:{v['qtd']}|MED:{med:.2f}m\n"
        
    client = OpenAI(api_key=st.secrets["openai"]["api_key"])
    
    prompt = """
    Engenheiro HVAC Sênior. Classifique os itens recebidos (Texto do CAD + Qtd + Comprimento Médio Detectado).
    
    REGRAS:
    1. DUTOS: Dimensões (AxL, ø). Use 'MED' como comprimento se > 0.2, senão 0.
    2. EQUIPAMENTOS: Fancoil, Split, Chiller. Extraia TR/BTU/HP se houver.
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
            messages=[
                {"role":"system","content":prompt},
                {"role":"user","content":txt_prompt}
            ], 
            temperature=0.0
        )
        return r.choices[0].message.content
    except Exception as e: 
        st.error(e)
        return None

def processar_resposta(r):
    blocos = {"DUTOS":[],"TERMINAIS":[],"EQUIPAMENTOS":[],"ELETRICA":[]}
    atual = None
    for l in r.split('\n'):
        l = l.strip()
        if "---DUTOS" in l: 
            atual="DUTOS"
            continue
        if "---TERM" in l: 
            atual="TERMINAIS"
            continue
        if "---EQUI" in l: 
            atual="EQUIPAMENTOS"
            continue
        if "---ELET" in l: 
            atual="ELETRICA"
            continue
        
        if atual and ";" in l and "Largura" not in l and "Tag" not in l: 
            blocos[atual].append(l.split(';'))
    return blocos

# ============================================================================
# 4. INTERFACE
# ============================================================================
uploaded_dxf = st.file_uploader("📂 Carregar DXF (>10MB? Salve como R12/2010 ASCII)", type=["dxf"])

if uploaded_dxf:
    # 1. TENTA LER O ARQUIVO
    with st.spinner("Lendo arquivo e geometrias (Isso pode demorar um pouco)..."):
        itens_brutos, msg_status = extrair_dados_com_geometria(uploaded_dxf, raio_busca)

    # 2. SE ACHOU ITENS, MOSTRA BOTÃO DE PROCESSAR
    if itens_brutos:
        st.success(f"✅ Arquivo Lido! {len(itens_brutos)} textos analisados. ({msg_status})")
        
        if st.button("🚀 Extrair Quantitativo (IA)", type="primary"):
            with st.spinner("Classificando itens..."):
                res = analisar_com_ia_detalhada(itens_brutos)
                if res:
                    st.session_state['dados_geo_v2'] = processar_resposta(res)
                    st.rerun()
    
    # 3. SE NÃO ACHOU NADA, MOSTRA O ERRO
    else:
        st.error(f"❌ Não foi possível extrair dados.")
        st.warning(f"Detalhe do erro: {msg_status}")
        st.info("Dica: Se o arquivo for muito grande, tente apagar as plantas de arquitetura no AutoCAD e deixar apenas o HVAC antes de salvar.")

# ============================================================================
# 5. RESULTADOS
# ============================================================================
if 'dados_geo_v2' in st.session_state:
    d = st.session_state['dados_geo_v2']
    t1, t2, t3, t4 = st.tabs(["🌪️ Dutos","💨 Terminais","⚙️ Equips","⚡ Elétrica"])
    
    with t1:
        if d["DUTOS"]:
            df = pd.DataFrame(d["DUTOS"], columns=["Largura","Altura","Qtd","CompIA"])
            for c in df.columns: 
                df[c] = pd.to_numeric(df[c], errors='coerce').fillna(0)
            
            # Lógica: Se IA achou comprimento > 0.2, usa. Senão usa Mínimo.
            df["Comp. Unit (m)"] = df["CompIA"].apply(lambda x: x if x > 0.2 else comp_minimo)
            
            st.caption("Ajuste a coluna 'Comp. Unit (m)' se necessário.")
            df_ed = st.data_editor(df, num_rows="dynamic", key="dutos_v3")
            
            # Cálculos
            df_ed["Perímetro"] = (2*df_ed["Largura"] + 2*df_ed["Altura"])/1000
            df_ed["Total (m)"] = df_ed["Qtd"] * df_ed["Comp. Unit (m)"]
            df_ed["Área (m²)"] = df_ed["Perímetro"] * df_ed["Total (m)"]
            
            fator = 1 + (perda_corte/100)
            area = (df_ed["Área (m²)"] * fator).sum()
            
            c1, c2, c3 = st.columns(3)
            c1.metric("Área Total", f"{area:,.2f} m²")
            c2.metric("Peso (~5.6kg/m²)", f"{area*5.6:,.0f} kg")
            
            if tipo_isolamento != "Sem Isolamento":
                isol = f"{area:,.2f} m²"
            else:
                isol = "-"
            c3.metric("Isolamento", isol)
            
            st.dataframe(df_ed)
        else: 
            st.warning("Nenhum duto encontrado.")

    with t2:
        if d["TERMINAIS"]: 
            st.data_editor(pd.DataFrame(d["TERMINAIS"], columns=["Item","Qtd"]), num_rows="dynamic")
        else: 
            st.info("Vazio")

    with t3:
        if d["EQUIPAMENTOS"]: 
            st.data_editor(pd.DataFrame(d["EQUIPAMENTOS"], columns=["Tag","Tipo","Detalhe","Qtd"]), num_rows="dynamic")
        else: 
            st.info("Vazio")

    with t4:
        if d["ELETRICA"]: 
            st.data_editor(pd.DataFrame(d["ELETRICA"], columns=["Tag","Desc","Qtd"]), num_rows="dynamic")
        else: 
            st.info("Vazio")
