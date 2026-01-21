import streamlit as st
import gspread
from google.oauth2.service_account import Credentials

st.set_page_config(page_title="Teste Banco", page_icon="🔧")

st.title("🔧 Teste de Conexão: SIARCON -> Google Sheets")

# 1. Tentar pegar as credenciais do cofre
try:
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]
    
    credentials = Credentials.from_service_account_info(
        st.secrets["gcp_service_account"],
        scopes=scopes
    )
    
    # 2. Autenticar
    gc = gspread.authorize(credentials)
    
    # 3. Abrir a planilha
    # O nome tem que ser IDÊNTICO ao que você criou no Google
    sh = gc.open("DB_SIARCON")
    
    st.success("✅ Conexão BEM SUCEDIDA com o Google Sheets!")
    st.write(f"Planilha encontrada: **{sh.title}**")
    
    # 4. Listar as abas
    abas = [ws.title for ws in sh.worksheets()]
    st.info(f"Abas encontradas: {abas}")
    
    # 5. Teste de Escrita (Opcional)
    if st.button("Testar Gravação (Escrever 'Teste' na aba Dutos)"):
        worksheet = sh.worksheet("Dutos")
        worksheet.append_row(["Teste de Conexão", "Funcionou!", "Linha criada pelo App"])
        st.balloons()
        st.success("Linha gravada com sucesso! Confira na sua planilha.")

except Exception as e:
    st.error("❌ Falha na conexão.")
    st.error(f"Erro detalhado: {e}")
    st.markdown("""
    **Checklist de Correção:**
    1. O nome da planilha no Google é exatamente `DB_SIARCON`?
    2. Você compartilhou a planilha com o e-mail do robô (`client_email` que está nos Secrets)?
    3. Os dados no Secrets estão entre aspas duplas?
    """)
