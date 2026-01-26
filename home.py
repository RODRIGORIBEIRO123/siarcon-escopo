import streamlit as st
import pandas as pd
import utils_db
import os

st.set_page_config(page_title="Dashboard SIARCON", page_icon="📊", layout="wide")

# --- 🔍 FERRAMENTA DE DIAGNÓSTICO (MENU LATERAL) ---
with st.sidebar:
    st.header("🔍 Diagnóstico de Arquivos")
    st.caption("O sistema está enxergando estes arquivos na pasta 'pages':")
    try:
        arquivos = os.listdir("pages")
        for arq in arquivos:
            if arq.endswith(".py"):
                st.code(arq, language="text")
    except Exception as e:
        st.error(f"Não foi possível ler a pasta pages: {e}")
    st.divider()

# --- MAPA DE ARQUIVOS (NOMES SIMPLIFICADOS) ---
# A chave deve ser EXATAMENTE como está no seu Excel (Coluna Disciplina)
MAPA_PAGINAS = {
    # Variações de Dutos
    "Geral": "pages/dutos.py",
    "Dutos": "pages/dutos.py",
    
    # Demais itens (tudo minúsculo agora)
    "Hidráulica": "pages/hidraulica.py",
    "Elétrica": "pages/eletrica.py",
    "Automação": "pages/automacao.py",
    "TAB": "pages/tab.py",
    "Movimentações": "pages/movimentacoes.py",
    "Linha de Cobre": "pages/cobre.py"
}

# --- FUNÇÃO DE NAVEGAÇÃO SEGURA ---
def ir_para_edicao(row):
    disciplina = row['Disciplina']
    
    # 1. Tenta encontrar no mapa
    if disciplina in MAPA_PAGINAS:
        arquivo_destino = MAPA_PAGINAS[disciplina]
        
        # 2. Verifica se o arquivo realmente existe fisicamente
        if os.path.exists(arquivo_destino):
            st.session_state['dados_projeto'] = row.to_dict()
            st.session_state['modo_edicao'] = True
            st.switch_page(arquivo_destino)
        else:
            st.error(f"⛔ ERRO CRÍTICO: O sistema tentou abrir '{arquivo_destino}', mas esse arquivo não existe na pasta 'pages'.")
            st.info("Verifique a lista de arquivos na barra lateral esquerda.")
    else:
        st.error(f"❌ A disciplina '{disciplina}' não está cadastrada no MAPA_PAGINAS.")

# --- INTERFACE ---
st.title("📊 Dashboard de Contratos")

df = utils_db.listar_todos_projetos()

# Criar Nova Obra
with st.expander("➕ Criar Novo Pacote de Obra"):
    with st.form("form_nova_obra"):
        c1, c2 = st.columns(2)
        novo_cliente = c1.text_input("Cliente")
        nova_obra = c2.text_input("Nome da Obra")
        
        opcoes_disciplinas = [
            "Dutos", "Hidráulica", "Elétrica", "Automação", 
            "TAB", "Movimentações", "Linha de Cobre"
        ]
        disciplinas_selecionadas = st.multiselect("Quais escopos farão parte?", options=opcoes_disciplinas)
        
        if st.form_submit_button("🚀 Criar Pacote"):
            if utils_db.criar_pacote_obra(novo_cliente, nova_obra, disciplinas_selecionadas):
                st.success("Criado! Atualize a página."); st.rerun()
            else: st.error("Erro ao criar.")

st.divider()

# Kanban
if not df.empty:
    c_filt1, c_filt2 = st.columns(2)
    lista_clientes = sorted(list(df['Cliente'].unique())) if 'Cliente' in df.columns else []
    lista_obras = sorted(list(df['Obra'].unique())) if 'Obra' in df.columns else []
    
    filtro_cliente = c_filt1.selectbox("Filtrar Cliente:", ["Todos"] + lista_clientes)
    filtro_obra = c_filt2.selectbox("Filtrar Obra:", ["Todas"] + lista_obras)
    
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
                    # Mostra o nome real que está no banco para debug
                    disc_real = row['Disciplina']
                    
                    st.markdown(f"**{row['Obra']}**")
                    st.caption(f"{row['Cliente']} | {disc_real}")
                    
                    if row['Fornecedor']: st.text(f"🏢 {row['Fornecedor']}")
                    
                    if st.button(f"✏️ Editar", key=f"btn_{row['_id_linha']}"):
                        ir_para_edicao(row)
else:
    st.info("Nenhum projeto encontrado.")
