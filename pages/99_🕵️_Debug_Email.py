import streamlit as st
import utils_email
import io

st.set_page_config(page_title="Debug Anexo", page_icon="🕵️")
st.title("🕵️ Teste de Anexo")

usuario_secreto = st.secrets["email"]["usuario"]
st.info(f"Testando envio de: {usuario_secreto}")

destinatario = st.text_input("Enviar para:", value=usuario_secreto)

if st.button("🔥 Enviar E-mail com Anexo de Teste"):
    with st.spinner("Gerando arquivo e enviando..."):
        
        # 1. Cria um arquivo de texto simples na memória
        arquivo_teste = io.BytesIO()
        arquivo_teste.write(b"Ola! Este e um arquivo de teste para validar o anexo.\nSe voce esta lendo isso, funcionou.")
        arquivo_teste.seek(0) # Volta para o inicio
        
        # 2. Tenta enviar
        resultado = utils_email.enviar_email_com_anexo(
            destinatario=destinatario,
            assunto="Teste de Anexo - SIARCON",
            corpo="Segue anexo de teste.",
            arquivo_bytes=arquivo_teste.getvalue(),
            nome_arquivo="teste_conexao.txt"
        )
        
        if resultado is True:
            st.success(f"✅ O Python diz que enviou! Verifique se chegou um email com 'teste_conexao.txt'.")
        else:
            st.error(f"❌ Erro: {resultado}")
