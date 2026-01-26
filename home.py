import streamlit as st
import pandas as pd
import utils_db
import os
import unicodedata

st.set_page_config(page_title="Painel de Projetos", page_icon="📊", layout="wide")

# ==================================================
# 🕵️‍♂️ DIAGNÓSTICO (A VERDADE NUA E CRUA)
# ==================================================
st.title("📊 Dashboard de Contratos")

# 1. Lê a pasta física
arquivos_reais = []
if os.path.exists("pages"):
    # Pega apenas arquivos .py
    arquivos_reais = [f for f in os.listdir("pages") if f.endswith(".py")]
else:
    st.error("🚨 ERRO CRÍTICO: A pasta 'pages' não existe!")
    st.stop()

# ==================================================
# 🧠 CÉREBRO DE BUSCA
# ==================================================
def encontrar_e_abrir(disciplina_db):
    """
    Tenta casar o nome do banco (ex: 'Elétrica') com o arquivo real (ex: 'eletrica.py')
    """
    # 1. Normaliza o nome que veio do banco (tira acento, põe minúsculo)
    nome_limpo = unicodedata.normalize('NFKD', disciplina_db).encode('ASCII', 'ignore').decode('ASCII').lower()
    
    # Ajustes manuais para apelidos
    if "geral" in nome_limpo: nome_limpo = "dutos"
    if "linha" in nome_limpo: nome_limpo = "cobre"
    
    # 2. Procura na lista de arquivos reais
    arquivo_escolhido = None
    
    for arquivo in arquivos_reais:
        arquivo_lower = arquivo.lower()
        # Verifica se o nome da disciplina está contido no nome do arquivo
        if nome_limpo in arquivo_lower:
            arquivo_escolhido = f"pages/{arquivo}"
            break
            
    # 3. Tenta abrir ou avisa o erro
    if arquivo_escolhido:
        st.session_state['modo_edicao'] = True
        st.switch_page(arquivo_escolhido) # O Pulo do Gato
    else:
        st.error(f"❌ Não encontrei arquivo para '{disciplina_db}'")
        st.info(f"O sistema procurou por algo parecido com '{nome_limpo}' na lista de arquivos acima, mas não achou.")

# ==================================================
# 🖥️ INTERFACE
# ==================================================

# Carregar Dados
df = utils_db.listar_todos_projetos()

# Criar Nova Obra
with st.expander("➕ CADASTRO NOVA OBRA"):
    with st.form("form_nova_obra"):
        c1, c2 = st.columns(2)
        novo_cliente = c1.text_input("Cliente")
        nova_obra = c2.text_input("Nome da Obra")
        
        opcoes = ["Dutos", "Hidráulica", "Elétrica", "Automação", "TAB", "Movimentações", "Linha de Cobre"]
        sel = st.multiselect("Escopos:", options=opcoes)
        
        if st.form_submit_button("🚀 Criar Pacote"):
            if utils_db.criar_pacote_obra(novo_cliente, nova_obra, sel):
                st.success("Criado!"); st.rerun()
            else: st.error("Erro.")

st.divider()

if not df.empty:
    cols = st.columns(4)
    grupos = {
        "⚪ Não Iniciado": ["Não Iniciado"],
        "👷 Engenharia": ["Em Elaboração (Engenharia)", "Aguardando Obras"],
        "🚧 Obras": ["Recebido (Suprimentos)", "Enviado para Cotação", "Em Negociação"],
        "✅ Concluídos": ["Contratação Finalizada"]
    }

    idx = 0
    for g_nome, g_status in grupos.items():
        with cols[idx]:
            st.markdown(f"### {g_nome}")
            for _, row in df[df['Status'].isin(g_status)].iterrows():
                with st.container(border=True):
                    st.caption(row['Cliente'])
                    st.markdown(f"**{row['Obra']}**")
                    st.markdown(f"📄 {row['Disciplina']}")
                    
                    if st.button(f"✏️ Editar", key=f"btn_{row['_id_linha']}"):
                        # Salva os dados na sessão antes de pular
                        st.session_state['dados_projeto'] = row.to_dict()
                        encontrar_e_abrir(row['Disciplina'])
        idx += 1
else:
    st.info("Nenhum projeto cadastrado.")

# DEBUG NO RODAPÉ (Para não atrapalhar, mas estar lá se precisar)
with st.expander("🔧 Ver Arquivos do Sistema (Debug)"):
    st.write("Arquivos encontrados na pasta 'pages':")
    st.code(arquivos_reais)
