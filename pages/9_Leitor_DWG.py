import streamlit as st
import ezdxf
import math
from openai import OpenAI
import pandas as pd
import io
from collections import Counter

# --- 🔒 BLOCO DE SEGURANÇA ---
if 'logado' not in st.session_state or not st.session_state['logado']:
    st.warning("🔒 Acesso negado. Faça login no Dashboard.")
    st.stop()

st.set_page_config(page_title="Leitor DXF (Geométrico)", page_icon="📐", layout="wide")

st.title("📐 Leitor Técnico DXF + Geometria")
st.markdown("""
**Novidade:** O sistema agora tenta medir o **Comprimento Real** das peças.
Ele procura pela *linha mais longa* ou *polilinha* próxima ao texto da etiqueta para definir o tamanho do duto.
""")

# ============================================================================
# 1. CONFIGURAÇÕES (ABNT NBR 16401)
# ============================================================================
with st.sidebar:
    st.header("⚙️ Configurações")
    
    classe_pressao = st.selectbox(
        "Classe de Pressão (ABNT NBR 16401)", 
        ["Classe A (Baixa)", "Classe B (Média)", "Classe C (Alta)", "Classe D (Especial)"]
    )
    
    st.divider()
    st.subheader("📏 Calibração de Medidas")
    st.info("Ajuste isso para melhorar a precisão da leitura geométrica.")
    
    unidade_desenho = st.selectbox("Unidade do Desenho", ["Centímetros (cm)", "Metros (m)", "Milímetros (mm)"])
    
    # Define o raio de busca baseado na unidade
    raio_padrao = 50.0 if unidade_desenho == "Centímetros (cm)" else (0.5 if unidade_desenho == "Metros (m)" else 500.0)
    raio_busca = st.number_input(
        "Raio de Busca Geometria", 
        value=raio_padrao, 
        help="Distância que o robô vai procurar linhas ao redor do texto. Se o duto for largo, aumente isso."
    )
    
    comp_minimo = st.number_input("Comprimento Mínimo (Default)", value=1.0, help="Se o robô não achar nenhuma linha perto, usa esse valor.")
    
    st.divider()
    perda_corte = st.number_input("% Perda / Corte", value=10.0)
    tipo_isolamento = st.selectbox("Isolamento", ["Lã de Vidro", "Borracha Elast.", "Isopor", "Sem Isolamento"])

# ============================================================================
# 2. MOTOR GEOMÉTRICO (EZDXF)
# ============================================================================

def calcular_distancia(p1, p2):
    return math.hypot(p2[0] - p1[0], p2[1] - p1[1])

def obter_comprimento_entidade(entity):
    """Calcula comprimento de Linhas ou Polilinhas"""
    try:
        if entity.dxftype() == 'LINE':
            return calcular_distancia(entity.dxf.start, entity.dxf.end)
        
        elif entity.dxftype() == 'LWPOLYLINE':
            # Soma os segmentos da polilinha
            pts = entity.get_points()
            comprimento = 0
            for i in range(len(pts) - 1):
                comprimento += calcular_distancia(pts[i], pts[i+1])
            # Se for fechada (retângulo), pega o maior lado (assumindo duto retangular)
            if entity.closed:
                # Simplificação: Pega perímetro / 2 ou maior segmento
                # Para duto, geralmente queremos o comprimento do fluxo. 
                # Vamos pegar o maior segmento da polilinha como 'comprimento'
                max_seg = 0
                for i in range(len(pts) - 1):
                    seg = calcular_distancia(pts[i], pts[i+1])
                    if seg > max_seg: max_seg = seg
                return max_seg
            return comprimento
    except:
        return 0

def extrair_dados_com_geometria(bytes_file, raio_search):
    """
    Lê textos E procura geometria próxima para estimar comprimento.
    """
    itens_encontrados = [] # Lista de dicts: {'texto': str, 'comprimento_geo': float}
    
    try:
        # Tenta ler DXF
        try: content = bytes_file.getvalue().decode("cp1252")
        except: content = bytes_file.getvalue().decode("utf-8", errors='ignore')
        
        stream = io.StringIO(content)
        doc = ezdxf.read(stream)
        msp = doc.modelspace()
        
        # 1. Indexar Geometrias (Linhas e Polilinhas) para não ficar lento
        # Como Python é lento, pegamos todas e filtraremos por distancia simples
        linhas = list(msp.query('LINE LWPOLYLINE'))
        
        # 2. Ler Textos
        for e in msp.query('TEXT MTEXT'):
            txt = e.dxf.text if e.dxftype() == 'TEXT' else e.text
            if not txt or len(txt) < 3: continue
            
            # Coordenada do Texto
            insert = e.dxf.insert
            pos_texto = (insert[0], insert[1])
            
            # 3. BUSCA GEOMÉTRICA (A MÁGICA)
            # Procura a linha mais longa dentro do raio de busca
            maior_comprimento_proximo = 0.0
            
            # Otimização: Só checa linhas se tivermos poucas (<5000) ou faz brute-force se necessário.
            # Para Streamlit, vamos limitar a busca às primeiras 2000 linhas próximas para não travar
            # ou usar um filtro simples de coordenadas (bounding box manual)
            
            count_checked = 0
            for geo in linhas:
                # Pega um ponto de referência da geometria
                if geo.dxftype() == 'LINE': ref = geo.dxf.start
                else: ref = geo.get_points()[0]
                
                # Distância rápida
                dist = math.hypot(ref[0] - pos_texto[0], ref[1] - pos_texto[1])
                
                if dist <= raio_search:
                    comp = obter_comprimento_entidade(geo)
                    if comp > maior_comprimento_proximo:
                        maior_comprimento_proximo = comp
                
                count_checked += 1
                if count_checked > 3000: break # Safety break para desenhos gigantes
            
            # Normalização de Unidades para Metros
            comp_final_m = maior_comprimento_proximo
            if unidade_desenho == "Centímetros (cm)": comp_final_m /= 100
            elif unidade_desenho == "Milímetros (mm)": comp_final_m /= 1000
            
            # Se não achou geometria válida, marca como 0 (usará default depois)
            itens_encontrados.append({
                'texto': txt.strip(),
                'geo_m': comp_final_m
            })
            
        return itens_encontrados, "Leitura Geométrico-Espacial"
        
    except Exception as e:
        return [], f"Erro Geometria: {str(e)}"

# ============================================================================
# 3. INTELIGÊNCIA ARTIFICIAL (CLASSIFICAÇÃO)
# ============================================================================
def analisar_com_ia_detalhada(lista_itens):
    if "openai" not in st.secrets: st.error("Erro: Sem chave API"); return None
    
    # Agrupa por texto para mandar pra IA, mas guarda a SOMA das geometrias
    resumo = {}
    for item in lista_itens:
        t = item['texto']
        if t not in resumo: resumo[t] = {'qtd': 0, 'soma_geo': 0.0}
        resumo[t]['qtd'] += 1
        resumo[t]['soma_geo'] += item['geo_m']
    
    # Prepara texto para IA
    texto_prompt = ""
    for k, v in list(resumo.items())[:300]: # Top 300 itens
        media_geo = v['soma_geo'] / v['qtd'] if v['qtd'] > 0 else 0
        texto_prompt += f"TEXTO: '{k}' | QTD: {v['qtd']} | COMPRIMENTO_DETECTADO_MEDIA: {media_geo:.2f}m\n"
    
    client = OpenAI(api_key=st.secrets["openai"]["api_key"])
    
    prompt = """
    Você é um Especialista em Orçamentos HVAC.
    Recebi uma lista de textos do CAD + Comprimento Geométrico Médio detectado pelo robô.
    
    SEU OBJETIVO: Classificar e validar.
    
    REGRAS:
    1. DUTOS: Se for duto (ex: 500x400), use o 'COMPRIMENTO_DETECTADO_MEDIA' como base. 
       - Se a média for muito pequena (< 0.2), ignore e coloque 0 (usaremos padrão).
       - Saída: Largura;Altura;QtdPeças;CompMedioDetectado
    
    2. EQUIPAMENTOS: Procure TR, BTU, HP, CV. 
       - Tente extrair Tensão e Capacidade.
    
    3. TERMINAIS: Grelhas, Difusores.
    
    FORMATO CSV (Ponto e vírgula):
    ---DUTOS---
    Largura;Altura;Qtd;CompMedio
    500;450;2;5.20
    
    ---EQUIPAMENTOS---
    Tag;Tipo;Detalhes;Qtd
    FC-01;Fancoil;5TR 220V;1
    
    ---TERMINAIS---
    Item;Qtd
    Grelha 600x600;10
    
    ---ELETRICA---
    Tag;Descricao;Qtd
    Q-01;Quadro;1
    """
    
    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "system", "content": prompt}, {"role": "user", "content": texto_prompt}],
            temperature=0.0
        )
        return response.choices[0].message.content
    except: return None

def processar_resposta(resposta):
    blocos = {"DUTOS": [], "TERMINAIS": [], "EQUIPAMENTOS": [], "ELETRICA": []}
    atual = None
    for linha in resposta.split('\n'):
        linha = linha.strip()
        if "---DUTOS---" in linha: atual = "DUTOS"; continue
        if "---TERMINAIS---" in linha: atual = "TERMINAIS"; continue
        if "---EQUIPAMENTOS---" in linha: atual = "EQUIPAMENTOS"; continue
        if "---ELETRICA---" in linha: atual = "ELETRICA"; continue
        
        if atual and linha and ";" in linha and "Largura" not in linha and "Tag" not in linha:
            blocos[atual].append(linha.split(';'))
    return blocos

# ============================================================================
# 4. INTERFACE
# ============================================================================
uploaded_dxf = st.file_uploader("📂 Carregar DXF (Salvar como ASCII 2010)", type=["dxf"])

if uploaded_dxf:
    with st.spinner("🕵️‍♀️ O Robô está medindo linhas próximas aos textos..."):
        itens_brutos, msg = extrair_dados_com_geometria(uploaded_dxf, raio_busca)
        
    if itens_brutos:
        st.success(f"✅ {len(itens_brutos)} itens analisados espacialmente.")
        
        if st.button("🚀 Processar Inteligência (IA)", type="primary"):
            with st.spinner("Classificando e consolidando medidas..."):
                res_ia = analisar_com_ia_detalhada(itens_brutos)
                if res_ia:
                    st.session_state['dados_geo'] = processar_resposta(res_ia)
                    st.rerun()

# ============================================================================
# 5. RESULTADOS
# ============================================================================
if 'dados_geo' in st.session_state:
    dados = st.session_state['dados_geo']
    
    tab1, tab2, tab3, tab4 = st.tabs(["🌪️ Dutos (Medição)", "💨 Terminais", "⚙️ Equipamentos", "⚡ Elétrica"])
    
    with tab1:
        st.markdown("### 📏 Memória de Cálculo (Automática)")
        lista = dados["DUTOS"]
        if lista:
            # Cria DF
            try: df = pd.DataFrame(lista, columns=["Largura", "Altura", "Qtd", "Comp. Médio (IA)"])
            except: df = pd.DataFrame(lista)
            
            # Converte números
            cols_num = ["Largura", "Altura", "Qtd", "Comp. Médio (IA)"]
            for c in cols_num: 
                if c in df.columns: df[c] = pd.to_numeric(df[c], errors='coerce').fillna(0)
            
            # LÓGICA DE DECISÃO: GEOMETRIA OU PADRÃO?
            # Se a IA detectou um comprimento geométrico útil (>0.2m), usa ele.
            # Se não (zero), usa o comprimento mínimo configurado no menu.
            df["Comp. Unitário Final (m)"] = df["Comp. Médio (IA)"].apply(lambda x: x if x > 0.2 else comp_minimo)
            
            # Tabela Editável
            st.caption("A coluna 'Comp. Unitário' foi preenchida automaticamente pela geometria do desenho. Você pode ajustar.")
            df_edit = st.data_editor(df, num_rows="dynamic", key="dutos_geo")
            
            # CÁLCULOS FINAIS
            df_calc = df_edit.copy()
            df_calc["Perímetro (m)"] = (2*df_calc["Largura"] + 2*df_calc["Altura"]) / 1000
            df_calc["Comp. Total Linha (m)"] = df_calc["Qtd"] * df_calc["Comp. Unitário Final (m)"]
            df_calc["Área (m²)"] = df_calc["Perímetro (m)"] * df_calc["Comp. Total Linha (m)"]
            
            fator = 1 + (perda_corte/100)
            area_total = (df_calc["Área (m²)"] * fator).sum()
            peso = area_total * 5.6
            
            # Exibição
            c1, c2, c3 = st.columns(3)
            c1.metric("Área Total (+Perda)", f"{area_total:,.2f} m²")
            c2.metric("Peso Estimado", f"{peso:,.0f} kg")
            c3.metric("Isolamento", f"{area_total:,.2f} m²" if tipo_isolamento != "Sem Isolamento" else "-")
            
            st.dataframe(df_calc[["Largura", "Altura", "Qtd", "Comp. Unitário Final (m)", "Comp. Total Linha (m)", "Área (m²)"]])
        else:
            st.warning("Nenhum duto identificado.")

    with tab2:
        if dados["TERMINAIS"]: st.data_editor(pd.DataFrame(dados["TERMINAIS"], columns=["Item", "Qtd"]), num_rows="dynamic")
        else: st.info("Vazio")

    with tab3:
        if dados["EQUIPAMENTOS"]:
            st.data_editor(pd.DataFrame(dados["EQUIPAMENTOS"], columns=["Tag", "Tipo", "Detalhes", "Qtd"]), num_rows="dynamic")
        else: st.info("Vazio")
        
    with tab4:
        if dados["ELETRICA"]: st.data_editor(pd.DataFrame(dados["ELETRICA"], columns=["Tag", "Desc", "Qtd"]), num_rows="dynamic")
        else: st.info("Vazio")
