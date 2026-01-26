import streamlit as st
import utils_db
import os

st.set_page_config(page_title="Dashboard", page_icon="📊", layout="wide")

# ==================================================
# 🗺️ MAPA MANUAL DE ARQUIVOS
# ==================================================
# ATENÇÃO: Os caminhos são relativos à pasta principal,
# por isso usamos "pages/..." mesmo estando dentro da pasta pages.
MAPA_ARQUIVOS = {
    "Dutos": "pages/1_Dutos.py",
    "Geral": "pages/1_Dutos.py", 
    "Hidráulica": "pages/2_Hidraulica.py",
    "Elétrica": "pages/3_Eletrica.py",
    "Automação": "pages/4_Automacao.py",
    "TAB": "pages/5_TAB.py",
    "Movimentações": "pages/6_Movimentacoes.py",
    "Linha de Cobre": "pages/7_Cobre.py"
}

def ir_para_edicao(row):
    disciplina = row['Disciplina']
    
    # 1. Verifica se a disciplina existe no mapa
    if disciplina in MAPA_ARQUIVOS:
        arquivo_destino = MAPA_ARQUIVOS[disciplina]
        
        # 2. Salva os dados na memória (Sessão)
        st.session_state['dados_projeto'] = row.to_dict()
        st.session_state['modo_edicao'] = True
        
        # 3. Executa a troca de página
        try:
            st.switch_page(arquivo_destino)
        except Exception as e:
            st.error(f"❌ Erro ao tentar abrir: {arquivo_destino}")
            st.code(str(e))
    else:
        st.error(f"❌ A disciplina '{disciplina}' não está configurada no Mapa.")

# ==================================================
# 🖥️ INTERFACE DO KANBAN
# ==================================================
st.title("📊 Painel de Projetos (Kanban)")

if st.button("🔄 Atualizar"):
    st.rerun()

# 1. Carregar Dados
try:
    df = utils_db.listar_todos_projetos()
except Exception as e:
    st.error(f"Erro ao ler banco de dados: {e}")
    st.stop()

# 2. Criar Nova Obra
with st.expander("➕ Nova Obra"):
    with st.form("nova_obra_form"):
        c1, c2 = st.columns(2)
        cli = c1.text_input("Cliente")
        obr = c2.text_input("Obra")
        # Nomes EXATOS que batem com o MAPA acima
        opcoes = ["Dutos", "Hidráulica", "Elétrica", "Automação", "TAB", "Movimentações", "Linha de Cobre"]
        discs = st.multiselect("Disciplinas", opcoes)
        
        if st.form_submit_button("Criar"):
            if utils_db.criar_pacote_obra(cli, obr, discs):
                st.success("Criado!")
                st.rerun()

st.divider()

# 3. Visualização Kanban
if not df.empty:
    cols = st.columns(4)
    # Mapeamento de Status para Colunas (0 a 3)
    status_map = {
        "Não Iniciado": 0,
        "Em Elaboração (Engenharia)": 1, "Aguardando Obras": 1,
        "Recebido (Suprimentos)": 2, "Enviado para Cotação": 2, "Em Negociação": 2,
        "Contratação Finalizada": 3
    }
    titulos = ["⚪ A Fazer", "👷 Engenharia", "🚧 Obras/Suprimentos", "✅ Concluído"]

    # Desenha as colunas
    for idx_col, titulo in enumerate(titulos):
        with cols[idx_col]:
            st.markdown(f"### {titulo}")
            
            # Itera sobre os projetos
            for _, row in df.iterrows():
                # Descobre em qual coluna o card deve ficar
                s = row.get('Status', 'Não Iniciado')
                col_destino = status_map.get(s, 0)
                
                # Se o card pertence a esta coluna, desenha ele
                if col_destino == idx_col:
                    with st.container(border=True):
                        st.markdown(f"**{row['Obra']}**")
                        st.caption(f"{row['Cliente']}")
                        
                        # Ícone bonitinho
                        icones = {"Dutos": "❄️", "Hidráulica": "💧", "Elétrica": "⚡", "Automação": "🤖", "TAB": "💨", "Movimentações": "🏗️", "Linha de Cobre": "🔥"}
                        ico = icones.get(row['Disciplina'], "📁")
                        st.markdown(f"**{ico} {row['Disciplina']}**")
                        
                        # Botões
                        c_b1, c_b2 = st.columns([2,1])
                        if c_b1.button("✏️ Editar", key=f"edit_{row['_id_linha']}", use_container_width=True):
                            ir_para_edicao(row)
                        
                        if c_b2.button("🗑️", key=f"del_{row['_id_linha']}"):
                            utils_db.excluir_projeto(row['_id_linha'])
                            st.rerun()
else:
    st.info("Nenhum projeto cadastrado.")
