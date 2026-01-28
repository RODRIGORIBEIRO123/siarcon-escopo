import streamlit as st
import ezdxf
from openai import OpenAI
import pandas as pd
import io
import re

# --- 🔒 BLOCO DE SEGURANÇA ---
if 'logado' not in st.session_state or not st.session_state['logado']:
    st.warning("🔒 Acesso negado. Faça login no Dashboard.")
    st.stop()

st.set_page_config(page_title="Leitor DXF Avançado", page_icon="📐", layout="wide")

st.title("📐 Leitor Técnico de Projetos (DXF)")
st.markdown("""
Esta ferramenta extrai textos e blocos do DXF para gerar listas de materiais.
**Como funciona:**
1. A IA identifica as **Bitolas de Dutos**, **Equipamentos** e **Grelhas**.
2. Você confirma as quantidades/metragens na tabela interativa.
3. O sistema calcula a **Área de Isolamento** automaticamente.
""")

# ============================================================================
# 1. CONFIGURAÇÕES (VOLTARAM!)
# ============================================================================
with st.sidebar:
    st.header("⚙️ Configurações de Cálculo")
    classe_pressao = st.selectbox("Classe de Pressão (SMACNA)", ["Baixa (até 50mmca)", "Média (até 100mmca)", "Alta (até 150mmca)"])
    perda_corte = st.number_input("% Perda / Corte (Chapas)", min_value=0.0, max_value=20.0, value=10.0, step=1.0)
    tipo_isolamento = st.selectbox("Isolamento", ["Lã de Vidro", "Borracha Elast.", "Sem Isolamento"])

# ============================================================================
# 2. FUNÇÕES DE EXTRAÇÃO
# ============================================================================
def extrair_textos_dxf(dxf_file):
    try:
        doc = ezdxf.read(dxf_file)
        msp = doc.modelspace()
        textos = []
        # Extrai TEXT e MTEXT
        for e in msp.query('TEXT MTEXT'):
            txt = e.dxf.text if e.dxftype() == 'TEXT' else e.text
            if txt and len(txt) > 2: # Ignora textos muito curtos
                textos.append(txt.strip())
        return textos
    except Exception as e:
        st.error(f"Erro ao ler DXF: {e}")
        return []

def analisar_com_ia_categorizado(lista_textos):
    if "openai" not in st.secrets:
        st.error("🚨 Chave OpenAI não configurada."); return None
    
    client = OpenAI(api_key=st.secrets["openai"]["api_key"])
    texto_bruto = "\n".join(lista_textos[:4000]) # Limite para não estourar tokens
    
    prompt = """
    Você é um Engenheiro de Orçamentos MEP. Analise a lista de textos extraída de um DWG/DXF.
    
    SEU OBJETIVO: Separar e estruturar os dados em 4 categorias (CSV separado por ponto e vírgula).
    
    CATEGORIAS A BUSCAR:
    1. DUTOS: Procure dimensões (ex: 300x200, 500x400, ø200). Ignore textos de arquitetura.
    2. GRELHAS/DIFUSORES: Procure códigos (ex: G-01, D-02, Boca de Lobo, Veneziana).
    3. EQUIPAMENTOS: Procure Fancoil, Chiller, Split, VRF, K7, com suas capacidades (TR, HP, BTU).
    4. ELETRICA/AUTOMAÇÃO: Procure Quadros (QGBT, QF), Painéis, Sensores.

    SAÍDA OBRIGATÓRIA (Apenas este formato, sem introdução):
    
    ---DUTOS---
    Largura;Altura;Tipo(Rect/Circ)
    300;200;Rect
    500;400;Rect
    
    ---TERMINAIS---
    Item;Quantidade Estimada (Pela contagem de tags)
    Grelha Retorno 600x600;4
    Difusor Linear;10
    
    ---EQUIPAMENTOS---
    Tag;Descrição;Detalhes (Capacidade/Tensão)
    FC-01;Fancoil Duto;5TR 220V
    SPL-02;Split Hiwall;12000 BTU
    
    ---ELETRICA---
    Tag;Descrição
    Q-01;Quadro de Força
    DDC-01;Painel Automação
    """
    
    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": f"Analise estes textos do CAD:\n{texto_bruto}"}
            ],
            temperature=0.1
        )
        return response.choices[0].message.content
    except Exception as e:
        st.error(f"Erro na IA: {e}")
        return None

def processar_resposta_ia(resposta):
    # Separa os blocos da resposta
    blocos = {"DUTOS": [], "TERMINAIS": [], "EQUIPAMENTOS": [], "ELETRICA": []}
    atual = None
    
    for linha in resposta.split('\n'):
        linha = linha.strip()
        if "---DUTOS---" in linha: atual = "DUTOS"; continue
        if "---TERMINAIS---" in linha: atual = "TERMINAIS"; continue
        if "---EQUIPAMENTOS---" in linha: atual = "EQUIPAMENTOS"; continue
        if "---ELETRICA---" in linha: atual = "ELETRICA"; continue
        
        if atual and linha and ";" in linha and "Largura" not in linha and "Item" not in linha and "Tag" not in linha:
            blocos[atual].append(linha.split(';'))
            
    return blocos

# ============================================================================
# 3. INTERFACE PRINCIPAL
# ============================================================================
uploaded_dxf = st.file_uploader("📂 Carregar Arquivo .DXF", type=["dxf"])

if uploaded_dxf:
    with st.spinner("Lendo arquivo DXF..."):
        try:
            content = uploaded_dxf.getvalue().decode("cp1252", errors="ignore")
            stream = io.StringIO(content)
            lista_textos = extrair_textos_dxf(stream)
            st.success(f"{len(lista_textos)} textos extraídos com sucesso!")
        except Exception as e:
            st.error("Erro ao decodificar arquivo. Tente salvar o DXF em versão mais antiga (2010).")
            lista_textos = []

    if lista_textos:
        if st.button("🚀 Analisar e Extrair Dados", type="primary"):
            with st.spinner("A IA está categorizando os itens..."):
                resultado_ia = analisar_com_ia_categorizado(lista_textos)
                
                if resultado_ia:
                    dados_processados = processar_resposta_ia(resultado_ia)
                    st.session_state['dados_dxf'] = dados_processados
                    st.rerun()

# ============================================================================
# 4. EXIBIÇÃO DOS RESULTADOS (ABAS)
# ============================================================================
if 'dados_dxf' in st.session_state:
    dados = st.session_state['dados_dxf']
    
    tab_dutos, tab_term, tab_equip, tab_elet = st.tabs([
        "🌪️ Rede de Dutos (Cálculo)", 
        "💨 Grelhas e Difusores", 
        "⚙️ Equipamentos", 
        "⚡ Elétrica/Automação"
    ])
    
    # --- ABA 1: DUTOS (CÁLCULO AUTOMÁTICO) ---
    with tab_dutos:
        st.info("A IA identificou as bitolas abaixo. Insira o COMPRIMENTO TOTAL (m) para calcular a área.")
        
        # Prepara DataFrame para edição
        lista_dutos = dados["DUTOS"]
        if lista_dutos:
            df_dutos = pd.DataFrame(lista_dutos, columns=["Largura (mm)", "Altura (mm)", "Tipo"])
            # Adiciona coluna de comprimento para o usuário preencher (padrão 0)
            df_dutos["Comprimento Total (m)"] = 0.0
            
            # Tabela Editável
            df_editado = st.data_editor(df_dutos, num_rows="dynamic", key="editor_dutos")
            
            # --- CÁLCULOS MATEMÁTICOS ---
            st.divider()
            st.subheader("📊 Resultados Calculados")
            
            # Converte para float para calcular
            try:
                df_calc = df_editado.copy()
                df_calc["Largura (mm)"] = pd.to_numeric(df_calc["Largura (mm)"], errors='coerce').fillna(0)
                df_calc["Altura (mm)"] = pd.to_numeric(df_calc["Altura (mm)"], errors='coerce').fillna(0)
                
                # Cálculo do Perímetro (m) = (2*L + 2*A) / 1000
                df_calc["Perímetro (m)"] = (2 * df_calc["Largura (mm)"] + 2 * df_calc["Altura (mm)"]) / 1000
                
                # Cálculo da Área (m²) = Perímetro * Comprimento
                df_calc["Área Duto (m²)"] = df_calc["Perímetro (m)"] * df_calc["Comprimento Total (m)"]
                
                # Adiciona Perda
                fator_perda = 1 + (perda_corte / 100)
                df_calc["Área c/ Perda (m²)"] = df_calc["Área Duto (m²)"] * fator_perda
                
                # Totais
                area_total = df_calc["Área c/ Perda (m²)"].sum()
                
                # Exibição
                c1, c2, c3 = st.columns(3)
                c1.metric("Área Total de Chapa (m²)", f"{area_total:,.2f}")
                
                if tipo_isolamento != "Sem Isolamento":
                    c2.metric(f"Área Isolamento ({tipo_isolamento})", f"{area_total:,.2f} m²")
                
                c3.metric("Classe Pressão Selecionada", classe_pressao)
                
                st.dataframe(df_calc[["Largura (mm)", "Altura (mm)", "Comprimento Total (m)", "Área c/ Perda (m²)"]])
                
            except Exception as e:
                st.warning("Preencha os comprimentos para ver o cálculo.")
        else:
            st.warning("Nenhuma bitola de duto identificada automaticamente.")

    # --- ABA 2: TERMINAIS ---
    with tab_term:
        st.subheader("Lista de Grelhas, Difusores e Venezianas")
        if dados["TERMINAIS"]:
            df_term = pd.DataFrame(dados["TERMINAIS"], columns=["Descrição", "Qtd Estimada (Tags)"])
            st.data_editor(df_term, num_rows="dynamic")
        else:
            st.info("Nenhum terminal identificado.")

    # --- ABA 3: EQUIPAMENTOS ---
    with tab_equip:
        st.subheader("Lista de Equipamentos (HVAC)")
        if dados["EQUIPAMENTOS"]:
            df_equip = pd.DataFrame(dados["EQUIPAMENTOS"], columns=["Tag", "Modelo/Tipo", "Detalhes"])
            st.data_editor(df_equip, num_rows="dynamic")
        else:
            st.info("Nenhum equipamento identificado.")

    # --- ABA 4: ELÉTRICA ---
    with tab_elet:
        st.subheader("Painéis Elétricos e Automação")
        if dados["ELETRICA"]:
            df_elet = pd.DataFrame(dados["ELETRICA"], columns=["Tag", "Descrição"])
            st.data_editor(df_elet, num_rows="dynamic")
        else:
            st.info("Nenhum item elétrico identificado.")
