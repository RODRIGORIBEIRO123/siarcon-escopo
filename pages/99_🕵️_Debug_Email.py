import streamlit as st
import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

st.set_page_config(page_title="Debug Email", page_icon="🕵️")

st.title("🕵️ Diagnóstico de E-mail")

st.write("Vamos testar a conexão com o Gmail e verificar se as credenciais estão sendo lidas corretamente.")

# 1. VERIFICAR OS SEGREDOS
st.subheader("1. Verificação das Credenciais")
try:
    usuario_secreto = st.secrets["email"]["usuario"]
    senha_secreta = st.secrets["email"]["senha"]
    
    st.success("✅ O arquivo secrets.toml foi encontrado.")
    st.info(f"📧 E-mail configurado no Robô: **{usuario_secreto}**")
    
    # Verifica se a senha tem 16 caracteres (padrão de App Password)
    tamanho_senha = len(senha_secreta.replace(" ", ""))
    if tamanho_senha == 16:
        st.success(f"✅ A senha parece correta (tem 16 caracteres).")
    else:
        st.error(f"⚠️ A senha parece suspeita. Ela tem {tamanho_senha} caracteres. Uma senha de app do Google deve ter exatamente 16 letras.")

except Exception as e:
    st.error(f"❌ Erro ao ler secrets: {e}")
    st.stop()

st.divider()

# 2. TESTE DE ENVIO REAL
st.subheader("2. Teste de Disparo Real")
destinatario = st.text_input("Digite um e-mail para receber o teste:", value=usuario_secreto)

if st.button("🔥 Tentar Enviar E-mail de Teste"):
    with st.spinner("Conectando ao servidor do Google..."):
        try:
            # Monta um e-mail simples SEM anexo
            msg = MIMEMultipart()
            msg['From'] = usuario_secreto
            msg['To'] = destinatario
            msg['Subject'] = "Teste de Diagnóstico SIARCON"
            body = "Se você recebeu este e-mail, a conexão do robô está funcionando 100%."
            msg.attach(MIMEText(body, 'plain'))

            # Conexão SMTP com debug ativado
            context = ssl.create_default_context()
            with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=context) as server:
                # Tenta logar
                st.write("🔑 Tentando login...")
                server.login(usuario_secreto, senha_secreta)
                st.write("✅ Login aceito pelo Google!")
                
                # Tenta enviar
                st.write("📤 Enviando pacote de dados...")
                server.sendmail(usuario_secreto, destinatario, msg.as_string())
                st.write("✅ Comando de envio finalizado.")
            
            st.balloons()
            st.success(f"🎉 O código rodou sem erros! Verifique agora a caixa de entrada de {destinatario}.")
            st.warning("⚠️ Se não chegar em 1 minuto, verifique a pasta SPAM.")

        except smtplib.SMTPAuthenticationError:
            st.error("❌ Erro de Autenticação: O Google recusou o login. Verifique se o e-mail no secrets é EXATAMENTE o mesmo da conta onde a senha de app foi gerada.")
        except Exception as e:
            st.error(f"❌ Erro Técnico: {e}")
