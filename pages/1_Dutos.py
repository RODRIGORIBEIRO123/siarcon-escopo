import streamlit as st
import pandas as pd
from datetime import datetime
import time

# Configuração da Página
st.set_page_config(page_title="Escopo - Dutos", page_icon="🔧", layout="wide")

# 1. Recupera contexto (Vem do Dashboard)
projeto_ativo = st.session_state.get('projeto_ativo')
cliente_ativo = st.session_state.get('cliente_ativo')

# 2. Verifica se veio do Dashboard corretamente
if not projeto_ativo:
    st.error("⛔ Projeto não selecionado.")
    st.info("Por favor, volte ao Dashboard e selecione um projeto.")
    # CORREÇÃO AQUI: O nome do arquivo tem que ser exato, com emoji, conforme seu log
    if st.button("Voltar ao Dashboard"):
        st.switch_page("_📊_Dashboard.py") 
    st.stop()

DISCIPLINA_ATUAL = "Dutos"

st.title(f"🔧 Escopo: {DISCIPLINA_ATUAL}")
st.success(f"📂 Obra: **{projeto_ativo}** | 🏢 Cliente: **{cliente_ativo}**")

# Inicializa lista local
if 'db_escopo' not in st.session_state:
    st.session_state['db_escopo'] = []

# --- FORMULÁRIO ---
with st.sidebar:
    st.header(f"➕ Adicionar Item")
    with st.form("form_item", clear_on_submit=True):
        descricao = st.text_input("Descrição")
        c1, c2 = st.columns(2)
        qtd = c1.number_input("Qtd", value=1.0)
        unid = c2.selectbox("Unid.", ["pç", "m", "m²", "kg", "vb", "h"])
        obs = st.text_area("Obs")
        
        if st.form_submit_button("Salvar"):
            novo_item = {
                "data": datetime.now().strftime("%d/%m/%Y"),
                "projeto": projeto_ativo,  # Usa o projeto que veio do dashboard
                "cliente": cliente_ativo,  # Usa o cliente que veio do dashboard
                "disciplina": DISCIPLINA_ATUAL,
                "descricao": descricao,
                "qtd": qtd,
                "unid": unid,
                "obs": obs,
                "origem": "Manual"
            }
            st.session_state['db_escopo'].append(novo_item)
            st.success("Salvo!")
            time.sleep(0.5)
            st.rerun() # Força atualização da tabela

# --- TABELA ---
df = pd.DataFrame(st.session_state['db_escopo'])

if not df.empty:
    # Filtra só o projeto atual
    filtro = (df['projeto'] == projeto_ativo) & (df['disciplina'] == DISCIPLINA_ATUAL)
    df_show = df[filtro].copy()
    
    if not df_show.empty:
        st.data_editor(
            df_show, 
            column_config={
                "projeto": None, 
                "cliente": None, 
                "disciplina": None
            },
            use_container_width=True,
            num_rows="dynamic",
            key="tabela_dutos"
        )
    else:
        st.info("Nenhum item cadastrado para este projeto.")
else:
    st.info("Lista vazia.")

st.divider()
# CORREÇÃO DO BOTÃO VOLTAR TAMBÉM
if st.button("⬅️ Voltar"):
    st.switch_page("_📊_Dashboard.py")
