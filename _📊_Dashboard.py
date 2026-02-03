import streamlit as st
import pandas as pd
import time
from datetime import datetime
import utils_db

# ============================================================================
# 1. CONFIGURAÇÕES
# ============================================================================
st.set_page_config(page_title="Painel SIARCON", page_icon="📊", layout="wide")

if 'logado' not in st.session_state:
    st.session_state['logado'] = False

# Tela de Login
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
# 2. CABEÇALHO E CADASTRO (NO TOPO)
# ============================================================================
st.title("Painel de projetos SIARCON")

# Formulário de Cadastro movido para o topo dentro de um Expander
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
        
        prazo = st.date_input("Prazo de Entrega")
        
        if st.form_submit_button("🚀 Criar Projeto"):
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
                st.success(f"Projeto '{obra}' cadastrado com sucesso!")
                time.sleep(1)
                st.rerun()
            else:
                st.error("Por favor, preencha o Cliente e o Nome da Obra.")

st.divider()

# ============================================================================
# 3. KANBAN (COM NAVEGAÇÃO POR ABAS/BOTÕES)
# ============================================================================

# Carrega Dados
try:
    df = utils_db.listar_todos_projetos()
except Exception as e:
    st.error(f"Erro ao ler banco: {e}")
    df = pd.DataFrame()

if df.empty:
    st.info("Nenhum projeto encontrado. Utilize o cadastro acima.")
else:
    # Garante colunas mínimas
    for c in ['obra', 'cliente', 'disciplina', 'status']:
        if c not in df.columns: df[c] = "-"

    # Definição das Abas (Etiquetas do Kanban)
    status_kanban = ["Não Iniciado", "Engenharia", "Obras", "Suprimentos", "Finalizado"]
    
    # Cria os "botões para ir para os lados" (Abas)
    abas = st.tabs([f"  {s}  " for s in status_kanban])
    
    cores = {
        "Não Iniciado": "🔴", 
        "Engenharia": "🔵", 
        "Obras": "🏗️", 
        "Suprimentos": "📦", 
        "Finalizado": "🟢"
    }

    # Preenche cada aba
    for i, status_nome in enumerate(status_kanban):
        with abas[i]:
            st.markdown(f"### {cores.get(status_nome, '⚪')} {status_nome}")
            
            # Filtra projetos do status atual
            if 'status' in df.columns:
                df_s = df[df['status'] == status_nome]
            else:
                df_s = pd.DataFrame()
            
            # Mostra os cards
            if df_s.empty:
                st.caption("Nenhum projeto nesta fase.")
            else:
                # Cria um grid de cards (3 por linha para não ficar lista linguiça)
                cols_cards = st.columns(3)
                for idx, (index_df, row) in enumerate(df_s.iterrows()):
                    col_atual = cols_cards[idx % 3]
                    
                    with col_atual:
                        with st.container(border=True):
                            titulo = row.get('obra', row.get('projeto', 'Sem Nome'))
                            cli = row.get('cliente', '')
                            disc = row.get('disciplina', '-')
                            prazo_txt = row.get('prazo', '-')
                            
                            st.markdown(f"**{titulo}**")
                            st.text(f"🏢 {cli}")
                            st.caption(f"🔧 {disc} | 📅 {prazo_txt}")
                            
                            # BOTÃO DE EDIÇÃO (Mantendo a correção do vínculo)
                            uid = row.get('_id', index_df)
                            if st.button("✏️ Abrir Escopo", key=f"btn_{uid}", use_container_width=True):
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
                                destino = rotas.get(disc, "pages/1_Dutos.py")
                                st.switch_page(destino)

# --- BOTÃO DE RECARGA (Rodapé) ---
st.divider()
if st.button("🔄 Atualizar Quadro"):
    st.cache_data.clear()
    st.rerun()
