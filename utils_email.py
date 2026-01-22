import streamlit as st
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders

def enviar_email_com_anexo(destinatario, assunto, corpo, arquivo_bytes, nome_arquivo):
    """
    Tenta enviar e-mail com anexo usando protocolo seguro (TLS/587).
    """
    try:
        # 1. Credenciais
        usuario = str(st.secrets["email"]["usuario"])
        senha = str(st.secrets["email"]["senha"])
        
        # 2. Monta o E-mail
        msg = MIMEMultipart()
        msg['From'] = f"Portal SIARCON <{usuario}>"
        msg['To'] = destinatario
        msg['Subject'] = assunto
        
        msg.attach(MIMEText(corpo, 'plain'))
        
        # 3. Anexo Blindado
        if arquivo_bytes:
            part = MIMEBase('application', "octet-stream")
            part.set_payload(arquivo_bytes)
            encoders.encode_base64(part)
            part.add_header('Content-Disposition', f'attachment; filename="{nome_arquivo}"')
            msg.attach(part)

        # 4. Envio
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(usuario, senha)
        text = msg.as_string()
        server.sendmail(usuario, destinatario, text)
        server.quit()
            
        return True

    except Exception as e:
        return f"Erro técnico: {e}"
