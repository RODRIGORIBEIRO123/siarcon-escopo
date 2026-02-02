import streamlit as st
import pandas as pd
import time
from datetime import datetime

# ============================================================================
# 1. CONFIGURAÇÃO OBRIGATÓRIA (PRIMEIRA LINHA)
# ============================================================================
st.set_page_config(page_title="Dashboard Siarcon", page_icon="📊", layout="wide")

# ============================================================================
# 2. TENTATIVA DE CONEXÃO COM BANCO DE DADOS
# ============================================================================
# Tenta importar seu arquivo. Se der erro, usa uma função provisória para não travar a tela.
try:
    import utils_db
    CONEXAO_DB = True
except ImportError:
    CONEXAO_DB = False
    st.error("⚠️ Arquivo 'utils_db.py' não encontrado. Usando modo de teste.")

# Função segura para listar projetos
def listar_projetos_seguro():
    if CONEXAO_DB:
        try:
            dados = utils_db.listar_todos_projetos()
            return pd.DataFrame(dados) # Garante que seja DataFrame
        except Exception as e:
            st.error(f"Erro ao ler banco de dados real: {e}")
            return pd.DataFrame() # Retorna vazio se der erro
    else:
        # Dados de teste para quando o sistema não consegue ler o banco
        return pd.DataFrame([
            {"_id": 1, "obra": "Obra Teste 1", "cliente": "Cliente A", "disciplina": "Dutos", "status": "Em Andamento"},
            {"_id": 2, "obra": "Obra Teste 2", "cliente": "Cliente B", "disciplina": "Hidráulica", "status": "Não Iniciado"},
        ])

# Função segura para salvar
def salvar_projeto_seguro(novo_projeto):
    if CONEXAO_DB:
        try:
            utils_db.salvar_projeto(novo_projeto)
            return True
        except Exception as e:
            st.error(f"Erro ao salvar no banco: {e}")
            return False
    else:
        st.warning("Modo de teste: O projeto não foi salvo no banco real.")
        return True

# ============================================================================
# 3. LÓGICA DE LOGIN
# ============================================================================
if 'logado' not in st.session_state:
    st.session_state['logado'] = False

# Se quiser remover o login, comente as linhas abaixo
if not st.session_state['logado']:
    col1, col2, col3 = st.columns([1,2,1])
    with col2:
        st.title("🔒 Acesso Restrito")
        senha = st.text_input("Senha", type="password")
        if st.button("Entrar"):
            if senha == "1234":
                st.session_state['logado'] = True
                st.rerun()
            else:
                st.error("Senha incorreta")
    st.stop()

# ============================================================================
# 4. BARRA LATERAL (CADASTRO)
# ============================================================================
with st.sidebar:
    st.title("Siarcon Engenharia")
    st.divider()
    
    st.header("➕ Novo Projeto")
    
    with st.form("form_novo_projeto", clear_on_submit=True):
        cliente = st.text_input("Cliente:", placeholder="Ex: Farmacêutica XYZ")
        obra = st.text_input("Nome da Obra:", placeholder="Ex: Retrofit HVAC")
        
        c1, c2 = st.columns(2)
        disciplina = c1.selectbox("Disciplina:", ["Dutos", "Hidráulica", "Elétrica", "Automação", "TAB", "Movimentações", "Cobre"])
        status = c2.selectbox("Status:", ["Não Iniciado", "Em Andamento"])
        
        responsavel = st.text_input("Responsável:", value="Engenharia")
        prazo = st.date_input("Prazo:")
        
        if st.form_submit_button("🚀 Criar Projeto"):
            if not cliente or not obra:
                st.error("Preencha Cliente e Obra!")
            else:
                novo = {
                    "data_criacao": datetime.now().strftime("%Y-%m-%d %H:%M"),
                    "cliente": cliente,
                    "obra": obra,
                    "disciplina": disciplina,
                    "status": status,
                    "responsavel": responsavel,
                    "prazo": str(prazo)
                }
                if salvar_projeto_seguro(novo):
                    st.success("Sucesso!")
                    time.sleep(1)
                    st.rerun()
    
    st.divider()
    if st.button("🔄 Recarregar Sistema"):
        st.cache_data.clear()
        st.rerun()

# ============================================================================
# 5. KANBAN (ÁREA PRINCIPAL)
# ============================================================================
st.title("📊 Painel de Controle")

# Carrega dados
df = listar_projetos_seguro()

if df.empty:
    st.info("Nenhum projeto encontrado.")
else:
    # Garante que as colunas essenciais existam para não dar erro
    for col in ['obra', 'cliente', 'disciplina', 'status']:
        if col not in df.columns:
            df[col] = " - " # Preenche com traço se faltar coluna

    # Filtros
    clientes = df['cliente'].unique()
    filtro = st.multiselect("Filtrar Cliente:", clientes)
    if filtro:
        df = df[df['cliente'].isin(filtro)]

    st.divider()

    # Layout de Colunas
    cols = st.columns(4)
    status_map = ["Não Iniciado", "Em Andamento", "Revisão", "Concluído"]
    colors = {"Não Iniciado": "🔴", "Em Andamento": "🟡", "Revisão": "🟠", "Concluído": "🟢"}

    for i, s_nome in enumerate(status_map):
        with cols[i]:
            st.markdown(f"### {colors.get(s_nome, '⚪')} {s_nome}")
            st.divider()
            
            df_s = df[df['status'] == s_nome]
            
            for idx, row in df_s.iterrows():
                with st.container(border=True):
                    # Exibe dados (usando .get para segurança)
                    st.markdown(f"**{row.get('obra', 'Sem Nome')}**")
                    st.caption(f"🏢 {row.get('cliente', '')}")
                    st.caption(f"🔧 {row.get('disciplina', '')}")
                    
                    # --- BOTÃO DE EDIÇÃO (CORRIGIDO) ---
                    key_btn = f"btn_{row.get('_id', idx)}"
                    if st.button("✏️ Editar", key=key_btn, use_container_width=True):
                        # Salva na memória
                        st.session_state['projeto_ativo'] = row.get('obra')
                        st.session_state['cliente_ativo'] = row.get('cliente')
                        st.session_state['id_projeto_editar'] = row.get('_id')
                        st.session_state['logado'] = True
                        
                        # Define destino
                        disc = row.get('disciplina', 'Dutos')
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
