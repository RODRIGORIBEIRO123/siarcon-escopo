import streamlit as st
import pandas as pd
import utils_db

st.set_page_config(page_title="Dashboard | SIARCON", page_icon="📊", layout="wide")
st.title("📊 Painel de Projetos (Kanban)")

if st.button("🔄 Atualizar Quadro"):
    st.rerun()

# --- CARREGAR DADOS ---
df = utils_db.listar_todos_projetos()

# --- FUNÇÃO QUE CRIA O CARTÃO VISUAL ---
def card_projeto(row, cor_status="blue"):
    """Cria um cartão Kanban com botões Editar e Excluir lado a lado"""
    with st.container(border=True):
        st.markdown(f"**{row['Cliente']}**")
        st.caption(f"📍 {row['Obra']}")
        st.markdown(f":{cor_status}[{row['Status']}]")
        
        # Cria duas colunas: 80% para Editar, 20% para Excluir
        col_edit, col_del = st.columns([0.85, 0.15])
        
        with col_edit:
            if st.button(f"✏️ Editar", key=f"edit_{row['_id_linha']}", use_container_width=True):
                st.session_state['dados_projeto'] = row.to_dict()
                st.session_state['modo_edicao'] = True
                st.switch_page("pages/1_❄️_Escopo_Dutos.py")
        
        with col_del:
            # Botão Compacto de Excluir
            if st.button("🗑️", key=f"del_{row['_id_linha']}", help="Excluir este projeto permanentemente"):
                sucesso = utils_db.excluir_projeto(row['_id_linha'])
                if sucesso:
                    st.toast("Projeto excluído com sucesso!", icon="🗑️")
                    st.rerun()
                else:
                    st.error("Erro ao excluir.")

# --- RENDERIZAÇÃO DAS RAIAS ---
if not df.empty:
    # Garante coluna Status
    if "Status" not in df.columns:
        df["Status"] = "Em Elaboração (Engenharia)"
    
    # Métricas de Topo
    total = len(df)
    pendencia_obras = len(df[df["Status"].str.contains("Aguardando Obras", na=False)])
    
    m1, m2 = st.columns([1, 3])
    m1.metric("Total de Projetos", total)
    if pendencia_obras > 0:
        m2.warning(f"⚠️ Atenção Obras: Existem {pendencia_obras} projetos na fila!")
    else:
        m2.success("✅ Fila de Obras Zerada!")

    st.divider()

    # Define as 4 Colunas do Kanban
    col_eng, col_obras, col_supr, col_fim = st.columns(4)
    
    # 1. ENGENHARIA
    with col_eng:
        st.subheader("👷 Engenharia")
        st.markdown("---")
        filtro = df[df["Status"] == "Em Elaboração (Engenharia)"]
        for i, row in filtro.iterrows():
            card_projeto(row, "blue")

    # 2. OBRAS
    with col_obras:
        st.subheader("🚧 Obras")
        st.markdown("---")
        filtro = df[df["Status"] == "Aguardando Obras"]
        for i, row in filtro.iterrows():
            card_projeto(row, "orange")

    # 3. SUPRIMENTOS
    with col_supr:
        st.subheader("💰 Suprimentos")
        st.markdown("---")
        lista = ["Recebido (Suprimentos)", "Enviado para Cotação", "Em Negociação"]
        filtro = df[df["Status"].isin(lista)]
        for i, row in filtro.iterrows():
            card_projeto(row, "violet")

    # 4. FINALIZADOS
    with col_fim:
        st.subheader("✅ Concluídos")
        st.markdown("---")
        filtro = df[df["Status"] == "Contratação Finalizada"]
        for i, row in filtro.iterrows():
            card_projeto(row, "green")

else:
    st.info("📭 Nenhum projeto encontrado. Cadastre um novo na aba lateral.")
