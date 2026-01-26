import streamlit as st
import utils_db
import os

st.set_page_config(page_title="Painel Kanban", page_icon="📊", layout="wide")

# --- MAPA MANUAL (EXTREMAMENTE SEGURO) ---
# Baseado na sua imagem da árvore de arquivos
MAPA_ARQUIVOS = {
    "Dutos": "pages/1_Dutos.py",
    "Geral": "pages/1_Dutos.py", # Para compatibilidade
    "Hidráulica": "pages/2_Hidraulica.py",
    "Elétrica": "pages/3_Eletrica.py",
    "Automação": "pages/4_Automacao.py",
    "TAB": "pages/5_TAB.py",
    "Movimentações": "pages/6_Movimentacoes.py",
    "Linha de Cobre": "pages/7_Cobre.py"
}

def ir_para_edicao(row):
    disciplina = row['Disciplina']
    
    # Verifica no mapa
    if disciplina in MAPA_ARQUIVOS:
        arquivo = MAPA_ARQUIVOS[disciplina]
        st.session_state['dados_projeto'] = row.to_dict()
        st.session_state['modo_edicao'] = True
        st.switch_page(arquivo)
    else:
        st.error(f"❌ Erro de Configuração: Não sei onde fica o arquivo de '{disciplina}'.")

# --- INTERFACE ---
st.title("🚀 Painel de Controle de Obras")

if st.button("🗑️ Limpar Erros / Reiniciar"):
    st.rerun()

# 1. Carregar Projetos
try:
    df = utils_db.listar_todos_projetos()
except Exception as e:
    st.error(f"Erro ao ler banco de dados: {e}")
    st.stop()

# 2. Criar Nova Obra
with st.expander("➕ Nova Obra"):
    with st.form("nova"):
        c1, c2 = st.columns(2)
        cli = c1.text_input("Cliente")
        obr = c2.text_input("Obra")
        # Nomes EXATOS que batem com o MAPA acima
        discs = st.multiselect("Disciplinas", ["Dutos", "Hidráulica", "Elétrica", "Automação", "TAB", "Movimentações", "Linha de Cobre"])
        if st.form_submit_button("Criar"):
            utils_db.criar_pacote_obra(cli, obr, discs)
            st.rerun()

st.divider()

# 3. Kanban
if not df.empty:
    cols = st.columns(4)
    status_map = {
        "Não Iniciado": 0,
        "Em Elaboração (Engenharia)": 1, "Aguardando Obras": 1,
        "Recebido (Suprimentos)": 2, "Enviado para Cotação": 2, "Em Negociação": 2,
        "Contratação Finalizada": 3
    }
    titulos = ["⚪ A Fazer", "👷 Engenharia", "🚧 Obras/Suprimentos", "✅ Concluído"]

    for idx, titulo in enumerate(titulos):
        with cols[idx]:
            st.markdown(f"### {titulo}")
            # Filtra projetos desta coluna
            for _, row in df.iterrows():
                # Lógica simples de coluna
                s = row['Status']
                col_idx = status_map.get(s, 0)
                
                if col_idx == idx:
                    with st.container(border=True):
                        st.markdown(f"**{row['Obra']}**")
                        st.caption(f"{row['Cliente']} | {row['Disciplina']}")
                        
                        if st.button(f"✏️ Editar", key=f"btn_{row['_id_linha']}", use_container_width=True):
                            ir_para_edicao(row)
                        
                        if st.button("Excluir", key=f"del_{row['_id_linha']}"):
                            utils_db.excluir_projeto(row['_id_linha'])
                            st.rerun()
else:
    st.info("Nenhum projeto cadastrado.")
