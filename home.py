import streamlit as st
import pandas as pd
import utils_db
import os
import unicodedata

st.set_page_config(page_title="Dashboard SIARCON", page_icon="📊", layout="wide")

# ==================================================
# 🧠 CÉREBRO DE NAVEGAÇÃO (AUTO-DETECÇÃO)
# ==================================================
def normalizar(texto):
    """Transforma 'Elétrica' em 'eletrica' para facilitar a busca"""
    if not isinstance(texto, str): return ""
    return unicodedata.normalize('NFKD', texto).encode('ASCII', 'ignore').decode('ASCII').lower()

def encontrar_arquivo_automatico(disciplina_banco):
    """
    Varre a pasta 'pages' e encontra o arquivo certo baseada em palavras-chave.
    """
    # Palavras-chave para identificar cada disciplina
    # A esquerda: O que está no Excel/Banco
    # A direita: Um pedaço do nome que TEM que estar no nome do arquivo
    mapa_palavras = {
        "dutos": "dutos",
        "geral": "dutos", # Legado
        "hidraulica": "hidraulica",
        "eletrica": "eletrica",
        "automacao": "automacao",
        "tab": "tab",
        "movimentacoes": "movimentacoes",
        "cobre": "cobre"
    }

    termo_busca = mapa_palavras.get(normalizar(disciplina_banco))
    
    if not termo_busca:
        return None, f"Não sei procurar por: {disciplina_banco}"

    try:
        if not os.path.exists("pages"):
            return None, "A pasta 'pages' não existe no diretório principal."

        arquivos = os.listdir("pages")
        
        for arq in arquivos:
            # Pula arquivos que não sejam Python
            if not arq.endswith(".py"): continue
            
            # Se o pedaço do nome (ex: "dutos") estiver no nome do arquivo (ex: "1_dutos.py")
            if termo_busca in normalizar(arq):
                return f"pages/{arq}", None # ACHOU! Retorna o caminho completo
        
        return None, f"Não encontrei nenhum arquivo na pasta 'pages' que tenha '{termo_busca}' no nome."
        
    except Exception as e:
        return None, f"Erro crítico ao ler pasta: {e}"

# --- AÇÃO DO BOTÃO ---
def ir_para_edicao(row):
    disciplina = row['Disciplina']
    caminho, erro = encontrar_arquivo_automatico(disciplina)
    
    if caminho:
        st.session_state['dados_projeto'] = row.to_dict()
        st.session_state['modo_edicao'] = True
        st.switch_page(caminho)
    else:
        st.error(f"🚨 Erro: {erro}")
        st.info("Verifique se os arquivos na pasta 'pages' contêm palavras como: dutos, hidraulica, eletrica, etc.")

# ==================================================
# 🖥️ INTERFACE
# ==================================================
st.title("📊 Dashboard de Contratos")

# --- DEBUG LATERAL (Para te ajudar a ver o que está acontecendo) ---
with st.sidebar:
    st.header("🔍 Arquivos Detectados")
    if os.path.exists("pages"):
        arquivos = sorted([f for f in os.listdir("pages") if f.endswith(".py")])
        for f in arquivos:
            st.code(f, language="text")
    else:
        st.error("⚠️ Pasta 'pages' não encontrada!")
    st.divider()

# Carregar Dados
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
                    # Mostra o nome real
                    disc_nome = "Dutos (Antigo)" if row['Disciplina'] == "Geral" else row['Disciplina']
                    
                    st.markdown(f"**{row['Obra']}**")
                    st.caption(f"{row['Cliente']} | {disc_nome}")
                    if row['Fornecedor']: st.text(f"🏢 {row['Fornecedor']}")
                    
                    # O Botão Mágico
                    if st.button(f"✏️ Editar", key=f"btn_{row['_id_linha']}"):
                        ir_para_edicao(row)
else:
    st.info("Nenhum projeto encontrado.")
