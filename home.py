import streamlit as st
import pandas as pd
import utils_db
import os
from streamlit.source_util import get_pages as st_get_pages

st.set_page_config(page_title="Dashboard SIARCON", page_icon="📊", layout="wide")

# ==================================================
# 🧠 NAVEGADOR VIA REGISTRO INTERNO (INFALÍVEL)
# ==================================================
def navegar_para_disciplina(row):
    disciplina_alvo = row['Disciplina'].lower()
    
    # Mapeia nomes do banco para palavras-chave no nome do arquivo
    # Esquerda: Nome no Excel (minúsculo) | Direita: Trecho único do nome do arquivo
    palavras_chave = {
        "dutos": "dutos",
        "geral": "dutos",
        "hidráulica": "hidraulica", # ou hidr
        "hidraulica": "hidraulica",
        "elétrica": "eletrica",     # ou eletr
        "eletrica": "eletrica",
        "automação": "automacao",   # ou auto
        "automacao": "automacao",
        "tab": "tab",
        "movimentações": "movimentacoes", # ou mov
        "movimentacoes": "movimentacoes",
        "linha de cobre": "cobre",
        "cobre": "cobre"
    }

    # 1. Pega a palavra-chave
    keyword = palavras_chave.get(disciplina_alvo)
    if not keyword:
        st.error(f"Não sei procurar por: {row['Disciplina']}")
        return

    # 2. Pede ao Streamlit a lista oficial de páginas registradas
    # Isso retorna exatamente o que aparece no menu lateral
    paginas_registradas = st_get_pages("Home.py")
    
    caminho_final = None
    
    # 3. Procura a página correta na lista interna
    for page_hash, page_info in paginas_registradas.items():
        script_path = page_info["script_path"]
        # Verifica se a palavra chave (ex: "eletrica") está no caminho do arquivo
        if keyword in script_path.lower():
            caminho_final = script_path
            break
    
    # 4. Executa a ação
    if caminho_final:
        st.session_state['dados_projeto'] = row.to_dict()
        st.session_state['modo_edicao'] = True
        st.switch_page(caminho_final)
    else:
        st.error(f"❌ O Streamlit não encontrou nenhuma página registrada contendo '{keyword}'.")
        st.info("Debug: Confira os nomes no menu lateral.")

# ==================================================
# 🖥️ INTERFACE
# ==================================================
st.title("📊 Dashboard de Contratos")

# Debug Discreto (Expander)
with st.sidebar.expander("🔧 Debug Técnico"):
    st.write("Páginas que o Streamlit enxerga:")
    try:
        pages = st_get_pages("Home.py")
        for k, v in pages.items():
            st.code(v['script_path'], language="text")
    except:
        st.write("Erro ao ler registro interno.")

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
    filtro_cliente = c_filt1.selectbox("Filtrar Cliente:", ["Todos"] + lista_clientes)
    if filtro_cliente != "Todos": df = df[df['Cliente'] == filtro_cliente]

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
                    d_nome = "Dutos" if row['Disciplina'] == "Geral" else row['Disciplina']
                    
                    st.markdown(f"**{row['Obra']}**")
                    st.caption(f"{row['Cliente']} | {d_nome}")
                    if row['Fornecedor']: st.text(f"🏢 {row['Fornecedor']}")
                    
                    if st.button(f"✏️ Editar", key=f"btn_{row['_id_linha']}"):
                        navegar_para_disciplina(row) # Função Nova
else:
    st.info("Nenhum projeto encontrado.")
