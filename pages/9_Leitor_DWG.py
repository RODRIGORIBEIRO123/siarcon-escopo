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

st.set_page_config(page_title="Leitor DXF (ABNT)", page_icon="📐", layout="wide")

st.title("📐 Leitor Técnico (DXF) - ABNT NBR 16401")
st.markdown("""
**Instrução Importante:** Para evitar erros, no AutoCAD, vá em *Save As* e escolha **AutoCAD 2010 DXF**.
Se o arquivo for muito pesado ou binário, o sistema tentará o "Modo de Leitura Forçada".
""")

# ============================================================================
# 1. CONFIGURAÇÕES (ABNT NBR 16401)
# ============================================================================
with st.sidebar:
    st.header("⚙️ Configurações (ABNT)")
    
    # NBR 16401 define estanqueidade por classes de pressão
    classe_pressao = st.selectbox(
        "Classe de Pressão (ABNT NBR 16401)", 
        [
            "Classe A (Baixa Pressão - até 500 Pa)", 
            "Classe B (Média Pressão - até 1000 Pa)", 
            "Classe C (Alta Pressão - até 2000 Pa)",
            "Classe D (Muito Alta - Especial)"
        ]
    )
    
    st.info(f"Selecionado: {classe_pressao}")
    
    perda_corte = st.number_input("% Perda / Corte (Chapas)", min_value=0.0, max_value=20.0, value=10.0, step=1.0)
    tipo_isolamento = st.selectbox("Isolamento", ["Lã de Vidro", "Borracha Elast.", "Poliestireno (Isopor)", "Sem Isolamento"])

# ============================================================================
# 2. FUNÇÕES DE EXTRAÇÃO BLINDADAS
# ============================================================================
def ler_dxf_bruto(conteudo_str):
    """
    Função 'MacGyver': Se o ezdxf falhar, lê o arquivo linha por linha
    procurando padrões de texto. Menos elegante, mas funciona sempre.
    """
    textos = []
    # No formato DXF ASCII, o código de grupo 1 indica texto primário
    # O padrão é:
    # 1
    # CONTEUDO DO TEXTO
    linhas = conteudo_str.split('\n')
    for i, linha in enumerate(linhas):
        linha = linha.strip()
        # Se acharmos um código de texto, pegamos a próxima linha
        if linha == '1' and i + 1 < len(linhas):
            texto_provavel = linhas[i+1].strip()
            # Filtra lixo e pega só o que parece texto útil
            if len(texto_provavel) > 2 and not texto_provavel.startswith('{'):
                textos.append(texto_provavel)
    return textos

def extrair_textos_dxf(bytes_file):
    textos = []
    sucesso_metodo = ""
    
    # Tenta decodificar o arquivo (Windows 1252 é padrão AutoCAD Brasil, ou UTF-8)
    try:
        content_str = bytes_file.getvalue().decode("cp1252")
    except:
        try:
            content_str = bytes_file.getvalue().decode("utf-8", errors='ignore')
        except:
            return [], "Erro fatal de codificação"

    # TENTATIVA 1: Biblioteca Oficial (EZDXF)
    try:
        stream = io.StringIO(content_str)
        doc = ezdxf.read(stream)
        msp = doc.modelspace()
        for e in msp.query('TEXT MTEXT'):
            txt = e.dxf.text if e.dxftype() == 'TEXT' else e.text
            if txt and len(txt) > 2:
                textos.append(txt.strip())
        sucesso_metodo = "Leitura Padrão (Precisa)"
    except:
        # TENTATIVA 2: Modo Bruto (Fallback)
        # Se a biblioteca falhar (erro binário), usamos o leitor de texto bruto
        textos = ler_dxf_bruto(content_str)
        sucesso_metodo = "Leitura Forçada (Fallback)"
    
    return textos, sucesso_metodo

def analisar_com_ia_categorizado(lista_textos):
    if "openai" not in st.secrets:
        st.error("🚨 Chave OpenAI não configurada."); return None
    
    client = OpenAI(api_key=st.secrets["openai"]["api_key"])
    
    # Pega uma amostra maior para garantir
    texto_bruto = "\n".join(lista_textos[:4500]) 
    
    prompt = """
    Você é um Engenheiro de Orçamentos MEP Sênior.
    Analise a lista de textos (OCR/DXF) de um projeto de AVAC.
    
    SEU OBJETIVO: Filtrar e estruturar os dados em 4 categorias CSV (;).
    
    1. DUTOS: Procure dimensões (ex: 300x200, 500x400, ø200, 20x20). 
       - Ignore cotas de parede (ex: 15, 2.80). foque em pares AxL.
    2. TERMINAIS: Procure Grelhas, Difusores, Venezianas, Dampers (ex: G-01, VZ-02).
    3. EQUIPAMENTOS: Procure Fancoil, Chiller, Split, VRF, K7, Exaustor.
       - Tente capturar a capacidade (TR, BTU) e Tensão.
    4. ELETRICA/AUTOMAÇÃO: Quadros, Sensores, Termostatos.

    SAÍDA OBRIGATÓRIA (Use exatamente este formato):
    
    ---DUTOS---
    Largura;Altura;Tipo(Rect/Circ)
    300;200;Rect
    
    ---TERMINAIS---
    Item;Qtd (Conte as tags)
    Grelha Retorno 600x600;4
    
    ---EQUIPAMENTOS---
    Tag;Tipo;Detalhes
    FC-01;Fancoil;5TR
    
    ---ELETRICA---
    Tag;Descrição
    Q-01;Quadro
    """
    
    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": f"Analise estes textos brutos:\n{texto_bruto}"}
            ],
            temperature=0.1
        )
        return response.choices[0].message.content
    except Exception as e:
        st.error(f"Erro na IA: {e}")
        return None

def processar_resposta_ia(resposta):
    blocos = {"DUTOS": [], "TERMINAIS": [], "EQUIPAMENTOS": [], "ELETRICA": []}
    atual = None
    for linha in resposta.split('\n'):
        linha = linha.strip()
        if "---DUTOS---" in linha: atual = "DUTOS"; continue
        if "---TERMINAIS---" in linha: atual = "TERMINAIS"; continue
        if "---EQUIPAMENTOS---" in linha: atual = "EQUIPAMENTOS"; continue
        if "---ELETRICA---" in linha: atual = "ELETRICA"; continue
        
        if atual and linha and ";" in linha and "Largura" not in linha and "Item" not in linha:
            blocos[atual].append(linha.split(';'))
    return blocos

# ============================================================================
# 3. INTERFACE PRINCIPAL
# ============================================================================
uploaded_dxf = st.file_uploader("📂 Carregar Arquivo .DXF (Salve como ASCII 2010)", type=["dxf"])

if uploaded_dxf:
    with st.spinner("Decodificando arquivo..."):
        lista_textos, metodo = extrair_textos_dxf(uploaded_dxf)
        
    if lista_textos:
        st.success(f"✅ {len(lista_textos)} textos extraídos via {metodo}!")
        
        if st.button("🚀 Processar com IA", type="primary"):
            with st.spinner("Classificando itens de engenharia..."):
                resultado_ia = analisar_com_ia_categorizado(lista_textos)
                if resultado_ia:
                    st.session_state['dados_dxf'] = processar_resposta_ia(resultado_ia)
                    st.rerun()
    else:
        st.error("❌ Não foi possível ler textos. O arquivo pode ser uma imagem (Scan) ou estar corrompido.")

# ============================================================================
# 4. EXIBIÇÃO E CÁLCULOS
# ============================================================================
if 'dados_dxf' in st.session_state:
    dados = st.session_state['dados_dxf']
    
    tab_dutos, tab_term, tab_equip, tab_elet = st.tabs([
        "🌪️ Rede de Dutos (ABNT 16401)", 
        "💨 Terminais de Ar", 
        "⚙️ Equipamentos", 
        "⚡ Elétrica"
    ])
    
    # --- ABA DUTOS ---
    with tab_dutos:
        st.info("Insira o COMPRIMENTO TOTAL (m) para calcular a área conforme ABNT NBR 16401.")
        
        lista_dutos = dados["DUTOS"]
        if lista_dutos:
            df_dutos = pd.DataFrame(lista_dutos, columns=["Largura (mm)", "Altura (mm)", "Tipo"])
            df_dutos["Comprimento Total (m)"] = 0.0
            
            df_editado = st.data_editor(df_dutos, num_rows="dynamic", key="editor_dutos_abnt")
            
            st.divider()
            st.subheader("📊 Memória de Cálculo")
            
            try:
                # Tratamento de dados
                df_calc = df_editado.copy()
                for col in ["Largura (mm)", "Altura (mm)", "Comprimento Total (m)"]:
                    df_calc[col] = pd.to_numeric(df_calc[col], errors='coerce').fillna(0)
                
                # Fórmulas
                # Perímetro retangular (m) = (2L + 2A)/1000
                # Se for circular, a IA costuma mandar Diâmetro na largura. P = (pi * D)/1000
                # Aqui simplificamos assumindo retangular ou maior dimensão.
                
                df_calc["Perímetro (m)"] = (2 * df_calc["Largura (mm)"] + 2 * df_calc["Altura (mm)"]) / 1000
                df_calc["Área Física (m²)"] = df_calc["Perímetro (m)"] * df_calc["Comprimento Total (m)"]
                
                fator_perda = 1 + (perda_corte / 100)
                df_calc["Área Total (m²)"] = df_calc["Área Física (m²)"] * fator_perda
                
                area_total = df_calc["Área Total (m²)"].sum()
                
                # KPIs
                c1, c2, c3 = st.columns(3)
                c1.metric("Área Chapa (c/ Perda)", f"{area_total:,.2f} m²")
                
                msg_isol = f"{area_total:,.2f} m²" if tipo_isolamento != "Sem Isolamento" else "---"
                c2.metric(f"Isolamento ({tipo_isolamento})", msg_isol)
                
                c3.metric("Norma Aplicada", "NBR 16401", delta=classe_pressao)
                
                st.write("Detalhamento:")
                st.dataframe(df_calc)
                
            except Exception as e:
                st.error(f"Erro no cálculo: {e}")
        else:
            st.warning("Nenhum duto identificado automaticamente.")

    # --- OUTRAS ABAS (Mantidas simples) ---
    with tab_term:
        if dados["TERMINAIS"]:
            st.data_editor(pd.DataFrame(dados["TERMINAIS"], columns=["Item", "Qtd"]), num_rows="dynamic")
        else: st.info("Vazio")

    with tab_equip:
        if dados["EQUIPAMENTOS"]:
            st.data_editor(pd.DataFrame(dados["EQUIPAMENTOS"], columns=["Tag", "Tipo", "Detalhes"]), num_rows="dynamic")
        else: st.info("Vazio")

    with tab_elet:
        if dados["ELETRICA"]:
            st.data_editor(pd.DataFrame(dados["ELETRICA"], columns=["Tag", "Descrição"]), num_rows="dynamic")
        else: st.info("Vazio")
