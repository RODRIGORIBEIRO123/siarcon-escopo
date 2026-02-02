import streamlit as st
import pandas as pd
from datetime import datetime
import time

# Se você tiver o arquivo utils_db.py, descomente a linha abaixo:
# import utils_db 

# ============================================================================
# CONFIGURAÇÃO DA PÁGINA E RECUPERAÇÃO DE ESTADO
# ============================================================================
st.set_page_config(page_title="Escopo - Dutos", page_icon="🔧", layout="wide")

# 1. Recupera as credenciais que o Dashboard enviou
projeto_ativo = st.session_state.get('projeto_ativo')
cliente_ativo = st.session_state.get('cliente_ativo')

# 2. Trava de Segurança: Se não vier do Dashboard, avisa.
if not projeto_ativo or not cliente_ativo:
    st.error("⛔ ERRO DE VÍNCULO: Projeto não identificado.")
    st.info("Vá ao Dashboard e clique no lápis ✏️ do card do projeto.")
    if st.button("Voltar ao Dashboard"):
        st.switch_page("_Dashboard.py") # Verifique se o nome do arquivo principal é esse
    st.stop()

# Define a disciplina desta página
DISCIPLINA_ATUAL = "Dutos"

st.title(f"🔧 Escopo: {DISCIPLINA_ATUAL}")
# Mostra que está vinculado corretamente
st.success(f"📂 Projeto: **{projeto_ativo}** | 🏢 Cliente: **{cliente_ativo}**")

# Garante que a lista local exista (para visualização imediata)
if 'db_escopo' not in st.session_state:
    st.session_state['db_escopo'] = []

# ============================================================================
# FORMULÁRIO (Lateral)
# ============================================================================
with st.sidebar:
    st.header(f"➕ Adicionar em {DISCIPLINA_ATUAL}")
    
    with st.form("form_item", clear_on_submit=True):
        descricao = st.text_input("Descrição do Item:")
        c1, c2 = st.columns(2)
        qtd = c1.number_input("Quantidade", min_value=0.0, value=1.0, step=1.0)
        unid = c2.selectbox("Unidade", ["pç", "m", "m²", "kg", "vb", "h", "gl", "cj"])
        obs = st.text_area("Observações")
        
        enviado = st.form_submit_button("💾 Salvar Item")

        if enviado:
            if not descricao:
                st.error("Descrição é obrigatória.")
            else:
                # 1. Cria o objeto do item
                novo_item = {
                    "data": datetime.now().strftime("%d/%m/%Y"),
                    "projeto": projeto_ativo,  # <--- USA A VARIÁVEL RECUPERADA
                    "cliente": cliente_ativo,  # <--- USA A VARIÁVEL RECUPERADA
                    "disciplina": DISCIPLINA_ATUAL,
                    "descricao": descricao,
                    "qtd": qtd,
                    "unid": unid,
                    "obs": obs,
                    "origem": "Manual"
                }
                
                # 2. Salva na Sessão (Visualização Imediata)
                st.session_state['db_escopo'].append(novo_item)
                
                # 3. (OPCIONAL) Se você tiver função de banco, chame aqui:
                # utils_db.salvar_item_escopo(novo_item) 

                st.toast(f"Item '{descricao}' salvo com sucesso!")
                
                # 4. FORÇA A ATUALIZAÇÃO DA TELA (Corrige o bug de não aparecer)
                time.sleep(0.5)
                st.rerun()

# ============================================================================
# TABELA DE ITENS
# ============================================================================
# Converte a lista da memória em Tabela
df = pd.DataFrame(st.session_state['db_escopo'])

if not df.empty:
    # Filtra: Só mostra itens DESTE projeto e DESTA disciplina
    filtro = (df['projeto'] == projeto_ativo) & (df['disciplina'] == DISCIPLINA_ATUAL)
    df_filtrado = df[filtro].copy()

    if not df_filtrado.empty:
        st.data_editor(
            df_filtrado,
            column_config={
                "descricao": "Descrição",
                "qtd": st.column_config.NumberColumn("Qtd", format="%.2f"),
                "unid": "Unid.",
                "obs": "Obs",
                # Ocultamos colunas repetitivas para limpar a visão
                "projeto": None, 
                "cliente": None,
                "disciplina": None
            },
            use_container_width=True,
            num_rows="dynamic", # Permite adicionar linhas na tabela
            key="editor_dutos"
        )
    else:
        st.info(f"Nenhum item cadastrado em {DISCIPLINA_ATUAL} para este projeto.")
else:
    st.info("Lista de escopo vazia.")

# Botão de Voltar
st.divider()
if st.button("⬅️ Voltar ao Dashboard"):
    st.switch_page("_Dashboard.py")
