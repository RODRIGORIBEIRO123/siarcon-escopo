import streamlit as st
import pandas as pd
import time
from datetime import datetime
import utils_db  # Certifique-se que este arquivo existe na mesma pasta

# ============================================================================
# 1. CONFIGURAÇÕES INICIAIS
# ============================================================================
st.set_page_config(page_title="Dashboard de Projetos", page_icon="📊", layout="wide")

# Inicializa variáveis de sessão essenciais
if 'logado' not in st.session_state:
    st.session_state['logado'] = False

# (Opcional) Tela de Login Simples
# Se quiser remover o login, apague ou comente as linhas abaixo até o 'st.stop()'
if not st.session_state['logado']:
    col1, col2, col3 = st.columns([1,2,1])
    with col2:
        st.title("🔒 Acesso Restrito")
        senha = st.text_input("Senha de Acesso", type="password")
        if st.button("Entrar"):
            if senha == "1234":  # Senha padrão
                st.session_state['logado'] = True
                st.rerun()
            else:
                st.error("Senha incorreta")
    st.stop()

# ============================================================================
# 2. BARRA LATERAL - CADASTRO DE NOVO PROJETO
# ============================================================================
with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/1087/1087815.png", width=50)
    st.title("Siarcon Engenharia")
    st.divider()
    
    st.header("➕ Novo Projeto")
    
    with st.form("form_novo_projeto", clear_on_submit=True):
        cliente = st.text_input("Cliente:", placeholder="Ex: Farmacêutica XYZ")
        obra = st.text_input("Nome da Obra/Projeto:", placeholder="Ex: Retrofit HVAC")
        
        c1, c2 = st.columns(2)
        disciplina = c1.selectbox("Disciplina:", [
            "Dutos", "Hidráulica", "Elétrica", 
            "Automação", "TAB", "Movimentações", "Cobre"
        ])
        status = c2.selectbox("Status Inicial:", ["Não Iniciado", "Em Andamento"])
        
        responsavel = st.text_input("Responsável:", value="Engenharia")
        prazo = st.date_input("Prazo de Entrega:")
        
        btn_criar = st.form_submit_button("🚀 Criar Projeto")
        
        if btn_criar:
            if not cliente or not obra:
                st.error("Preencha Cliente e Nome da Obra!")
            else:
                novo_projeto = {
                    "data_criacao": datetime.now().strftime("%Y-%m-%d %H:%M"),
                    "cliente": cliente,
                    "obra": obra,
                    "disciplina": disciplina,
                    "status": status,
                    "responsavel": responsavel,
                    "prazo": str(prazo)
                }
                
                # Salva no banco (função do seu arquivo utils_db.py)
                utils_db.salvar_projeto(novo_projeto)
                
                st.success("Projeto criado com sucesso!")
                time.sleep(1)
                st.rerun()

    st.divider()
    if st.button("🔄 Atualizar Painel"):
        st.cache_data.clear()
        st.rerun()

# ============================================================================
# 3. ÁREA PRINCIPAL - KANBAN
# ============================================================================
st.title("📊 Painel de Controle de Projetos")

# Carrega dados do banco de dados
try:
    df = utils_db.listar_todos_projetos()
except Exception as e:
    st.error(f"Erro ao ler banco de dados: {e}")
    df = pd.DataFrame() # Cria vazio para não travar

if df.empty:
    st.info("Nenhum projeto encontrado. Cadastre o primeiro na barra lateral!")
else:
    # Filtros de visualização
    col_filtro1, col_filtro2 = st.columns(2)
    
    # Tratamento para evitar erro se a coluna 'cliente' não existir
    lista_clientes = df['cliente'].unique() if 'cliente' in df.columns else []
    filtro_cliente = col_filtro1.multiselect("Filtrar por Cliente:", options=lista_clientes)
    
    if filtro_cliente:
        df = df[df['cliente'].isin(filtro_cliente)]

    st.divider()

    # --- FUNÇÃO DO BOTÃO (CORRIGIDA E BLINDADA) ---
    def renderizar_botao_editar(row):
        # Gera uma chave única usando ID ou índice para não dar conflito
        id_unico = row.get('_id', row.name) # row.name pega o index se não tiver _id
        key_btn = f"btn_edit_{id_unico}"
        
        if st.button("✏️ Editar Escopo", key=key_btn, use_container_width=True):
            # 1. Captura os dados com segurança (Proteção contra colunas com nomes errados)
            # Tenta pegar 'obra', se não achar tenta 'projeto', se não achar põe 'Sem Nome'
            projeto_nome = row.get('obra', row.get('projeto', 'Sem Nome'))
            cliente_nome = row.get('cliente', 'Cliente Não Informado')
            projeto_id = str(id_unico)
            disc_alvo = row.get('disciplina', 'Dutos')

            # 2. Salva na Memória Global (Session State)
            st.session_state['projeto_ativo'] = projeto_nome
            st.session_state['cliente_ativo'] = cliente_nome
            st.session_state['id_projeto_editar'] = projeto_id
            st.session_state['logado'] = True
            
            # 3. Define para onde ir
            rotas = {
                "Dutos": "pages/1_Dutos.py",
                "Hidráulica": "pages/2_Hidráulica.py",
                "Elétrica": "pages/3_Elétrica.py",
                "Automação": "pages/4_Automação.py",
                "TAB": "pages/5_TAB.py",
                "Movimentações": "pages/6_Movimentações.py",
                "Cobre": "pages/7_Cobre.py"
            }
            
            destino = rotas.get(disc_alvo, "pages/1_Dutos.py")
            
            # 4. Navega
            st.switch_page(destino)

    # --- DESENHO DO KANBAN ---
    cols = st.columns(4)
    status_list = ["Não Iniciado", "Em Andamento", "Revisão", "Concluído"]
    cores = {"Não Iniciado": "🔴", "Em Andamento": "🟡", "Revisão": "🟠", "Concluído": "🟢"}

    for i, status_nome in enumerate(status_list):
        with cols[i]:
            st.markdown(f"### {cores[status_nome]} {status_nome}")
            st.divider()
            
            # Filtra projetos deste status
            if 'status' in df.columns:
                df_status = df[df['status'] == status_nome]
            else:
                # Se não tiver coluna status, joga tudo em 'Não Iniciado'
                df_status = df if status_nome == "Não Iniciado" else pd.DataFrame()

            for idx, row in df_status.iterrows():
                with st.container(border=True):
                    # Tenta pegar 'obra', se não der pega 'projeto'
                    titulo = row.get('obra', row.get('projeto', 'Sem Título'))
                    cliente_txt = row.get('cliente', 'Sem Cliente')
                    disc_txt = row.get('disciplina', '-')
                    
                    st.markdown(f"**{titulo}**")
                    st.caption(f"🏢 {cliente_txt}")
                    st.caption(f"🔧 {disc_txt}")
                    
                    # Chama o botão corrigido
                    renderizar_botao_editar(row)
