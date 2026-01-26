import streamlit as st
import pandas as pd
import utils_db
import os
import unicodedata

st.set_page_config(page_title="Dashboard SIARCON", page_icon="📊", layout="wide")

# ==================================================
# 🧠 NAVEGADOR INTELIGENTE (Auto-Detector)
# ==================================================
def normalizar_texto(texto):
    """Remove acentos e deixa minúsculo para comparação"""
    if not isinstance(texto, str): return ""
    return unicodedata.normalize('NFKD', texto).encode('ASCII', 'ignore').decode('ASCII').lower()

def encontrar_arquivo_destino(disciplina_db):
    """
    Procura na pasta 'pages' qual arquivo corresponde à disciplina,
    independente de ter números ou emojis no nome.
    """
    # 1. Define a palavra-chave que deve existir no nome do arquivo
    mapa_palavras_chave = {
        "Dutos": "dutos",
        "Geral": "dutos", # Legado
        "Hidráulica": "hidraulica",
        "Elétrica": "eletrica",
        "Automação": "automacao",
        "TAB": "tab",
        "Movimentações": "movimentacoes",
        "Linha de Cobre": "cobre"
    }
    
    palavra_chave = mapa_palavras_chave.get(disciplina_db)
    
    if not palavra_chave:
        return None, f"Disciplina '{disciplina_db}' não tem palavra-chave definida."

    try:
        # 2. Varre a pasta pages
        arquivos_na_pasta = os.listdir("pages")
        
        for arquivo in arquivos_na_pasta:
            nome_normalizado = normalizar_texto(arquivo)
            # Se a palavra chave (ex: "dutos") estiver no nome do arquivo (ex: "1_dutos.py")
            if palavra_chave in nome_normalizado and arquivo.endswith(".py"):
                return f"pages/{arquivo}", None # Sucesso! Retorna o caminho
                
        return None, f"Não achei nenhum arquivo contendo '{palavra_chave}' na pasta pages."
        
    except Exception as e:
        return None, f"Erro ao ler pasta pages: {e}"

# --- FUNÇÃO DE CLIQUE DO BOTÃO ---
def ir_para_edicao(row):
    disciplina = row['Disciplina']
    
    # Usa a inteligência para achar o arquivo
    caminho_arquivo, erro = encontrar_arquivo_destino(disciplina)
    
    if caminho_arquivo:
        st.session_state['dados_projeto'] = row.to_dict()
        st.session_state['modo_edicao'] = True
        st.switch_page(caminho_arquivo)
    else:
        st.error(f"❌ Erro de Navegação: {erro}")
        st.info("Verifique se os arquivos na pasta 'pages' contêm os nomes: dutos, hidraulica, eletrica, automacao, tab, movimentacoes, cobre.")

# ==================================================
# 🖥️ INTERFACE
# ==================================================
st.title("📊 Dashboard de Contratos")

# Diagnóstico Rápido na Barra Lateral (Para garantir)
with st.sidebar:
    st.caption("📂 Arquivos que o sistema vê:")
    try:
        for f in sorted(os.listdir("pages")):
            if f.endswith(".py"): st.code(f, language="text")
    except: st.error("Pasta pages não encontrada")

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
                    d_nome = "Dutos (Antigo)" if row['Disciplina'] == "Geral" else row['Disciplina']
                    
                    st.markdown(f"**{row['Obra']}**")
                    st.caption(f"{row['Cliente']} | {d_nome}")
                    if row['Fornecedor']: st.text(f"🏢 {row['Fornecedor']}")
                    
                    if st.button(f"✏️ Editar", key=f"btn_{row['_id_linha']}"):
                        ir_para_edicao(row)
else:
    st.info("Nenhum projeto encontrado.")
