import streamlit as st
import pandas as pd
import time
from datetime import datetime
import utils_db

# Configuração da Página
st.set_page_config(page_title="Siarcon - Gestão", page_icon="📊", layout="wide")

# Estado de Login
if 'logado' not in st.session_state: st.session_state['logado'] = False

if not st.session_state['logado']:
    col1, col2, col3 = st.columns([1,2,1])
    with col2:
        st.title("🔒 Siarcon")
        senha = st.text_input("Senha", type="password")
        if st.button("Entrar"):
            if senha == "1234":
                st.session_state['logado'] = True
                st.rerun()
            else:
                st.error("Senha incorreta")
    st.stop()

# --- BARRA LATERAL ---
with st.sidebar:
    st.title("Siarcon")
    st.divider()
    st.header("➕ Novo Projeto")
    
    with st.form("novo_projeto", clear_on_submit=True):
        cliente = st.text_input("Cliente")
        obra = st.text_input("Nome da Obra")
        disciplina = st.selectbox("Disciplina", ["Dutos", "Hidráulica", "Elétrica", "Automação", "TAB", "Movimentações", "Cobre"])
        # SEUS STATUS ORIGINAIS
        status = st.selectbox("Status", ["Não Iniciado", "Engenharia", "Obras", "Suprimentos", "Finalizado"])
        prazo = st.date_input("Prazo")
        
        if st.form_submit_button("Criar"):
            if cliente and obra:
                novo = {
                    "data": datetime.now().strftime("%Y-%m-%d"),
                    "cliente": cliente,
                    "obra": obra,
                    "disciplina": disciplina,
                    "status": status,
                    "prazo": str(prazo)
                }
                utils_db.salvar_projeto(novo) # Salva no banco real
                st.success("Criado!")
                time.sleep(1)
                st.rerun()
            else:
                st.error("Preencha dados básicos.")
    
    st.divider()
    if st.button("🔄 Atualizar"):
        st.cache_data.clear()
        st.rerun()

# --- KANBAN ---
st.title("📊 Painel de Projetos")

try: df = utils_db.listar_todos_projetos()
except: df = pd.DataFrame()

if df.empty:
    st.info("Nenhum projeto encontrado.")
else:
    # Garante colunas
    for c in ['obra', 'cliente', 'disciplina', 'status']:
        if c not in df.columns: df[c] = "-"

    # COLUNAS DO SEU FLUXO DE TRABALHO
    kanban_cols = ["Não Iniciado", "Engenharia", "Obras", "Suprimentos", "Finalizado"]
    cols_ui = st.columns(len(kanban_cols))
    
    for i, status_nome in enumerate(kanban_cols):
        with cols_ui[i]:
            st.markdown(f"### {status_nome}")
            st.divider()
            
            if 'status' in df.columns: df_s = df[df['status'] == status_nome]
            else: df_s = pd.DataFrame()
            
            for idx, row in df_s.iterrows():
                with st.container(border=True):
                    # Recupera dados com segurança
                    titulo = row.get('obra', row.get('projeto', 'Sem Nome'))
                    cli = row.get('cliente', '')
                    disc = row.get('disciplina', 'Dutos')
                    
                    st.markdown(f"**{titulo}**")
                    st.caption(f"{cli} | {disc}")
                    
                    # --- BOTÃO DE VÍNCULO (ESSENCIAL) ---
                    uid = row.get('_id', idx)
                    if st.button("✏️ Editar", key=f"ed_{uid}", use_container_width=True):
                        st.session_state['projeto_ativo'] = titulo
                        st.session_state['cliente_ativo'] = cli
                        st.session_state['id_projeto_editar'] = uid
                        st.session_state['logado'] = True
                        
                        rotas = {
                            "Dutos": "pages/1_Dutos.py",
                            "Hidráulica": "pages/2_Hidráulica.py",
                            "Elétrica": "pages/3_Elétrica.py",
                            "Automação": "pages/4_Automação.py",
                            "TAB": "pages/5_TAB.py",
                            "Movimentações": "pages/6_Movimentações.py",
                            "Cobre": "pages/7_Cobre.py"
                        }
                        st.switch_page(rotas.get(disc, "pages/1_Dutos.py"))
