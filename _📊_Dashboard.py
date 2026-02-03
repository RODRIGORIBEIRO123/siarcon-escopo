import streamlit as st
import pandas as pd
import time
from datetime import datetime, date
import utils_db

# ============================================================================
# 1. CONFIGURAÇÕES INICIAIS
# ============================================================================
st.set_page_config(page_title="Painel SIARCON", page_icon="📊", layout="wide")

# Inicializa variáveis de sessão
if 'logado' not in st.session_state:
    st.session_state['logado'] = False
if 'usuario_atual' not in st.session_state:
    st.session_state['usuario_atual'] = ""

# --- TELA DE LOGIN (CORRIGIDA) ---
if not st.session_state['logado']:
    col1, col2, col3 = st.columns([1,2,1])
    with col2:
        st.title("🔒 Siarcon Engenharia")
        st.markdown("### Acesso Restrito")
        
        with st.form("form_login"):
            usuario = st.text_input("Usuário")
            senha = st.text_input("Senha de Acesso", type="password")
            btn_entrar = st.form_submit_button("Entrar")
            
            if btn_entrar:
                # Validação simples (Senha Fixa: 1234)
                if senha == "1234" and usuario:
                    st.session_state['logado'] = True
                    st.session_state['usuario_atual'] = usuario
                    st.rerun()
                elif not usuario:
                    st.warning("Por favor, digite seu usuário.")
                else:
                    st.error("Senha incorreta.")
    
    # COMANDO CRÍTICO: Pára o script aqui se não estiver logado
    st.stop()

# Função auxiliar de data
def formatar_data_br(valor):
    if not valor or valor == "-": return "-"
    try:
        if isinstance(valor, (datetime, date)):
            return valor.strftime("%d/%m/%Y")
        return datetime.strptime(str(valor), "%Y-%m-%d").strftime("%d/%m/%Y")
    except:
        return valor

# ============================================================================
# 2. CABEÇALHO E CADASTRO
# ============================================================================
c_head1, c_head2 = st.columns([3, 1])
c_head1.title("Painel de projetos SIARCON")
c_head2.info(f"👤 Logado como: **{st.session_state['usuario_atual']}**")

with st.expander("➕ Cadastrar Nova Obra / Projeto", expanded=False):
    with st.form("novo_projeto", clear_on_submit=True):
        c1, c2 = st.columns(2)
        cliente = c1.text_input("Cliente")
        obra = c2.text_input("Nome da Obra")
        
        c3, c4 = st.columns(2)
        disciplina = c3.selectbox("Disciplina", [
            "Dutos", "Hidráulica", "Elétrica", 
            "Automação", "TAB", "Movimentações", "Cobre"
        ])
        
        status_opcoes = ["Não Iniciado", "Engenharia", "Obras", "Suprimentos", "Finalizado"]
        status = c4.selectbox("Status Inicial", status_opcoes)
        
        prazo_input = st.date_input("Prazo de Entrega", format="DD/MM/YYYY")
        
        if st.form_submit_button("🚀 Criar Projeto"):
            if cliente and obra:
                novo = {
                    "data": datetime.now().strftime("%Y-%m-%d"),
                    "cliente": cliente,
                    "obra": obra,
                    "disciplina": disciplina,
                    "status": status,
                    "prazo": str(prazo_input),
                    "criado_por": st.session_state['usuario_atual']
                }
                utils_db.salvar_projeto(novo)
                st.success(f"Projeto '{obra}' cadastrado!")
                time.sleep(1)
                st.rerun()
            else:
                st.error("Preencha Cliente e Obra.")

st.divider()

# ============================================================================
# 3. KANBAN (COM SETAS E LIXEIRA)
# ============================================================================
try:
    df = utils_db.listar_todos_projetos()
except Exception as e:
    st.error(f"Erro ao ler banco: {e}")
    df = pd.DataFrame()

if df.empty:
    st.info("Nenhum projeto encontrado.")
else:
    # Garante colunas
    for c in ['obra', 'cliente', 'disciplina', 'status']:
        if c not in df.columns: df[c] = "-"
    
    # Normalização dos Status
    status_kanban = ["Não Iniciado", "Engenharia", "Obras", "Suprimentos", "Finalizado"]
    if 'status' in df.columns:
        df['status'] = df['status'].astype(str).str.strip()
        df.loc[~df['status'].isin(status_kanban), 'status'] = "Não Iniciado"

    # Abas de Navegação (Abas funcionam como filtro lateral/superior)
    abas = st.tabs([f"  {s}  " for s in status_kanban])
    
    cores = {
        "Não Iniciado": "🔴", "Engenharia": "🔵", 
        "Obras": "🏗️", "Suprimentos": "📦", "Finalizado": "🟢"
    }

    for i, status_nome in enumerate(status_kanban):
        with abas[i]:
            st.markdown(f"### {cores.get(status_nome, '⚪')} {status_nome}")
            
            if 'status' in df.columns:
                df_s = df[df['status'] == status_nome]
            else:
                df_s = pd.DataFrame()
            
            if df_s.empty:
                st.caption("Nenhum projeto nesta fase.")
            else:
                cols_cards = st.columns(3)
                for idx, (index_df, row) in enumerate(df_s.iterrows()):
                    col_atual = cols_cards[idx % 3]
                    
                    with col_atual:
                        with st.container(border=True):
                            uid = row.get('_id', index_df)
                            titulo = row.get('obra', 'Sem Nome')
                            cli = row.get('cliente', '')
                            disc = row.get('disciplina', '-')
                            prazo_txt = formatar_data_br(row.get('prazo', '-'))
                            
                            st.markdown(f"**{titulo}**")
                            st.text(f"🏢 {cli}")
                            st.caption(f"🔧 {disc} | 📅 {prazo_txt}")
                            
                            st.divider()
                            
                            # --- BOTÕES DE AÇÃO ---
                            c_esq, c_edit, c_del, c_dir = st.columns([1, 2, 1,
