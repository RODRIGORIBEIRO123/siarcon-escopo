import streamlit as st
import pandas as pd
import utils_db
import os

st.set_page_config(page_title="Painel de Projetos (Kanban)", page_icon="📊", layout="wide")

# ==================================================
# 🗺️ MAPA DA MINA (CONFIGURAÇÃO MANUAL E SEGURA)
# ==================================================
# Aqui conectamos o nome que está no BANCO DE DADOS
# com o nome EXATO do arquivo que vi na sua pasta.
MAPA_PAGINAS = {
    # Dutos
    "Dutos": "pages/1_Dutos.py",
    "Geral": "pages/1_Dutos.py", # Para os antigos
    
    # Hidráulica (No banco tem acento, no arquivo não)
    "Hidráulica": "pages/2_Hidraulica.py",
    "Hidraulica": "pages/2_Hidraulica.py",
    
    # Elétrica
    "Elétrica": "pages/3_Eletrica.py",
    "Eletrica": "pages/3_Eletrica.py",
    
    # Automação
    "Automação": "pages/4_Automacao.py",
    "Automacao": "pages/4_Automacao.py",
    
    # TAB
    "TAB": "pages/5_TAB.py",
    
    # Movimentações
    "Movimentações": "pages/6_Movimentacoes.py",
    "Movimentacoes": "pages/6_Movimentacoes.py",
    
    # Cobre
    "Linha de Cobre": "pages/7_Cobre.py",
    "Cobre": "pages/7_Cobre.py"
}

# --- AÇÃO DO BOTÃO ---
def ir_para_edicao(row):
    disciplina = row['Disciplina']
    
    # Verifica se a disciplina existe no mapa
    if disciplina in MAPA_PAGINAS:
        arquivo_destino = MAPA_PAGINAS[disciplina]
        
        # Verifica se o arquivo existe fisicamente
        if os.path.exists(arquivo_destino):
            st.session_state['dados_projeto'] = row.to_dict()
            st.session_state['modo_edicao'] = True
            st.switch_page(arquivo_destino)
        else:
            st.error(f"🚨 Arquivo não encontrado: {arquivo_destino}")
            st.info("Verifique se o nome do arquivo na pasta 'pages' mudou.")
    else:
        st.error(f"❌ A disciplina '{disciplina}' não está mapeada no código.")

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
        
        # Opções padronizadas para salvar no banco
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
                    
                    # Identificador único para o botão
                    if c_btn1.button(btn_label, key=f"btn_{row['_id_linha']}", use_container_width=True):
                        ir_para_edicao(row)
                    
                    if c_btn2.button("🗑️", key=f"del_{row['_id_linha']}"):
                        if utils_db.excluir_projeto(row['_id_linha']):
                            st.rerun()
        col_index += 1
else:
    st.info("Nenhum projeto encontrado.")
