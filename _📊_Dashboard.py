import streamlit as st
import pandas as pd
import time
from datetime import datetime, date
import utils_db

# ============================================================================
# 1. CONFIGURAÇÕES E ESTILO
# ============================================================================
st.set_page_config(page_title="Painel SIARCON", page_icon="📊", layout="wide")

# CSS para melhorar o visual do Kanban (Cards compactos)
st.markdown("""
<style>
    div[data-testid="stVerticalBlock"] > div[style*="flex-direction: column;"] > div[data-testid="stVerticalBlock"] {
        background-color: #262730;
        padding: 10px;
        border-radius: 5px;
        margin-bottom: 10px;
    }
</style>
""", unsafe_allow_html=True)

if 'logado' not in st.session_state: st.session_state['logado'] = False
if 'usuario_atual' not in st.session_state: st.session_state['usuario_atual'] = ""

# ============================================================================
# 2. LOGIN (CONECTADO AO BANCO)
# ============================================================================
if not st.session_state['logado']:
    col1, col2, col3 = st.columns([1,1,1])
    with col2:
        st.title("🔒 Siarcon Engenharia")
        with st.form("login_form"):
            usuario = st.text_input("Usuário")
            senha = st.text_input("Senha", type="password")
            
            if st.form_submit_button("Entrar"):
                # Valida na planilha
                if utils_db.verificar_login_db(usuario, senha):
                    st.session_state['logado'] = True
                    st.session_state['usuario_atual'] = usuario
                    st.rerun()
                else:
                    st.error("Usuário ou Senha incorretos.")
    st.stop()

# Função de data
def formatar_data_br(valor):
    try:
        if not valor or valor == "-": return "-"
        if isinstance(valor, (datetime, date)): return valor.strftime("%d/%m/%Y")
        return datetime.strptime(str(valor), "%Y-%m-%d").strftime("%d/%m/%Y")
    except: return valor

# ============================================================================
# 3. CABEÇALHO E CADASTRO
# ============================================================================
c1, c2 = st.columns([4, 1])
c1.title("Painel de projetos SIARCON")
c2.info(f"👤 {st.session_state['usuario_atual']}")

with st.expander("➕ Novo Projeto"):
    with st.form("cad_proj", clear_on_submit=True):
        co1, co2 = st.columns(2)
        cli = co1.text_input("Cliente")
        obr = co2.text_input("Obra")
        
        co3, co4 = st.columns(2)
        disc = co3.selectbox("Disciplina", ["Dutos", "Hidráulica", "Elétrica", "Automação", "TAB", "Movimentações", "Cobre"])
        stat = co4.selectbox("Status", ["Não Iniciado", "Engenharia", "Obras", "Suprimentos", "Finalizado"])
        prazo = st.date_input("Prazo", format="DD/MM/YYYY")
        
        if st.form_submit_button("Criar"):
            if cli and obr:
                novo = {
                    "cliente": cli, "obra": obr, "disciplina": disc, "status": stat,
                    "prazo": str(prazo), "criado_por": st.session_state['usuario_atual']
                }
                utils_db.salvar_projeto(novo)
                st.success("Criado!"); time.sleep(1); st.rerun()
            else: st.error("Preencha Cliente e Obra")

st.divider()

# ============================================================================
# 4. KANBAN VISUAL (COLUNAS LADO A LADO)
# ============================================================================
try:
    df = utils_db.listar_todos_projetos()
except:
    df = pd.DataFrame()

# Definição das Colunas do Kanban
status_cols = ["Não Iniciado", "Engenharia", "Obras", "Suprimentos", "Finalizado"]
colunas_tela = st.columns(len(status_cols))
cores = {"Não Iniciado": "🔴", "Engenharia": "🔵", "Obras": "🏗️", "Suprimentos": "📦", "Finalizado": "🟢"}

if df.empty:
    st.info("Nenhum projeto encontrado.")
else:
    # Garante colunas no DF
    for c in ['status', 'obra', 'cliente', 'disciplina']:
        if c not in df.columns: df[c] = ""
    
    # Limpa status
    df['status'] = df['status'].astype(str).str.strip()

    # Loop para criar as 5 colunas VISUAIS
    for i, s_nome in enumerate(status_cols):
        with colunas_tela[i]:
            st.markdown(f"**{cores.get(s_nome,'')} {s_nome}**")
            st.divider()
            
            # Filtra projetos desta coluna
            df_s = df[df['status'] == s_nome]
            
            for idx, row in df_s.iterrows():
                with st.container(border=True):
                    # Dados do Card
                    uid = row.get('_id', idx)
                    tit = row.get('obra', 'Sem Nome')
                    cli_txt = row.get('cliente', '')
                    disc_txt = row.get('disciplina', '')
                    prz = formatar_data_br(row.get('prazo', '-'))
                    
                    st.markdown(f"**{tit}**")
                    st.caption(f"{cli_txt}")
                    st.caption(f"{disc_txt} | {prz}")
                    
                    # Botões de Ação
                    b1, b2, b3, b4 = st.columns([1, 2, 1, 1])
                    
                    # Esquerda
                    if i > 0:
                        if b1.button("⬅️", key=f"L_{uid}"):
                            row['status'] = status_cols[i-1]
                            utils_db.salvar_projeto(row.to_dict())
                            st.rerun()
                    
                    # Abrir
                    if b2.button("✏️", key=f"E_{uid}", use_container_width=True):
                        st.session_state['projeto_ativo'] = tit
                        st.session_state['cliente_ativo'] = cli_txt
                        st.session_state['id_projeto_editar'] = uid
                        st.session_state['logado'] = True
                        
                        rotas = {
                            "Dutos": "pages/1_Dutos.py", "Hidráulica": "pages/2_Hidráulica.py",
                            "Elétrica": "pages/3_Elétrica.py", "Automação": "pages/4_Automação.py",
                            "TAB": "pages/5_TAB.py", "Movimentações": "pages/6_Movimentações.py",
                            "Cobre": "pages/7_Cobre.py"
                        }
                        st.switch_page(rotas.get(disc_txt, "pages/1_Dutos.py"))
                    
                    # Excluir
                    if b3.button("🗑️", key=f"D_{uid}"):
                        utils_db.excluir_projeto(uid)
                        st.rerun()

                    # Direita
                    if i < len(status_cols)-1:
                        if b4.button("➡️", key=f"R_{uid}"):
                            row['status'] = status_cols[i+1]
                            utils_db.salvar_projeto(row.to_dict())
                            st.rerun()

st.divider()
if st.button("🔄 Atualizar Quadro"):
    st.cache_data.clear()
    st.rerun()
