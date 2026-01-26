import streamlit as st
import pandas as pd
import utils_db
import os
import unicodedata

st.set_page_config(page_title="Dashboard SIARCON", page_icon="📊", layout="wide")

st.title("📊 Dashboard de Contratos")

# =========================================================
# 🕵️‍♂️ DIAGNÓSTICO VISUAL (NA TELA PRINCIPAL)
# =========================================================
st.subheader("🕵️‍♂️ Área de Diagnóstico")
arquivos_encontrados = []

if os.path.exists("pages"):
    arquivos_encontrados = [f for f in os.listdir("pages") if f.endswith(".py")]
    arquivos_encontrados.sort()
    
    # Mostra os arquivos encontrados
    st.info(f"O Sistema encontrou {len(arquivos_encontrados)} arquivos na pasta 'pages':")
    st.code(arquivos_encontrados)
else:
    st.error("🚨 ERRO CRÍTICO: A pasta 'pages' NÃO foi encontrada no diretório onde o Home.py está.")
    st.stop()

st.divider()

# =========================================================
# 🧠 LÓGICA DE NAVEGAÇÃO DINÂMICA
# =========================================================
def normalizar(texto):
    """Remove acentos e deixa minúsculo"""
    if not isinstance(texto, str): return ""
    return unicodedata.normalize('NFKD', texto).encode('ASCII', 'ignore').decode('ASCII').lower()

def encontrar_arquivo_e_navegar(row):
    disciplina_alvo = normalizar(row['Disciplina'])
    
    # Palavras-chave para busca
    mapa_busca = {
        "dutos": "dutos", "geral": "dutos",
        "hidraulica": "hidraulica", "hidr": "hidraulica",
        "eletrica": "eletrica", "eletr": "eletrica",
        "automacao": "automacao", "auto": "automacao",
        "tab": "tab",
        "movimentacoes": "movimentacoes", "mov": "movimentacoes",
        "cobre": "cobre", "linha": "cobre"
    }
    
    termo = mapa_busca.get(disciplina_alvo)
    
    # Tenta achar um arquivo que contenha o termo
    arquivo_destino = None
    if termo:
        for arq in arquivos_encontrados:
            if termo in normalizar(arq):
                arquivo_destino = f"pages/{arq}"
                break
    
    # Ação
    if arquivo_destino:
        st.session_state['dados_projeto'] = row.to_dict()
        st.session_state['modo_edicao'] = True
        st.switch_page(arquivo_destino)
    else:
        st.error(f"❌ Não encontrei nenhum arquivo para '{row['Disciplina']}'")
        st.warning(f"Procurei por arquivos contendo: '{termo}' na lista azul acima.")

# =========================================================
# 📋 KANBAN
# =========================================================
df = utils_db.listar_todos_projetos()

# Criar Nova Obra
with st.expander("➕ Criar Novo Pacote de Obra"):
    with st.form("form_nova_obra"):
        c1, c2 = st.columns(2)
        novo_cliente = c1.text_input("Cliente")
        nova_obra = c2.text_input("Nome da Obra")
        
        opcoes = ["Dutos", "Hidráulica", "Elétrica", "Automação", "TAB", "Movimentações", "Linha de Cobre"]
        sel = st.multiselect("Escopos:", options=opcoes)
        
        if st.form_submit_button("🚀 Criar"):
            if utils_db.criar_pacote_obra(novo_cliente, nova_obra, sel):
                st.success("Criado!"); st.rerun()
            else: st.error("Erro.")

if not df.empty:
    filtro_cli = st.selectbox("Cliente:", ["Todos"] + sorted(list(df['Cliente'].unique())))
    if filtro_cli != "Todos": df = df[df['Cliente'] == filtro_cli]

    cols = st.columns(3)
    grupos = {
        "🔴 A Fazer": ["Não Iniciado", "Aguardando Obras"],
        "🟡 Em Andamento": ["Em Elaboração (Engenharia)", "Recebido (Suprimentos)", "Enviado para Cotação", "Em Negociação"],
        "🟢 Concluído": ["Contratação Finalizada"]
    }

    for i, (g_nome, g_status) in enumerate(grupos.items()):
        with cols[i]:
            st.markdown(f"### {g_nome}")
            for _, row in df[df['Status'].isin(g_status)].iterrows():
                with st.container(border=True):
                    st.markdown(f"**{row['Obra']}**")
                    st.caption(f"{row['Disciplina']}")
                    if st.button(f"✏️ Editar", key=f"btn_{row['_id_linha']}"):
                        encontrar_arquivo_e_navegar(row)
else:
    st.info("Sem projetos.")
