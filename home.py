import streamlit as st
import pandas as pd
import utils_db
import os

st.set_page_config(page_title="Dashboard SIARCON", page_icon="📊", layout="wide")

# --- MAPA DE ARQUIVOS BLINDADO ---
# Chave: O que está escrito no Excel/Banco de Dados
# Valor: O nome do arquivo SIMPLIFICADO na pasta pages
MAPA_PAGINAS = {
    # Itens Antigos e Novos de Dutos
    "Geral": "pages/1_Dutos.py",
    "Dutos": "pages/1_Dutos.py",
    
    # Demais itens (Nomes no banco -> Arquivo físico)
    "Hidráulica": "pages/2_Hidraulica.py",
    "Elétrica": "pages/3_Eletrica.py",
    "Automação": "pages/4_Automacao.py",
    "TAB": "pages/5_TAB.py",
    "Movimentações": "pages/6_Movimentacoes.py",
    "Linha de Cobre": "pages/7_Cobre.py"
}

# --- FUNÇÃO DE NAVEGAÇÃO ---
def ir_para_edicao(row):
    """Prepara a sessão e redireciona para a página correta"""
    disciplina = row['Disciplina']
    
    if disciplina in MAPA_PAGINAS:
        arquivo_destino = MAPA_PAGINAS[disciplina]
        
        # Verifica se o arquivo realmente existe antes de tentar abrir
        if os.path.exists(arquivo_destino):
            st.session_state['dados_projeto'] = row.to_dict()
            st.session_state['modo_edicao'] = True
            st.switch_page(arquivo_destino)
        else:
            st.error(f"🚨 Arquivo não encontrado: {arquivo_destino}")
            st.info("Verifique se você renomeou o arquivo na pasta 'pages' corretamente (sem emojis/acentos).")
    else:
        st.error(f"❌ Disciplina desconhecida no sistema: '{disciplina}'")

# --- INTERFACE ---
st.title("📊 Dashboard de Contratos")

# 1. Carregar Dados
df = utils_db.listar_todos_projetos()

# 2. Criar Nova Obra
with st.expander("➕ Criar Novo Pacote de Obra"):
    with st.form("form_nova_obra"):
        c1, c2 = st.columns(2)
        novo_cliente = c1.text_input("Cliente")
        nova_obra = c2.text_input("Nome da Obra")
        
        # Nomes exatos que serão salvos no Banco de Dados (com acentos bonitinhos)
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
    lista_clientes = sorted(list(df['Cliente'].unique())) if 'Cliente' in df.columns else []
    lista_obras = sorted(list(df['Obra'].unique())) if 'Obra' in df.columns else []
    
    filtro_cliente = c_filt1.selectbox("Filtrar por Cliente:", ["Todos"] + lista_clientes)
    filtro_obra = c_filt2.selectbox("Filtrar por Obra:", ["Todas"] + lista_obras)
    
    if filtro_cliente != "Todos": df = df[df['Cliente'] == filtro_cliente]
    if filtro_obra != "Todas": df = df[df['Obra'] == filtro_obra]

    colunas_status = st.columns(3)
    grupos = {
        "🔴 A Fazer": ["Não Iniciado", "Aguardando Obras"],
        "🟡 Em Andamento": ["Em Elaboração (Engenharia)", "Recebido (Suprimentos)", "Enviado para Cotação", "Em Negociação"],
        "🟢 Concluído": ["Contratação Finalizada"]
    }

    for i, (grupo_nome, status_grupo) in enumerate(grupos.items()):
        with colunas_status[i]:
            st.markdown(f"### {grupo_nome}")
            df_grupo = df[df['Status'].isin(status_grupo)]
            
            for index, row in df_grupo.iterrows():
                with st.container(border=True):
                    disc_nome = "Dutos (Antigo)" if row['Disciplina'] == "Geral" else row['Disciplina']
                    
                    st.markdown(f"**{row['Obra']}**")
                    st.caption(f"{row['Cliente']} | {disc_nome}")
                    st.caption(f"Status: {row['Status']}")
                    
                    if row['Fornecedor']: st.text(f"🏢 {row['Fornecedor']}")
                    
                    if st.button(f"✏️ Editar", key=f"btn_{row['_id_linha']}"):
                        ir_para_edicao(row)

else:
    st.info("Nenhum projeto encontrado. Crie um novo pacote acima.")
