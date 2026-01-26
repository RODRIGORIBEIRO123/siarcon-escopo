import streamlit as st
import pandas as pd
import utils_db
import os

st.set_page_config(page_title="Dashboard SIARCON", page_icon="📊", layout="wide")

# ==================================================
# 🔍 DIAGNÓSTICO (PARA VOCÊ COPIAR OS NOMES CERTOS)
# ==================================================
with st.sidebar:
    st.header("🔧 Debug: Arquivos Reais")
    st.info("Copie os nomes abaixo se os links falharem:")
    try:
        arquivos_na_pasta = sorted(os.listdir("pages"))
        for arq in arquivos_na_pasta:
            if arq.endswith(".py"):
                st.code(f"pages/{arq}", language="text")
    except:
        st.error("Não achei a pasta 'pages'")
    st.divider()

# ==================================================
# 🗺️ MAPA DE NAVEGAÇÃO
# ==================================================
# ESQUERDA: O que está escrito na Coluna 'Disciplina' do Google Sheets/Excel
# DIREITA: O nome EXATO do arquivo que apareceu no Debug acima
MAPA_PAGINAS = {
    # Dutos
    "Geral": "pages/1_❄️_Escopo_Dutos.py",
    "Dutos": "pages/1_❄️_Escopo_Dutos.py",
    
    # Hidráulica
    "Hidráulica": "pages/2_💧_Escopo_Hidraulica.py",
    
    # Elétrica
    "Elétrica": "pages/3_⚡_Escopo_Eletrica.py",
    
    # Automação
    "Automação": "pages/4_🤖_Escopo_Automacao.py",
    
    # TAB
    "TAB": "pages/5_💨_Escopo_TAB.py",
    
    # Movimentações
    "Movimentações": "pages/6_🏗️_Escopo_Movimentacoes.py",
    
    # Linha de Cobre
    "Linha de Cobre": "pages/7_🔥_Escopo_Cobre.py"
}

# --- FUNÇÃO DE NAVEGAÇÃO ---
def ir_para_edicao(row):
    disciplina = row['Disciplina']
    
    # 1. Verifica se a disciplina está no mapa
    if disciplina in MAPA_PAGINAS:
        arquivo_destino = MAPA_PAGINAS[disciplina]
        
        # 2. Verifica se o arquivo existe fisicamente antes de tentar abrir
        if os.path.exists(arquivo_destino):
            st.session_state['dados_projeto'] = row.to_dict()
            st.session_state['modo_edicao'] = True
            st.switch_page(arquivo_destino)
        else:
            st.error(f"⛔ ERRO DE ARQUIVO: O código tentou abrir '{arquivo_destino}', mas ele não existe.")
            st.warning("👉 Olhe a barra lateral esquerda (Debug). Veja qual é o nome real do arquivo e corrija no 'MAPA_PAGINAS' dentro do Home.py")
    else:
        st.error(f"❌ Disciplina '{disciplina}' não está mapeada.")
        st.info(f"Adicione '{disciplina}' no MAPA_PAGINAS no código.")

# --- INTERFACE ---
st.title("📊 Dashboard de Contratos")

# Carregar Dados
df = utils_db.listar_todos_projetos()

# Criar Nova Obra
with st.expander("➕ Criar Novo Pacote de Obra"):
    with st.form("form_nova_obra"):
        c1, c2 = st.columns(2)
        novo_cliente = c1.text_input("Cliente")
        nova_obra = c2.text_input("Nome da Obra")
        
        # Opções devem bater com as chaves do MAPA_PAGINAS
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
    # Filtros
    c_filt1, c_filt2 = st.columns(2)
    lista_clientes = sorted(list(df['Cliente'].unique())) if 'Cliente' in df.columns else []
    filtro_cliente = c_filt1.selectbox("Filtrar Cliente:", ["Todos"] + lista_clientes)
    
    if filtro_cliente != "Todos": 
        df = df[df['Cliente'] == filtro_cliente]

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
                    # Exibe nome amigável se for o antigo "Geral"
                    disc_show = "Dutos (Legado)" if row['Disciplina'] == "Geral" else row['Disciplina']
                    
                    st.markdown(f"**{row['Obra']}**")
                    st.caption(f"{row['Cliente']} | {disc_show}")
                    
                    if row['Fornecedor']: st.text(f"🏢 {row['Fornecedor']}")
                    
                    if st.button(f"✏️ Editar", key=f"btn_{row['_id_linha']}"):
                        ir_para_edicao(row)
else:
    st.info("Nenhum projeto encontrado.")
