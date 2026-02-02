import streamlit as st
import pandas as pd
import utils_db
from datetime import datetime, timedelta
import os
import time

# Configuração da Página (DEVE SER A PRIMEIRA LINHA)
st.set_page_config(page_title="SIARCON", page_icon="📊", layout="wide")

# ============================================================================
# 🔐 LÓGICA DE LOGIN (VERSÃO ESTÁVEL - SEM COOKIES)
# ============================================================================
if 'logado' not in st.session_state:
    st.session_state['logado'] = False
if 'usuario_atual' not in st.session_state:
    st.session_state['usuario_atual'] = ""

# SE NÃO ESTIVER LOGADO, MOSTRA TELA DE LOGIN
if not st.session_state['logado']:
    # Oculta sidebar na tela de login
    st.markdown("""<style>[data-testid="stSidebar"] {display: none;}</style>""", unsafe_allow_html=True)

    c_vazio1, c_login, c_vazio2 = st.columns([1, 1, 1])
    
    with c_login:
        st.markdown("<br><br>", unsafe_allow_html=True)
        # Tenta carregar o logo
        if os.path.exists("Siarcon.png"):
            st.image("Siarcon.png", width=200)
        elif os.path.exists("siarcon.png"):
            st.image("siarcon.png", width=200)
        else:
            st.header("🏢 SIARCON")
            
        st.markdown("### 🔒 Acesso Restrito")
        st.markdown("Entre com suas credenciais.")
        
        usuario = st.text_input("Usuário")
        senha = st.text_input("Senha", type="password")
        
        if st.button("Entrar 🚀", type="primary", use_container_width=True):
            with st.spinner("Verificando..."):
                sucesso, mensagem = utils_db.verificar_login(usuario, senha)
                if sucesso:
                    st.session_state['logado'] = True
                    st.session_state['usuario_atual'] = mensagem
                    st.success(f"Bem-vindo, {mensagem}!")
                    time.sleep(0.5)
                    st.rerun()
                else:
                    st.error(mensagem)
    
    st.stop() # Bloqueia o resto do código se não logar

# ============================================================================
# 🔓 ÁREA LOGADA (DASHBOARD)
# ============================================================================

# -- CABEÇALHO --
c_logo, c_tit, c_user = st.columns([1, 6, 2])
with c_logo:
    if os.path.exists("Siarcon.png"): st.image("Siarcon.png", width=120)
    elif os.path.exists("siarcon.png"): st.image("siarcon.png", width=120)
    else: st.write("🏢 **SIARCON**")
with c_tit:
    st.title("Gestão de Projetos")
with c_user:
    st.markdown(f"<div style='text-align: right;'>👤 <b>{st.session_state['usuario_atual']}</b></div>", unsafe_allow_html=True)
    
    if st.button("Sair (Logout)", key="btn_logout"):
        st.session_state['logado'] = False
        st.session_state['usuario_atual'] = ""
        st.rerun()

# --- MAPEAMENTO DE PÁGINAS ---
PAGINAS_DISCIPLINAS = {
    "Dutos": "pages/1_Dutos.py",
    "Hidráulica": "pages/2_Hidráulica.py", "Hidraulica": "pages/2_Hidráulica.py",
    "Elétrica": "pages/3_Elétrica.py", "Eletrica": "pages/3_Elétrica.py",
    "Automação": "pages/4_Automação.py", "Automacao": "pages/4_Automação.py",
    "TAB": "pages/5_TAB.py",
    "Movimentações": "pages/6_Movimentações.py", "Movimentacoes": "pages/6_Movimentações.py",
    "Cobre": "pages/7_Cobre.py"
}

# --- 1. ÁREA DE CRIAÇÃO ---
with st.expander("➕ CADASTRAR NOVO PROJETO", expanded=False):
    c1, c2, c3 = st.columns([2, 2, 3])
    novo_cliente = c1.text_input("Nome do Cliente")
    nova_obra = c2.text_input("Nome da Obra")
    
    opcoes_visualizacao = ["Dutos", "Hidráulica", "Elétrica", "Automação", "TAB", "Movimentações", "Cobre"]
    disciplinas_selecionadas = c3.multiselect("Disciplinas do Escopo:", options=opcoes_visualizacao)
    
    if st.button("🚀 CRIAR PROJETOS", type="primary"):
        if not novo_cliente or not nova_obra or not disciplinas_selecionadas:
            st.error("Preencha todos os campos.")
        else:
            count = 0
            for i, disc in enumerate(disciplinas_selecionadas):
                dados_novo = {
                    '_id': f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{i}",
                    'status': 'Não Iniciado',
                    'disciplina': disc,
                    'cliente': novo_cliente,
                    'obra': nova_obra,
                    'fornecedor': '',
                    'valor_total': '',
                    'data_inicio': datetime.now().strftime("%Y-%m-%d"),
                    'criado_por': st.session_state['usuario_atual']
                }
                utils_db.registrar_projeto(dados_novo)
                count += 1
            st.success(f"{count} projetos criados!"); st.cache_data.clear(); st.rerun()

st.divider()

# --- 2. KANBAN ---
if st.button("🔄 Atualizar Quadro"):
    st.cache_data.clear(); st.rerun()

df = utils_db.listar_todos_projetos()

if df.empty:
    st.info("Nenhum projeto encontrado.")
else:
    col1, col2, col3, col4, col5 = st.columns(5)
    
    def botao_editar(row):
        # --- DIAGNÓSTICO (Opcional: removemos depois) ---
        # Se quiser ver os nomes das colunas na tela, descomente a linha abaixo:
        # st.caption(f"Colunas disponíveis: {list(row.keys())}")
        
        if st.button("✏️", key=f"edit_{row.get('_id', 'novo')}", help="Editar Escopo"):
            
            # 1. TENTA PEGAR A OBRA (PRIORIDADE PARA 'obra')
            # O .get() evita que o sistema trave se a coluna não existir
            nome_obra = row.get('obra', row.get('projeto', 'Projeto Sem Nome'))
            
            # 2. TENTA PEGAR O CLIENTE
            nome_cliente = row.get('cliente', 'Cliente Não Identificado')
            
            # 3. SALVA NA MEMÓRIA (SESSION STATE)
            st.session_state['projeto_ativo'] = nome_obra
            st.session_state['cliente_ativo'] = nome_cliente
            st.session_state['id_projeto_editar'] = row.get('_id')
            st.session_state['logado'] = True 
            
            # 4. REDIRECIONAMENTO
            disc_banco = row.get('disciplina', 'Dutos') # Padrão Dutos se falhar
            
            PAGINAS = {
                "Dutos": "pages/1_Dutos.py",
                "Hidráulica": "pages/2_Hidráulica.py",
                "Elétrica": "pages/3_Elétrica.py",
                "Automação": "pages/4_Automação.py",
                "TAB": "pages/5_TAB.py",
                "Movimentações": "pages/6_Movimentações.py",
                "Cobre": "pages/7_Cobre.py"
            }

            destino = PAGINAS.get(disc_banco)
            
            if destino:
                st.switch_page(destino)
            else:
                st.error(f"Página não encontrada para: {disc_banco}")
            
            PAGINAS = {
                "Dutos": "pages/1_Dutos.py",
                "Hidráulica": "pages/2_Hidráulica.py",
                "Elétrica": "pages/3_Elétrica.py",
                "Automação": "pages/4_Automação.py",
                "TAB": "pages/5_TAB.py",
                "Movimentações": "pages/6_Movimentações.py",
                "Cobre": "pages/7_Cobre.py"
            }

            destino = PAGINAS.get(disc_banco)
            
            if destino:
                st.switch_page(destino)
            else:
                st.error(f"Página não encontrada para: {disc_banco}")
        
        if pagina_destino:
            st.switch_page(pagina_destino)
        else:
            st.error(f"Página não encontrada para a disciplina: {disc_banco}")

    # --- COLUNAS ---
    with col1:
        st.markdown("### 💤 Não Iniciado")
        for idx, row in df[df['status'] == 'Não Iniciado'].iterrows():
            with st.container(border=True):
                c_tit, c_edit = st.columns([4, 1])
                c_tit.write(f"**{row['disciplina']} | {row['obra']}**")
                with c_edit: botao_editar(row)
                st.caption(row['cliente'])
                if st.button("Iniciar (Eng) ➡️", key=f"start_{row['_id']}"):
                    utils_db.atualizar_status_projeto(row['_id'], "Em Elaboração")
                    st.cache_data.clear(); st.rerun()

    with col2:
        st.markdown("### 👷 Engenharia")
        st.caption("(Definição Técnica)")
        for idx, row in df[df['status'] == 'Em Elaboração'].iterrows():
            with st.container(border=True):
                c_tit, c_edit = st.columns([4, 1])
                c_tit.info(f"**{row['disciplina']} | {row['obra']}**")
                with c_edit: botao_editar(row)
                st.caption(row['cliente'])
                if st.button("Validar (Obras) ➡️", key=f"to_obras_{row['_id']}"):
                    utils_db.atualizar_status_projeto(row['_id'], "Em Análise Obras")
                    st.cache_data.clear(); st.rerun()

    with col3:
        st.markdown("### 🏗️ Obras")
        st.caption("(Validação Campo)")
        for idx, row in df[df['status'] == 'Em Análise Obras'].iterrows():
            with st.container(border=True):
                c_tit, c_edit = st.columns([4, 1])
                c_tit.warning(f"**{row['disciplina']} | {row['obra']}**")
                with c_edit: botao_editar(row)
                st.caption(row['cliente'])
                c_v, c_i = st.columns(2)
                if c_v.button("⬅️ Eng", key=f"bk_eng_{row['_id']}"):
                    utils_db.atualizar_status_projeto(row['_id'], "Em Elaboração"); st.cache_data.clear(); st.rerun()
                if c_i.button("Sup ➡️", key=f"go_sup_{row['_id']}"):
                    utils_db.atualizar_status_projeto(row['_id'], "Em Cotação"); st.cache_data.clear(); st.rerun()

    with col4:
        st.markdown("### 💰 Suprimentos")
        st.caption("(Cotação/Compra)")
        for idx, row in df[df['status'] == 'Em Cotação'].iterrows():
            with st.container(border=True):
                c_tit, c_edit = st.columns([4, 1])
                c_tit.error(f"**{row['disciplina']} | {row['obra']}**")
                with c_edit: botao_editar(row)
                st.caption(row['cliente'])
                if row['fornecedor']: st.write(f"🏢 {row['fornecedor']}")
                if row['valor_total']: st.write(f"💲 {row['valor_total']}")
                c_v1, c_v2 = st.columns(2)
                if c_v1.button("⬅️ Eng", key=f"r_eng_{row['_id']}"):
                    utils_db.atualizar_status_projeto(row['_id'], "Em Elaboração"); st.cache_data.clear(); st.rerun()
                if c_v2.button("⬅️ Obras", key=f"r_obr_{row['_id']}"):
                    utils_db.atualizar_status_projeto(row['_id'], "Em Análise Obras"); st.cache_data.clear(); st.rerun()
                if st.button("✅ Concluir", key=f"fin_{row['_id']}", type="primary"):
                    utils_db.atualizar_status_projeto(row['_id'], "Concluído"); st.cache_data.clear(); st.rerun()

    with col5:
        st.markdown("### ✅ Concluído")
        for idx, row in df[df['status'] == 'Concluído'].iterrows():
            with st.expander(f"{row['disciplina']} | {row['obra']}"):
                st.write(f"Cliente: {row['cliente']}")
                st.success(f"Forn: {row['fornecedor']}")
                st.write(f"Valor: {row['valor_total']}")
                botao_editar(row)
