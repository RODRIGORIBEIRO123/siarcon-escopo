import streamlit as st
import pandas as pd
import utils_db
import os
import unicodedata

st.set_page_config(page_title="Painel de Projetos (Kanban)", page_icon="📊", layout="wide")

# ==================================================
# 🧠 CÉREBRO DE NAVEGAÇÃO (AUTO-DETECÇÃO)
# ==================================================
def normalizar(texto):
    """Remove acentos e deixa minúsculo para comparar (ex: 'Elétrica' vira 'eletrica')"""
    if not isinstance(texto, str): return ""
    return unicodedata.normalize('NFKD', texto).encode('ASCII', 'ignore').decode('ASCII').lower()

def encontrar_arquivo_automatico(disciplina_banco):
    """
    Varre a pasta 'pages' e encontra o arquivo certo baseada em palavras-chave.
    """
    # MAPA DE TRADUÇÃO:
    # Esquerda: O que está escrito no Card/Banco de Dados
    # Direita: Um pedaço do nome que OBRIGATORIAMENTE está no nome do arquivo
    mapa_palavras = {
        "dutos": "dutos",
        "geral": "dutos", # Para corrigir os antigos "Geral"
        "hidraulica": "hidraulica", # Sem acento
        "hidráulica": "hidraulica", # Com acento
        "eletrica": "eletrica",
        "elétrica": "eletrica",
        "automacao": "automacao",
        "automação": "automacao",
        "tab": "tab",
        "movimentacoes": "movimentacoes",
        "movimentações": "movimentacoes",
        "cobre": "cobre",
        "linha de cobre": "cobre"
    }

    # 1. Normaliza o nome que veio do banco (ex: "Elétrica" -> "eletrica")
    termo_busca = mapa_palavras.get(normalizar(disciplina_banco))
    
    if not termo_busca:
        return None, f"Não sei procurar por: {disciplina_banco}"

    try:
        if not os.path.exists("pages"):
            return None, "A pasta 'pages' não existe no diretório principal."

        # 2. Lista todos os arquivos da pasta pages
        arquivos = os.listdir("pages")
        
        for arq in arquivos:
            # Pula arquivos que não sejam Python
            if not arq.endswith(".py"): continue
            
            # 3. COMPARAÇÃO INTELIGENTE
            # Se o termo (ex: "eletrica") estiver dentro do nome do arquivo (ex: "3_Eletrica.py")
            if termo_busca in normalizar(arq):
                return f"pages/{arq}", None # ACHOU! Retorna o caminho exato
        
        return None, f"Não encontrei nenhum arquivo na pasta 'pages' que tenha a palavra '{termo_busca}'."
        
    except Exception as e:
        return None, f"Erro crítico ao ler pasta: {e}"

# --- AÇÃO DO BOTÃO ---
def ir_para_edicao(row):
    disciplina = row['Disciplina']
    
    # Usa a inteligência para achar o arquivo real
    caminho, erro = encontrar_arquivo_automatico(disciplina)
    
    if caminho:
        st.session_state['dados_projeto'] = row.to_dict()
        st.session_state['modo_edicao'] = True
        st.switch_page(caminho)
    else:
        st.toast(f"❌ Erro: {erro}", icon="🚨")
        st.error(f"Detalhe do erro: {erro}")

# ==================================================
# 🖥️ INTERFACE
# ==================================================
st.title("📊 Painel de Projetos (Kanban)")

# Carregar Dados
df = utils_db.listar_todos_projetos()

# Criar Nova Obra
with st.expander("➕ CADASTRO NOVA OBRA"):
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

if st.button("🔄 Atualizar Quadro"):
    st.rerun()

st.divider()

# Kanban
if not df.empty:
    colunas_status = st.columns(4) # Ajustado para 4 colunas como na imagem
    grupos = {
        "⚪ Não Iniciado": ["Não Iniciado"],
        "👷 Engenharia": ["Em Elaboração (Engenharia)", "Aguardando Obras"],
        "🚧 Obras": ["Recebido (Suprimentos)", "Enviado para Cotação", "Em Negociação"],
        "✅ Concluídos": ["Contratação Finalizada"]
    }

    col_index = 0
    for grupo_nome, status_grupo in grupos.items():
        with colunas_status[col_index]:
            st.markdown(f"### {grupo_nome}")
            df_grupo = df[df['Status'].isin(status_grupo)]
            
            for index, row in df_grupo.iterrows():
                with st.container(border=True):
                    # Header do Card
                    st.caption(f"{row['Cliente']}")
                    st.markdown(f"**📍 {row['Obra']}**")
                    
                    # Ícone dinâmico dependendo da disciplina
                    icon_map = {
                        "Dutos": "❄️", "Geral": "📄", "Hidráulica": "💧", 
                        "Elétrica": "⚡", "Automação": "🤖", "TAB": "💨",
                        "Movimentações": "🏗️", "Linha de Cobre": "🔥"
                    }
                    icone = icon_map.get(row['Disciplina'], "📁")
                    
                    st.markdown(f"### {icone} {row['Disciplina']}")
                    
                    # Status colorido
                    color = "orange" if "Aguardando" in row['Status'] else "blue"
                    if "Finalizada" in row['Status']: color = "green"
                    st.markdown(f":{color}[{row['Status']}]")

                    c_btn1, c_btn2 = st.columns([2,1])
                    btn_label = "▶️ Iniciar" if row['Status'] == "Não Iniciado" else "✏️ Editar"
                    
                    if c_btn1.button(btn_label, key=f"btn_{row['_id_linha']}", use_container_width=True):
                        ir_para_edicao(row)
                    
                    if c_btn2.button("🗑️", key=f"del_{row['_id_linha']}"):
                        utils_db.excluir_projeto(row['_id_linha'])
                        st.rerun()
        col_index += 1
else:
    st.info("Nenhum projeto encontrado.")
