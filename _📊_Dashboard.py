import streamlit as st
import pandas as pd
import time
from datetime import datetime, date
import utils_db

# ============================================================================
# 1. CONFIGURAÇÕES INICIAIS
# ============================================================================
st.set_page_config(page_title="Painel SIARCON", page_icon="📊", layout="wide")

# Inicializa sessão de login
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
                if senha == "1234" and usuario: # Validação simples
                    st.session_state['logado'] = True
                    st.session_state['usuario_atual'] = usuario
                    st.rerun()
                elif not usuario:
                    st.warning("Por favor, digite o nome do usuário.")
                else:
                    st.error("Senha incorreta.")
    st.stop() # Pára o código aqui se não estiver logado

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
c_head2.caption(f"👤 Usuário: **{st.session_state['usuario_atual']}**")

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
                # Usa a função unificada
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

    # Abas de Navegação (Filtros)
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
                            
                            # --- BOTÕES DE AÇÃO (SETAS, EDITAR, EXCLUIR) ---
                            c_esq, c_edit, c_del, c_dir = st.columns([1, 2, 1, 1])
                            
                            # 1. Mover Esquerda (⬅️)
                            if i > 0:
                                if c_esq.button("⬅️", key=f"L_{uid}", help="Voltar Fase"):
                                    novo_st = status_kanban[i-1]
                                    dados_up = row.to_dict(); dados_up['status'] = novo_st
                                    utils_db.salvar_projeto(dados_up)
                                    st.rerun()
                            
                            # 2. Editar (✏️)
                            if c_edit.button("✏️ Abrir", key=f"E_{uid}", use_container_width=True):
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
                            
                            # 3. Excluir (🗑️)
                            if c_del.button("🗑️", key=f"D_{uid}", help="Excluir Projeto"):
                                # Verifica se a função existe no utils_db
                                if hasattr(utils_db, 'excluir_projeto'):
                                    utils_db.excluir_projeto(uid)
                                    st.toast(f"Projeto {titulo} excluído!")
                                    time.sleep(1)
                                    st.rerun()
                                else:
                                    st.error("Função excluir_projeto não encontrada no utils_db!")
                                
                            # 4. Mover Direita (➡️)
                            if i < len(status_kanban) - 1:
                                if c_dir.button("➡️", key=f"R_{uid}", help="Avançar Fase"):
                                    novo_st = status_kanban[i+1]
                                    dados_up = row.to_dict(); dados_up['status'] = novo_st
                                    utils_db.salvar_projeto(dados_up)
                                    st.rerun()

st.divider()
if st.button("🔄 Atualizar Quadro"):
    st.cache_data.clear()
    st.rerun()
