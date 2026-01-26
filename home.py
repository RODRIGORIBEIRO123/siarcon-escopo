import streamlit as st
import pandas as pd
import utils_db
import os
import unicodedata

st.set_page_config(page_title="Painel de Projetos (Kanban)", page_icon="📊", layout="wide")

# ==================================================
# 🧠 NAVEGADOR FLEXÍVEL (A SOLUÇÃO DO PROBLEMA)
# ==================================================
def normalizar(texto):
    """Remove acentos e deixa minúsculo"""
    if not isinstance(texto, str): return ""
    return unicodedata.normalize('NFKD', texto).encode('ASCII', 'ignore').decode('ASCII').lower()

def encontrar_arquivo_flexivel(disciplina_banco):
    """
    1. Define uma palavra-chave para cada disciplina.
    2. Varre a pasta 'pages'.
    3. Retorna o PRIMEIRO arquivo que contiver a palavra-chave no nome.
    """
    # MAPA: Nome no Banco -> Palavra-chave obrigatória no nome do arquivo
    mapa_keywords = {
        "dutos": "dutos",
        "geral": "dutos",
        "hidraulica": "hidraulica",
        "hidráulica": "hidraulica",
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

    term_busca = mapa_keywords.get(normalizar(disciplina_banco))
    
    if not term_busca:
        return None, f"Disciplina '{disciplina_banco}' sem palavra-chave definida."

    try:
        if not os.path.exists("pages"):
            return None, "Pasta 'pages' não encontrada."

        # Lista arquivos reais na pasta (Ex: ['1_Dutos.py', '2_Hidraulica.py'])
        arquivos_reais = os.listdir("pages")
        
        for arquivo_real in arquivos_reais:
            # Ignora arquivos que não sejam Python
            if not arquivo_real.endswith(".py"): continue
            
            # COMPARAÇÃO INTELIGENTE:
            # Se a palavra 'dutos' estiver dentro de '1_Dutos.py' (normalizado), achamos!
            if term_busca in normalizar(arquivo_real):
                return f"pages/{arquivo_real}", None # Retorna o caminho EXATO que existe no disco
        
        return None, f"Não achei nenhum arquivo contendo '{term_busca}' na pasta pages."

    except Exception as e:
        return None, f"Erro ao ler pasta: {e}"

# --- AÇÃO DO BOTÃO ---
def ir_para_edicao(row):
    disciplina = row['Disciplina']
    
    # Usa a função flexível
    caminho_arquivo, erro = encontrar_arquivo_flexivel(disciplina)
    
    if caminho_arquivo:
        st.session_state['dados_projeto'] = row.to_dict()
        st.session_state['modo_edicao'] = True
        try:
            st.switch_page(caminho_arquivo)
        except Exception as e:
            st.error(f"Erro crítico ao trocar de página: {e}")
    else:
        st.error(f"❌ Erro de Link: {erro}")
        # Debug para ajudar você a ver o que está acontecendo
        st.caption("Arquivos disponíveis na pasta:")
        try:
            st.code(os.listdir("pages"))
        except: pass

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
    colunas_status = st.columns(4)
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
                    
                    # Ícone dinâmico
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
                        if utils_db.excluir_projeto(row['_id_linha']):
                            st.rerun()
        col_index += 1
else:
    st.info("Nenhum projeto encontrado.")
