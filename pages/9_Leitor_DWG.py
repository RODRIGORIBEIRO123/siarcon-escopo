import streamlit as st
import ezdxf
from ezdxf import recover
import pandas as pd
import tempfile
import os
import re
import math
from openai import OpenAI
from collections import Counter

# --- 🔒 SEGURANÇA ---
if 'logado' not in st.session_state or not st.session_state['logado']:
    st.warning("🔒 Acesso negado. Faça login no Dashboard.")
    st.stop()

st.set_page_config(page_title="Leitor DXF (Layout Oficial)", page_icon="📐", layout="wide")

st.title("📐 Leitor Técnico DXF")
st.markdown("""
Esta ferramenta extrai quantitativos baseados na leitura das **Etiquetas de Texto** do projeto.
A inteligência artificial classifica os itens nas abas corretas abaixo.
""")

# ============================================================================
# 1. CONFIGURAÇÕES (MENU LATERAL)
# ============================================================================
with st.sidebar:
    st.header("⚙️ Parâmetros de Cálculo")
    
    st.info("ℹ️ Cálculo de Dutos: Baseado na contagem de etiquetas x Comprimento Padrão.")
    comp_padrao = st.number_input("Comp. Padrão da Peça (m)", value=1.10, step=0.10, help="Comprimento médio de um duto reto (ex: 1.10m para dobra de chapa).")
    
    st.divider()
    classe_pressao = st.selectbox("Classe de Pressão", ["Classe A (Baixa)", "Classe B (Média)", "Classe C (Alta)"])
    perda_corte = st.number_input("% Perda / Corte", value=10.0)
    tipo_isolamento = st.selectbox("Isolamento", ["Lã de Vidro", "Borracha Elast.", "Isopor", "Sem Isolamento"])

# ============================================================================
# 2. MOTOR DE LEITURA (BLINDADO CONTRA ERROS BINÁRIOS)
# ============================================================================
def ler_textos_dxf_seguro(uploaded_file):
    """
    Usa arquivo temporário e 'recover' para ler qualquer DXF sem travar.
    Retorna apenas a lista de textos limpos e contados.
    """
    textos_encontrados = []
    temp_path = None
    
    try:
        # Salva temporário (Evita erro de buffer/rstrip)
        with tempfile.NamedTemporaryFile(delete=False, suffix=".dxf") as tmp_file:
            tmp_file.write(uploaded_file.getvalue())
            temp_path = tmp_file.name
            
        # Usa recover para abrir até arquivo corrompido
        doc, auditor = recover.readfile(temp_path)
        msp = doc.modelspace()
        
        # Extrai Textos
        for e in msp.query('TEXT MTEXT'):
            raw = e.dxf.text if e.dxftype() == 'TEXT' else e.text
            # Limpeza básica de códigos do AutoCAD
            clean = re.sub(r'\\[ACFHQTW].*?;', '', raw).replace('{', '').replace('}', '').strip()
            if len(clean) > 1 and len(clean) < 50: # Filtra lixo
                textos_encontrados.append(clean)
                
    except Exception as e:
        st.error(f"Erro na leitura do arquivo: {e}")
        return None
    finally:
        if temp_path and os.path.exists(temp_path):
            try: os.remove(temp_path)
            except: pass
            
    # Retorna contagem (ex: {'500x300': 10, 'FC-01': 2})
    return Counter(textos_encontrados)

# ============================================================================
# 3. INTELIGÊNCIA ARTIFICIAL (CLASSIFICAÇÃO)
# ============================================================================
def classificar_com_ia(dicionario_contagem):
    if "openai" not in st.secrets:
        st.error("🚨 Chave OpenAI não configurada."); return None
    
    # Prepara o resumo para a IA (Top 400 itens mais frequentes)
    texto_prompt = ""
    for k, v in dicionario_contagem.most_common(400):
        texto_prompt += f"TXT: '{k}' | QTD: {v}\n"
    
    client = OpenAI(api_key=st.secrets["openai"]["api_key"])
    
    prompt = """
    Você é um Engenheiro de Orçamentos HVAC. 
    Analise a lista de textos (TXT) e quantidades (QTD) extraídas de um DXF.
    
    SEU OBJETIVO: Separar em 4 categorias no formato CSV (ponto e vírgula).
    
    REGRAS:
    1. DUTOS: Procure medidas (AxL ou ø). Ex: 500x300, 30x20, 200ø.
    2. TERMINAIS: Grelhas, Difusores, Venezianas, Dampers.
    3. EQUIPAMENTOS: Fancoil, Split, VRF, K7 (Extraia TR/BTU/HP se houver).
    4. ELETRICA: Quadros, Painéis, Tomadas.

    SAÍDA OBRIGATÓRIA:
    ---DUTOS---
    Largura;Altura;Tipo;Qtd
    500;300;Rect;10
    200;200;Circ;5
    
    ---TERMINAIS---
    Item;Qtd
    Grelha Retorno 600x600;8
    
    ---EQUIPAMENTOS---
    Tag;Tipo;Detalhes;Qtd
    FC-01;Fancoil;5TR;2
    
    ---ELETRICA---
    Tag;Desc;Qtd
    Q-01;Quadro Força;1
    """
    
    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": texto_prompt}
            ],
            temperature=0.0
        )
        return response.choices[0].message.content
    except Exception as e:
        st.error(f"Erro na IA: {e}")
        return None

def processar_resposta_ia(resposta):
    blocos = {"DUTOS": [], "TERMINAIS": [], "EQUIPAMENTOS": [], "ELETRICA": []}
    atual = None
    if not resposta: return blocos
    
    for linha in resposta.split('\n'):
        linha = linha.strip()
        if "---DUTOS" in linha: atual = "DUTOS"; continue
        if "---TERM" in linha: atual = "TERMINAIS"; continue
        if "---EQUI" in linha: atual = "EQUIPAMENTOS"; continue
        if "---ELET" in linha: atual = "ELETRICA"; continue
        
        if atual and ";" in linha and "Largura" not in linha and "Tag" not in linha:
            blocos[atual].append(linha.split(';'))
    return blocos

# ============================================================================
# 4. INTERFACE PRINCIPAL
# ============================================================================
uploaded_dxf = st.file_uploader("📂 Carregar Arquivo .DXF", type=["dxf"])

if uploaded_dxf:
    with st.spinner("Lendo arquivo (Modo Seguro)..."):
        contagem = ler_textos_dxf_seguro(uploaded_dxf)
        
    if contagem:
        st.success(f"✅ Arquivo Lido! {len(contagem)} textos únicos identificados.")
        
        if st.button("🚀 Classificar e Calcular", type="primary"):
            with st.spinner("A IA está organizando o orçamento..."):
                res_ia = classificar_com_ia(contagem)
                if res_ia:
                    st.session_state['dados_orcamento'] = processar_resposta_ia(res_ia)
                    st.rerun()

# ============================================================================
# 5. RESULTADOS (LAYOUT APROVADO)
# ============================================================================
if 'dados_orcamento' in st.session_state:
    d = st.session_state['dados_orcamento']
    
    # Abas conforme solicitado
    tab_dutos, tab_term, tab_equip, tab_elet = st.tabs([
        "🌪️ Rede de Dutos", 
        "💨 Terminais de Ar", 
        "⚙️ Equipamentos", 
        "⚡ Elétrica"
    ])
    
    # --- ABA 1: DUTOS (COM CÁLCULOS E KPIS) ---
    with tab_dutos:
        if d["DUTOS"]:
            # Cria DataFrame
            df = pd.DataFrame(d["DUTOS"], columns=["Largura", "Altura", "Tipo", "Qtd Peças"])
            
            # Tratamento de erro numérico (Vital para não quebrar)
            for col in ["Largura", "Altura", "Qtd Peças"]:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
            
            # Coluna de Comprimento Padrão (Editável)
            df["Comp. Padrão (m)"] = comp_padrao
            
            # Tabela Editável
            st.markdown("### 📋 Quantitativo de Dutos")
            df_edit = st.data_editor(
                df, 
                num_rows="dynamic", 
                use_container_width=True,
                key="editor_dutos",
                column_config={
                    "Largura": st.column_config.NumberColumn("Largura (mm)", format="%d"),
                    "Altura": st.column_config.NumberColumn("Altura (mm)", format="%d"),
                    "Qtd Peças": st.column_config.NumberColumn("Qtd (Tags)"),
                    "Comp. Padrão (m)": st.column_config.NumberColumn("Comp. Unit (m)", step=0.1)
                }
            )
            
            st.divider()
            
            # --- CÁLCULOS ---
            # Perímetro (m)
            df_calc = df_edit.copy()
            # Lógica para Retangular vs Circular
            # Se for circular, considera Largura como Diâmetro
            df_calc['Perímetro (m)'] = df_calc.apply(
                lambda row: (math.pi * row['Largura'] / 1000) if 'Circ' in str(row['Tipo']) 
                else (2 * row['Largura'] + 2 * row['Altura']) / 1000, axis=1
            )
            
            # Área (m²) = Perímetro * (Qtd * Comp. Padrão)
            df_calc['Comp. Total (m)'] = df_calc['Qtd Peças'] * df_calc['Comp. Padrão (m)']
            df_calc['Área (m²)'] = df_calc['Perímetro (m)'] * df_calc['Comp. Total (m)']
            
            # Totais
            fator_perda = 1 + (perda_corte / 100)
            area_total = (df_calc['Área (m²)'] * fator_perda).sum()
            peso_total = area_total * 5.6 # Estimativa kg/m2
            
            # --- VISUAL DOS KPIs (No topo da aba, como pedido) ---
            c1, c2, c3 = st.columns(3)
            c1.metric("Área Total (c/ Perda)", f"{area_total:,.2f} m²")
            c2.metric("Peso Estimado", f"{peso_total:,.0f} kg")
            val_iso = f"{area_total:,.2f} m²" if tipo_isolamento != "Sem Isolamento" else "-"
            c3.metric("Isolamento", val_iso, delta=tipo_isolamento)
            
            # Exibe memória de cálculo detalhada se quiser
            with st.expander("Ver Memória de Cálculo Detalhada"):
                st.dataframe(df_calc[['Largura', 'Altura', 'Qtd Peças', 'Comp. Total (m)', 'Área (m²)']])
                
        else:
            st.info("Nenhum duto identificado automaticamente.")

    # --- ABA 2: TERMINAIS ---
    with tab_term:
        if d["TERMINAIS"]:
            df_t = pd.DataFrame(d["TERMINAIS"], columns=["Item", "Qtd"])
            st.data_editor(df_t, num_rows="dynamic", use_container_width=True)
        else: st.warning("Vazio")

    # --- ABA 3: EQUIPAMENTOS ---
    with tab_equip:
        if d["EQUIPAMENTOS"]:
            df_e = pd.DataFrame(d["EQUIPAMENTOS"], columns=["Tag", "Tipo", "Detalhes", "Qtd"])
            st.data_editor(df_e, num_rows="dynamic", use_container_width=True)
        else: st.warning("Vazio")

    # --- ABA 4: ELÉTRICA ---
    with tab_elet:
        if d["ELETRICA"]:
            df_el = pd.DataFrame(d["ELETRICA"], columns=["Tag", "Descrição", "Qtd"])
            st.data_editor(df_el, num_rows="dynamic", use_container_width=True)
        else: st.warning("Vazio")
