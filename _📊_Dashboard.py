import streamlit as st
import pandas as pd
import time
from datetime import datetime
import utils_db  # Volta a usar sua conexão oficial

# ============================================================================
# 1. CONFIGURAÇÕES INICIAIS
# ============================================================================
st.set_page_config(page_title="Siarcon - Gestão", page_icon="📊", layout="wide")

# Inicializa sessão
if 'logado' not in st.session_state:
    st.session_state['logado'] = False

# Tela de Login (Padrão)
if not st.session_state['logado']:
    col1, col2, col3 = st.columns([1,2,1])
    with col2:
        st.title("🔒 Siarcon Engenharia")
        senha = st.text_input("Senha", type="password")
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
        status = st.selectbox("Status", ["Não Iniciado", "Em Andamento"])
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
                # Salva no banco real
                utils_db.salvar_projeto(novo)
                st.success("Projeto criado!")
                time.sleep(1)
                st.rerun()
            else:
                st.error("Preencha Cliente e Obra.")

    st.divider()
    if st.button("🔄 Atualizar Dados"):
        st.cache_data.clear()
        st.rerun()

# ============================================================================
# 3. KANBAN (RESTAURADO PARA VERSÃO JANEIRO)
# ============================================================================
st.title("📊 Painel de Projetos")

# Tenta carregar do banco. Se der erro, cria vazio para não quebrar a tela.
try:
    df = utils_db.listar_todos_projetos()
except Exception as e:
    st.error(f"Erro ao conectar no banco: {e}")
    df = pd.DataFrame()

if df.empty:
    st.info("Nenhum projeto encontrado no banco de dados.")
else:
    # Garante colunas mínimas para evitar erro de chave
    for c in ['obra', 'cliente', 'disciplina', 'status']:
        if c not in df.columns: df[c] = "-"

    # Layout Kanban
    cols = st.columns(4)
    status_map = ["Não Iniciado", "Em Andamento", "Revisão", "Concluído"]
    colors = {"Não Iniciado": "🔴", "Em Andamento": "🟡", "Revisão": "🟠", "Concluído": "🟢"}

    for i, s_nome in enumerate(status_map):
        with cols[i]:
            st.markdown(f"### {colors.get(s_nome, '⚪')} {s_nome}")
            st.divider()
            
            if 'status' in df.columns:
                df_s = df[df['status'] == s_nome]
            else:
                df_s = df # Se não tiver status, mostra tudo
            
            for idx, row in df_s.iterrows():
                with st.container(border=True):
                    # Tenta pegar 'obra', se falhar pega 'projeto' (Proteção de nomes)
                    titulo = row.get('obra', row.get('projeto', 'Sem Nome'))
                    cli = row.get('cliente', '')
                    disc = row.get('disciplina', 'Dutos')
                    
                    st.markdown(f"**{titulo}**")
                    st.caption(f"🏢 {cli} | 🔧 {disc}")
                    
                    # --- BOTÃO DE EDIÇÃO (CORRIGIDO) ---
                    # Usa ID ou Index para chave única
                    uid = row.get('_id', idx)
                    if st.button("✏️ Editar", key=f"edit_{uid}", use_container_width=True):
                        
                        # SALVA NA MEMÓRIA GLOBAL (CRÍTICO PARA FUNCIONAR)
                        st.session_state['projeto_ativo'] = titulo
                        st.session_state['cliente_ativo'] = cli
                        st.session_state['id_projeto_editar'] = uid
                        st.session_state['logado'] = True
                        
                        # REDIRECIONAMENTO
                        rotas = {
                            "Dutos": "pages/1_Dutos.py",
                            "Hidráulica": "pages/2_Hidráulica.py",
                            "Elétrica": "pages/3_Elétrica.py",
                            "Automação": "pages/4_Automação.py",
                            "TAB": "pages/5_TAB.py",
                            "Movimentações": "pages/6_Movimentações.py",
                            "Cobre": "pages/7_Cobre.py"
                        }
                        # Vai para a página certa
                        st.switch_page(rotas.get(disc, "pages/1_Dutos.py"))
