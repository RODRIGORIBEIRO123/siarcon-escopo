import streamlit as st
import gspread

st.title("🧪 Teste de Conexão Definitivo")

try:
    # 1. Tenta pegar os segredos
    if "gcp_service_account" not in st.secrets:
        st.error("❌ Secrets não encontrados!")
        st.stop()

    creds = dict(st.secrets["gcp_service_account"])
    
    # 2. Mostra o início da chave para ver se o Streamlit leu certo (Debug)
    pk = creds.get("private_key", "")
    st.write(f"🔑 Chave lida (início): `{pk[:40]}...`")
    
    # 3. Tenta corrigir a chave (A Correção Universal)
    # Se a chave tiver "\n" escrito como texto, vira quebra de linha real
    if "\\n" in pk:
        creds["private_key"] = pk.replace("\\n", "\n")
    
    # 4. Tenta conectar
    gc = gspread.service_account_from_dict(creds)
    st.success("✅ Autenticação com Google: SUCESSO!")

    # 5. Tenta abrir a planilha
    sh = gc.open("DB_SIARCON")
    st.success(f"✅ Planilha Encontrada: {sh.title}")
    
    # 6. Tenta ler a aba Dados
    ws = sh.worksheet("Dados")
    dados = ws.get_all_records()
    st.write("📋 Dados lidos da planilha:", dados)

except Exception as e:
    st.error(f"☠️ ERRO FATAL: {e}")
    st.write("Dica: Se o erro for 'Invalid JWT', a chave nos secrets ainda está formatada errada.")
