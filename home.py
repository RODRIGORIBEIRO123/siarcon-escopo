import streamlit as st
from PIL import Image

st.set_page_config(
    page_title="Portal SIARCON",
    page_icon="🏗️",
    layout="wide"
)

# Tenta carregar o logo (se ele existir)
try:
    # Ajuste o width (largura) conforme necessário para ficar bonito
    st.image("Siarcon.png", width=300) 
except:
    st.warning("Arquivo Siarcon.png não encontrado. Verifique se o nome está correto no GitHub.")

st.title("🏗️ Portal de Engenharia & Obras")
st.markdown("---")

col1, col2 = st.columns([2, 1])

with col1:
    st.markdown("""
    ### Bem-vindo ao Sistema Integrado SIARCON.

    Utilize o **Menu Lateral (à esquerda)** para acessar os módulos de geração de escopo.

    **Disponível agora:**
    * ❄️ **Rede de Dutos:** Geração completa de contratos e anexos.
    * 💧 **Hidráulica:** (Em breve)
    * ⚡ **Elétrica:** (Em breve)
    
    Este sistema visa padronizar a contratação de terceiros, garantindo que todas as exigências técnicas e de SMS sejam cumpridas.
    """)

with col2:
    st.info("""
    **📢 Avisos da Engenharia**
    
    * **Novos Modelos:** O modelo de contrato de Dutos foi atualizado para a Rev.02.
    * **Dúvidas?** Entre em contato com a Gestão de Suprimentos.
    """)

st.markdown("---")
st.caption("Sistema desenvolvido para uso interno da SIARCON Engenharia © 2026")

