import streamlit as st
import pandas as pd
import utils_db

st.set_page_config(page_title="Dashboard SIARCON", page_icon="📊", layout="wide")

# --- MAPA DE ARQUIVOS (O SEGREDO DOS LINKS) ---
# A Esquerda (Chave): O nome exato que está salvo na Coluna 'Disciplina' da Planilha
# A Direita (Valor): O nome exato do arquivo na pasta 'pages'
MAPA_PAGINAS = {
    # Itens Antigos
    "Geral": "pages/1_❄️_Escopo_Dutos.py",
    
    # Itens Novos
    "Dutos": "pages/1_❄️_Escopo_Dutos.py",
    
    # Atenção aqui: O nome no banco tem acento, o arquivo NÃO tem (padrão de código)
    "Hidráulica": "pages/2_💧_Escopo_Hidraulica.py",
    "Elétrica": "pages/3_⚡_Escopo_Eletrica.py",
    "Automação": "pages/4_🤖_Escopo_Automacao.py",
    "TAB": "pages/5_💨_Escopo_TAB.py",
    "Movimentações": "pages/6_🏗️_Escopo_Movimentacoes.py",
    "Linha de Cobre": "pages/7_🔥_Escopo_Cobre.py"
}

# --- FUNÇÃO DE NAVEGAÇÃO SEGURA ---
def ir_para_edicao(row):
    """Prepara a sessão e redireciona para a página correta"""
    disciplina = row['Disciplina']
    
    # Verifica se existe página para essa disciplina
    if disciplina in MAPA_PAGINAS:
        arquivo_destino = MAPA_PAGINAS[disciplina]
        st.session_state['dados_projeto'] = row.to_dict()
        st.session_state['modo_edicao'] = True
        try:
            st.switch_page(arquivo_destino)
        except Exception as e:
            st.error(f"❌ Erro ao abrir o arquivo: {arquivo_destino}")
            st.caption("Verifique se o nome do arquivo na pasta 'pages' é EXATAMENTE esse.")
    else:
        st.error(f"❌ Disciplina desconhecida: '{disciplina}'. Contate o suporte.")

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
        
        # Seleção múltipla de escopos (Nomes exatos para salvar no banco)
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
    c_filt1, c_filt2 = st.columns(2)
    clientes = ["Todos"] + sorted(list(df['Cliente'].unique()))
    filtro_cliente = c_filt1.selectbox("Filtrar por Cliente:", clientes)
    
    obras = ["Todas"] + sorted(list(df['Obra'].unique()))
    filtro_obra = c_filt2.selectbox("Filtrar por Obra:", obras)
    
    if filtro_cliente != "Todos":
        df = df[df['Cliente'] == filtro_cliente]
    if filtro_obra != "Todas":
        df = df[df['Obra'] == filtro_obra]

    colunas_status = st.columns(3)
    # Grupos do Kanban
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
                    disciplina_display = "Dutos (Antigo)" if row['Disciplina'] == "Geral" else row['Disciplina']
                    st.markdown(f"**{row['Obra']}**")
                    st.caption(f"{row['Cliente']} | {disciplina_display}")
                    
                    # Status Badge
                    st.caption(f"Status: {row['Status']}")
                    
                    # Fornecedor (se tiver)
                    if row['Fornecedor']:
                        st.text(f"🏢 {row['Fornecedor']}")
                    
                    # Botão de Ação (Abre o escopo específico)
                    if st.button(f"✏️ Abrir/Editar", key=f"btn_{row['_id_linha']}"):
                        ir_para_edicao(row)

else:
    st.info("Nenhum projeto encontrado. Crie um novo pacote acima.")
