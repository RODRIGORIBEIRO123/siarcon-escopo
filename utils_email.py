import streamlit as st
import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication

def enviar_email_com_anexo(destinatario, assunto, corpo, arquivo_bytes, nome_arquivo):
    """
    Envia um e-mail com anexo usando servidor SMTP do Gmail.
    """
    # 1. Pegar credenciais do cofre
    remetente = st.secrets["email"]["usuario"]
    senha = st.secrets["email"]["senha"]
    
    # 2. Montar o E-mail
    msg = MIMEMultipart()
    msg['From'] = remetente
    msg['To'] = destinatario
    msg['Subject'] = assunto
    
    # Adiciona o texto do corpo
    msg.attach(MIMEText(corpo, 'plain'))
    
    # 3. Adicionar o Anexo
    try:
        # O arquivo vem como BytesIO, pegamos o valor
        part = MIMEApplication(arquivo_bytes, Name=nome_arquivo)
        part['Content-Disposition'] = f'attachment; filename="{nome_arquivo}"'
        msg.attach(part)
    except Exception as e:
        return f"Erro ao anexar arquivo: {e}"

    # 4. Conectar ao Gmail e Enviar
    context = ssl.create_default_context()
    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=context) as server:
            server.login(remetente, senha)
            server.sendmail(remetente, destinatario, msg.as_string())
        return True # Sucesso
    except Exception as e:
        return f"Erro no envio: {e}"
