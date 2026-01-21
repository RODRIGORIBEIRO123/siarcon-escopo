import streamlit as st
from PIL import Image

st.set_page_config(
    page_title="Portal SIARCON",
    page_icon="🏗️",
    layout="wide"
)

# --- CABEÇALHO COM LOGO E TÍTULO LADO A LADO ---
# Cria duas colunas: uma estreita para o logo (1) e uma larga para o texto (5)
col_logo, col_titulo = st.columns([1, 5])

with col_logo:
    try:
        # Tenta carregar o logo. Ajuste o width se ficar muito grande ou pequeno.
        st.image("Siarcon.png", width=150) 
    except:
        st.warning("Logo não encontrado.")

with col_titulo:
    # O título fica na coluna da direita, alinhado com o logo
    st.title("Portal de Engenharia & Obras")
    st.markdown("**SIARCON Engenharia** | Gestão de Suprimentos")

st.markdown("---")

# --- CONTEÚDO DA PÁGINA ---
col1, col2 = st.columns([2, 1])

with col1:
    st.markdown("""
    ### Bem-vindo ao Sistema Integrado.

    Utilize o **Menu Lateral (à esquerda)** para acessar os módulos de geração de escopo.

    **Disponível agora:**
    * ❄️ **Rede de Dutos:** Geração completa de contratos e anexos.
    * 💧 **Hidráulica:** (Em breve)
    * ⚡ **Elétrica:** (Em breve)
    * 🤖 **Automação:** (Em breve)
    * ✅ **TAB / Qualificação:** (Em breve)
    
    Este sistema visa padronizar a contratação de terceiros, garantindo que todas as exigências técnicas e de SMS sejam cumpridas.
    """)

with col2:
    st.info("""
    **📢 Avisos da Engenharia**
    
    * **Novos Modelos:** O modelo de contrato de Dutos foi atualizado para a Rev.02.
    * **Dúvidas?** Entre em contato com a Gestão de Suprimentos.
    """)

