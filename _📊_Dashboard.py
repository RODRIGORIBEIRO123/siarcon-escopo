import streamlit as st
import pandas as pd
import time
from datetime import datetime
import utils_db  # Garanta que este arquivo está na pasta

# --- CONFIGURAÇÃO DA PÁGINA (Deve ser a primeira linha) ---
st.set_page_config(page_title="Siarcon - Gestão de Escopo", page_icon="📊", layout="wide")

# --- ESTADO DE LOGIN ---
if 'logado' not in st.session_state:
    st.session_state['logado'] = False

if not st.session_state['logado']:
    # Tela de Login Simples
    col1, col2, col3 = st.columns([1,2,1])
    with col2:
        st.title("🔒 Siarcon Engenharia")
        st.markdown("### Acesso Restrito")
        senha = st.text_input("Senha de Acesso", type="password")
        if st.button("Entrar"):
            if senha == "1234":  # Senha padrão
                st.session_state['logado'] = True
                st.rerun()
            else:
                st.error("Senha incorreta.")
    st.stop()

# --- BARRA LATERAL (CADASTRO) ---
with st.sidebar:
    # Tente carregar o logo se existir, senão usa texto
    try:
        st.image("logo_siarcon.png", width=150)
    except:
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
                utils_db.salvar_projeto(novo)
                st.success("Projeto criado!")
                time.sleep(1)
                st.rerun()
            else:
                st.error("Preencha Cliente e Obra.")

    st.divider()
    if st.button("🔄 Atualizar Painel"):
        st.cache_data.clear()
        st.rerun()

# --- ÁREA PRINCIPAL (KANBAN) ---
st.title("📊 Painel de Projetos")

# Carrega Projetos
try:
    df = utils_db.listar_todos_projetos()
except:
    df = pd.DataFrame()

if df.empty:
    st.info("Nenhum projeto cadastrado.")
else:
    # Garante colunas mínimas
    for c in ['obra', 'cliente', 'disciplina', 'status']:
        if c not in df.columns: df[c] = "-"

    # Colunas do Kanban
    cols = st.columns(4)
    status_map = ["Não Iniciado", "Em Andamento", "Revisão", "Concluído"]
    colors = {"Não Iniciado": "🔴", "Em Andamento": "🟡", "Revisão": "🟠", "Concluído": "🟢"}

    for i, s_nome in enumerate(status_map):
        with cols[i]:
            st.markdown(f"### {colors.get(s_nome, '⚪')} {s_nome}")
            st.divider()
            
            # Filtra projetos do status
            if 'status' in df.columns:
                df_s = df[df['status'] == s_nome]
            else:
                df_s = df if s_nome == "Não Iniciado" else pd.DataFrame()
            
            for idx, row in df_s.iterrows():
                with st.container(border=True):
                    # Tenta pegar 'obra', se não, tenta 'projeto'
                    titulo = row.get('obra', row.get('projeto', 'Sem Nome'))
                    cli = row.get('cliente', '')
                    disc = row.get('disciplina', 'Dutos')
                    
                    st.markdown(f"**{titulo}**")
                    st.caption(f"🏢 {cli} | 🔧 {disc}")
                    
                    # --- BOTÃO DE EDIÇÃO (CORRIGIDO PARA VINCULAR) ---
                    # Usa row.get('_id') ou o índice se não tiver ID
                    uid = row.get('_id', idx)
                    if st.button("✏️ Editar", key=f"edit_{uid}", use_container_width=True):
                        
                        # SALVA NA MEMÓRIA GLOBAL
                        st.session_state['projeto_ativo'] = titulo
                        st.session_state['cliente_ativo'] = cli
                        st.session_state['id_projeto_editar'] = uid
                        st.session_state['logado'] = True
                        
                        # REDIRECIONA
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
