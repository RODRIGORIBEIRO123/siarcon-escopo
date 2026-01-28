import streamlit as st

st.set_page_config(
    page_title="SIARCON Engenharia",
    page_icon="🏗️",
    layout="wide"
)

st.title("🏗️ Sistema de Gerenciamento de Escopos")
st.markdown("### Bem-vindo ao Sistema SIARCON")
st.info("👈 Selecione a disciplina desejada no menu lateral para iniciar um escopo.")

st.divider()

st.subheader("📌 Status do Sistema")
try:
    import utils_db
    # Testa conexão rápida
    if "gcp_service_account" in st.secrets:
        st.success("✅ Conexão com Google Cloud configurada.")
    else:
        st.error("❌ Secrets não encontrados.")
except Exception as e:
    st.error(f"Erro ao carregar utilitários: {e}")
