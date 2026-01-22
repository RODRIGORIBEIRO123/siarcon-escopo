import streamlit as st
import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders

def enviar_email_com_anexo(destinatario, assunto, corpo, arquivo_bytes, nome_arquivo):
    """
    Envia e-mail usando MIMEBase e Encoders para garantir que o anexo
    passe pelos filtros do Gmail sem ser corrompido ou bloqueado.
    """
    try:
        # 1. Credenciais
        remetente = st.secrets["email"]["usuario"]
        senha = st.secrets["email"]["senha"]
        
        # 2. Montagem do E-mail
        msg = MIMEMultipart()
        msg['From'] = remetente
        msg['To'] = destinatario
        msg['Subject'] = assunto
        
        # Corpo do texto
        msg.attach(MIMEText(corpo, 'plain'))
        
        # 3. Anexo Blindado (MIMEBase)
        # O modo 'octet-stream' é genérico e aceito por todos os servidores
        part = MIMEBase('application', "octet-stream")
        part.set_payload(arquivo_bytes)
        
        # Codifica em Base64 (essencial para enviar arquivos pela internet)
        encoders.encode_base64(part)
        
        # Cabeçalho do arquivo
        part.add_header('Content-Disposition', f'attachment; filename="{nome_arquivo}"')
        
        msg.attach(part)

        # 4. Envio Seguro
        context = ssl.create_default_context()
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=context) as server:
            server.login(remetente, senha)
            server.sendmail(remetente, destinatario, msg.as_string())
            
        return True # Sucesso absoluto

    except Exception as e:
        return f"Erro técnico no envio: {e}"
