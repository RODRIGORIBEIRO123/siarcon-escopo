import streamlit as st
import pandas as pd
import utils_db

st.set_page_config(page_title="Dashboard SIARCON", page_icon="📊", layout="wide")

# --- MAPA DE ARQUIVOS (O SEGREDO DOS LINKS) ---
# O nome da chave deve ser EXATAMENTE o que está salvo na coluna 'Disciplina' do Excel/Google Sheets
MAPA_PAGINAS = {
    "Dutos": "pages/1_❄️_Escopo_Dutos.py",
    "Geral": "pages/1_❄️_Escopo_Dutos.py", # Correção para itens antigos salvos como 'Geral'
    "Hidráulica": "pages/2_💧_Escopo_Hidraulica.py",
    "Elétrica": "pages/3_⚡_Escopo_Eletrica.py",
    "Automação": "pages/4_🤖_Escopo_Automacao.py",
    "TAB": "pages/5_💨_Escopo_TAB.py",
    "Movimentações": "pages/6_🏗️_Escopo_Movimentacoes.py",
    "Linha de Cobre": "pages/7_🔥_Escopo_Cobre.py"
}

# --- FUNÇÃO DE NAVEGAÇÃO ---
def ir_para_edicao(row):
    """Prepara a sessão e redireciona para a página correta"""
    disciplina = row['Disciplina']
    
    # Verifica se existe página para essa disciplina
    if disciplina in MAPA_PAGINAS:
        st.session_state['dados_projeto'] = row.to_dict()
        st.session_state['modo_edicao'] = True
        st.switch_page(MAPA_PAGINAS[disciplina])
    else:
        st.error(f"Página não encontrada para a disciplina: {disciplina}")

# --- INTERFACE ---
st.title("📊 Dashboard de Contratos")

# 1. Carregar Dados
df = utils_db.listar_todos_projetos()

# 2. Criar Nova Obra (Botão no Topo)
with st.expander("➕ Criar Novo Pacote de Obra"):
    with st.form("form_nova_obra"):
        c1, c2 = st.columns(2)
        novo_cliente = c1.text_input("Cliente")
        nova_obra = c2.text_input("Nome da Obra")
        
        # Seleção múltipla de escopos
        opcoes_disciplinas = [
            "Dutos", "Hidráulica", "Elétrica", "Automação", 
            "TAB", "Movimentações", "Linha de Cobre"
        ]
        disciplinas_selecionadas = st.multiselect("Quais escopos farão parte?", options=opcoes_disciplinas)
        
        submitted = st.form_submit_button("🚀 Criar Pacote")
        if submitted and novo_cliente and nova_obra and disciplinas_selecionadas:
            if utils_db.criar_pacote_obra(novo_cliente, nova_obra, disciplinas_selecionadas):
                st.success("Pacote criado com sucesso! Atualize a página.")
                st.rerun()
            else:
                st.error("Erro ao criar pacote.")

st.divider()

# 3. Visualização Kanban
if not df.empty:
    # Filtros
    clientes = ["Todos"] + list(df['Cliente'].unique())
    filtro_cliente = st.selectbox("Filtrar por Cliente:", clientes)
    
    if filtro_cliente != "Todos":
        df = df[df['Cliente'] == filtro_cliente]

    colunas_status = st.columns(3)
    status_list = ["Não Iniciado", "Em Elaboração (Engenharia)", "Aguardando Obras", "Recebido (Suprimentos)", "Enviado para Cotação", "Em Negociação", "Contratação Finalizada"]
    
    # Agrupa status para caber em 3 colunas (Kanban simplificado)
    grupos = {
        "🔴 A Fazer": ["Não Iniciado", "Aguardando Obras"],
        "🟡 Em Andamento": ["Em Elaboração (Engenharia)", "Recebido (Suprimentos)", "Enviado para Cotação", "Em Negociação"],
        "🟢 Concluído": ["Contratação Finalizada"]
    }

    for i, (grupo_nome, status_grupo) in enumerate(grupos.items()):
        with colunas_status[i]:
            st.markdown(f"### {grupo_nome}")
            # Filtra o DF para este grupo
            df_grupo = df[df['Status'].isin(status_grupo)]
            
            for index, row in df_grupo.iterrows():
                # Cartão Estilizado
                with st.container(border=True):
                    # Título do Cartão
                    disciplina_display = "Dutos" if row['Disciplina'] == "Geral" else row['Disciplina']
                    st.markdown(f"**{row['Obra']}**")
                    st.caption(f"{row['Cliente']} | {disciplina_display}")
                    
                    # Status Badge
                    st.code(row['Status'], language="text")
                    
                    # Fornecedor (se tiver)
                    if row['Fornecedor']:
                        st.text(f"Forn: {row['Fornecedor']}")
                    
                    # Botão de Ação (Abre o escopo específico)
                    if st.button(f"✏️ Abrir {disciplina_display}", key=f"btn_{row['_id_linha']}"):
                        ir_para_edicao(row)

else:
    st.info("Nenhum projeto encontrado. Crie um novo pacote acima.")
