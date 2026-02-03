import streamlit as st
import pandas as pd
from datetime import datetime
import time

# Configuração da Página
st.set_page_config(page_title="Escopo - Dutos", page_icon="🔧", layout="wide")

# 1. RECUPERAÇÃO DO VÍNCULO (Correção do Bug de Preenchimento)
projeto_ativo = st.session_state.get('projeto_ativo')
cliente_ativo = st.session_state.get('cliente_ativo')

# Trava de segurança: Se tentar acessar direto sem passar pelo Dashboard
if not projeto_ativo:
    st.error("⛔ Nenhum projeto selecionado.")
    st.info("Volte ao Dashboard e clique no 'Lápis' do projeto desejado.")
    if st.button("Voltar ao Dashboard"):
        st.switch_page("_📊_Dashboard.py")
    st.stop()

DISCIPLINA_ATUAL = "Dutos"

st.title(f"🔧 Escopo: {DISCIPLINA_ATUAL}")
st.success(f"📂 Obra: **{projeto_ativo}** | 🏢 Cliente: **{cliente_ativo}**")

# Inicializa banco local de memória
if 'db_escopo' not in st.session_state:
    st.session_state['db_escopo'] = []

# --- FORMULÁRIO ---
with st.sidebar:
    st.header("➕ Adicionar Item")
    with st.form("form_item", clear_on_submit=True):
        descricao = st.text_input("Descrição")
        c1, c2 = st.columns(2)
        qtd = c1.number_input("Qtd", value=1.0)
        unid = c2.selectbox("Unid.", ["pç", "m", "m²", "kg", "vb", "h"])
        obs = st.text_area("Obs")
        
        if st.form_submit_button("Salvar"):
            novo_item = {
                "data": datetime.now().strftime("%d/%m/%Y"),
                "projeto": projeto_ativo,  # <--- Aqui está o segredo: usa a variável recuperada
                "cliente": cliente_ativo,  # <--- Aqui está o segredo
                "disciplina": DISCIPLINA_ATUAL,
                "descricao": descricao,
                "qtd": qtd,
                "unid": unid,
                "obs": obs,
                "origem": "Manual"
            }
            st.session_state['db_escopo'].append(novo_item)
            st.success("Item salvo!")
            time.sleep(0.5)
            st.rerun()

# --- TABELA DE ITENS ---
df = pd.DataFrame(st.session_state['db_escopo'])

if not df.empty:
    # Filtra apenas itens DESTE projeto e DESTA disciplina
    filtro = (df['projeto'] == projeto_ativo) & (df['disciplina'] == DISCIPLINA_ATUAL)
    df_show = df[filtro].copy()
    
    if not df_show.empty:
        st.data_editor(
            df_show, 
            column_config={
                "projeto": None, # Oculta pois é redundante
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
if st.button("⬅️ Voltar ao Dashboard"):
    st.switch_page("_📊_Dashboard.py")
