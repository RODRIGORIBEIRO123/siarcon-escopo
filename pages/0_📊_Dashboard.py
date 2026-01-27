import streamlit as st
import pandas as pd
import utils_db

st.set_page_config(page_title="Dashboard | SIARCON", page_icon="📊", layout="wide")

st.title("📊 Painel de Projetos (Kanban)")

if st.button("🔄 Atualizar"):
    st.cache_data.clear()
    st.rerun()

# Carrega Dados
df = utils_db.listar_todos_projetos()

if df.empty:
    st.warning("Nenhum projeto encontrado ou erro ao conectar com a planilha.")
else:
    # Métricas
    total = len(df)
    valor_total = pd.to_numeric(df['valor_total'].astype(str).str.replace('R$', '').str.replace('.', '').str.replace(',', '.'), errors='coerce').sum()
    
    c1, c2 = st.columns(2)
    c1.metric("Projetos Totais", total)
    c1.metric("Volume Financeiro Estimado", f"R$ {valor_total:,.2f}")

    st.markdown("---")
    
    # Kanban Simplificado
    cols = st.columns(3)
    status_list = ["Em Elaboração", "Enviado para Cotação", "Finalizado"]
    
    for i, status in enumerate(status_list):
        with cols[i]:
            st.subheader(status)
            filtrados = df[df['status'] == status]
            
            for index, row in filtrados.iterrows():
                with st.expander(f"{row['disciplina']} - {row['cliente']}"):
                    st.write(f"**Obra:** {row['obra']}")
                    st.write(f"**Forn:** {row['fornecedor']}")
                    st.caption(f"ID: {row['_id']}")
