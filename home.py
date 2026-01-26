import streamlit as st
import pandas as pd
import utils_db
import os

st.set_page_config(page_title="Dashboard SIARCON", page_icon="📊", layout="wide")

# =========================================================
# 🗺️ MAPA DEFINITIVO DE NAVEGAÇÃO
# =========================================================
# A Esquerda: O nome da Disciplina que está salva no Banco de Dados
# A Direita: O caminho EXATO do arquivo que você padronizou
MAPA_PAGINAS = {
    # Caso Dutos (antigo Geral e novo Dutos)
    "Geral": "pages/1_Dutos.py",
    "Dutos": "pages/1_Dutos.py",
    
    # Demais casos (Nomes do Banco -> Arquivos sem acento)
    "Hidráulica": "pages/2_Hidraulica.py",
    "Elétrica": "pages/3_Eletrica.py",
    "Automação": "pages/4_Automacao.py",
    "TAB": "pages/5_TAB.py",
    "Movimentações": "pages/6_Movimentacoes.py",
    "Linha de Cobre": "pages/7_Cobre.py"
}

# --- FUNÇÃO DE NAVEGAÇÃO ---
def ir_para_edicao(row):
    disciplina = row['Disciplina']
    
    # 1. Verifica se a disciplina existe no mapa
    if disciplina in MAPA_PAGINAS:
        arquivo_destino = MAPA_PAGINAS[disciplina]
        
        # 2. Salva os dados na memória (Sessão)
        st.session_state['dados_projeto'] = row.to_dict()
        st.session_state['modo_edicao'] = True
        
        # 3. Tenta pular para a página
        try:
            st.switch_page(arquivo_destino)
        except Exception as e:
            # Se der erro, mostra uma mensagem clara
            st.error(f"❌ Erro ao abrir a página: {arquivo_destino}")
            st.warning("Verifique se o nome do arquivo na pasta 'pages' é EXATAMENTE igual ao nome acima (letras maiúsculas/minúsculas importam!).")
            st.code(f"Esperado: {arquivo_destino}", language="text")
    else:
        st.error(f"❌ Disciplina '{disciplina}' não está mapeada no código.")

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
        
        # Nomes que serão salvos no banco (com acentos)
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
                    # Exibe nome amigável
                    d_nome = "Dutos (Antigo)" if row['Disciplina'] == "Geral" else row['Disciplina']
                    
                    st.markdown(f"**{row['Obra']}**")
                    st.caption(f"{row['Cliente']} | {d_nome}")
                    
                    if row['Fornecedor']: st.text(f"🏢 {row['Fornecedor']}")
                    
                    # Botão de Edição
                    if st.button(f"✏️ Editar", key=f"btn_{row['_id_linha']}"):
                        ir_para_edicao(row)
else:
    st.info("Nenhum projeto encontrado.")
