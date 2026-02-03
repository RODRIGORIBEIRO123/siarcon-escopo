import streamlit as st
import pandas as pd
import time
from datetime import datetime
import utils_db

# ============================================================================
# 1. CONFIGURAÇÕES
# ============================================================================
st.set_page_config(page_title="Siarcon - Gestão", page_icon="📊", layout="wide")

if 'logado' not in st.session_state:
    st.session_state['logado'] = False

# Login
if not st.session_state['logado']:
    col1, col2, col3 = st.columns([1,2,1])
    with col2:
        st.title("🔒 Siarcon Engenharia")
        senha = st.text_input("Senha de Acesso", type="password")
        if st.button("Entrar"):
            if senha == "1234":
                st.session_state['logado'] = True
                st.rerun()
            else:
                st.error("Senha incorreta")
    st.stop()

# ============================================================================
# 2. BARRA LATERAL (CADASTRO)
# ============================================================================
with st.sidebar:
    st.title("Siarcon")
    st.divider()
    st.header("➕ Novo Projeto")
    
    with st.form("novo_projeto", clear_on_submit=True):
        cliente = st.text_input("Cliente")
        obra = st.text_input("Nome da Obra")
        disciplina = st.selectbox("Disciplina", [
            "Dutos", "Hidráulica", "Elétrica", 
            "Automação", "TAB", "Movimentações", "Cobre"
        ])
        
        # STATUS ORIGINAIS DO SEU FLUXO
        status_opcoes = ["Não Iniciado", "Engenharia", "Obras", "Suprimentos", "Finalizado"]
        status = st.selectbox("Status Inicial", status_opcoes)
        
        prazo = st.date_input("Prazo")
        
        if st.form_submit_button("Criar Projeto"):
            if cliente and obra:
                novo = {
                    "data": datetime.now().strftime("%Y-%m-%d"),
                    "cliente": cliente,
                    "obra": obra,
                    "disciplina": disciplina,
                    "status": status,
                    "prazo": str(prazo)
                }
                utils_db.salvar_projeto(novo)
                st.success("Projeto cadastrado!")
                time.sleep(1)
                st.rerun()
            else:
                st.error("Preencha Cliente e Obra.")

    st.divider()
    if st.button("🔄 Atualizar Painel"):
        st.cache_data.clear()
        st.rerun()

# ============================================================================
# 3. KANBAN (LAYOUT RESTAURADO)
# ============================================================================
st.title("📊 Painel de Projetos")

try:
    df = utils_db.listar_todos_projetos()
except Exception as e:
    st.error(f"Erro ao ler banco: {e}")
    df = pd.DataFrame()

if df.empty:
    st.info("Nenhum projeto encontrado.")
else:
    # Garante colunas mínimas
    for c in ['obra', 'cliente', 'disciplina', 'status']:
        if c not in df.columns: df[c] = "-"

    # COLUNAS DO SEU FLUXO
    colunas_kanban = ["Não Iniciado", "Engenharia", "Obras", "Suprimentos", "Finalizado"]
    cols = st.columns(len(colunas_kanban))
    
    cores = {
        "Não Iniciado": "🔴", 
        "Engenharia": "🔵", 
        "Obras": "🏗️", 
        "Suprimentos": "📦", 
        "Finalizado": "🟢"
    }

    for i, status_nome in enumerate(colunas_kanban):
        with cols[i]:
            st.markdown(f"### {cores.get(status_nome, '⚪')} {status_nome}")
            st.divider()
            
            if 'status' in df.columns:
                df_s = df[df['status'] == status_nome]
            else:
                df_s = pd.DataFrame()
            
            for idx, row in df_s.iterrows():
                with st.container(border=True):
                    # Título usa 'obra' (se não tiver, tenta 'projeto')
                    titulo = row.get('obra', row.get('projeto', 'Sem Nome'))
                    cli = row.get('cliente', '')
                    disc = row.get('disciplina', 'Dutos')
                    
                    st.markdown(f"**{titulo}**")
                    st.caption(f"🏢 {cli}")
                    st.caption(f"🔧 {disc}")
                    
                    # --- CORREÇÃO DO VÍNCULO AQUI ---
                    uid = row.get('_id', idx)
                    if st.button("✏️ Editar", key=f"edit_{uid}", use_container_width=True):
                        
                        # 1. Salva OBRIGATORIAMENTE 'obra' e 'cliente' na memória
                        st.session_state['projeto_ativo'] = titulo
                        st.session_state['cliente_ativo'] = cli
                        st.session_state['id_projeto_editar'] = uid
                        st.session_state['logado'] = True
                        
                        # 2. Roteamento
                        rotas = {
                            "Dutos": "pages/1_Dutos.py",
                            "Hidráulica": "pages/2_Hidráulica.py",
                            "Elétrica": "pages/3_Elétrica.py",
                            "Automação": "pages/4_Automação.py",
                            "TAB": "pages/5_TAB.py",
                            "Movimentações": "pages/6_Movimentações.py",
                            "Cobre": "pages/7_Cobre.py"
                        }
                        
                        destino = rotas.get(disc, "pages/1_Dutos.py")
                        st.switch_page(destino)
