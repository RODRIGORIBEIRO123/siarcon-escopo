import streamlit as st
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders

def enviar_email_com_anexo(destinatario, assunto, corpo, arquivo_bytes, nome_arquivo):
    """
    Envia e-mail usando protocolo STARTTLS (Porta 587).
    """
    try:
        # 1. Credenciais (Garante que é string)
        usuario = str(st.secrets["email"]["usuario"])
        senha = str(st.secrets["email"]["senha"])
        
        # 2. Montagem do E-mail
        msg = MIMEMultipart()
        # Adiciona um "Nome" para não parecer robô
        msg['From'] = f"Portal SIARCON <{usuario}>"
        msg['To'] = destinatario
        msg['Subject'] = assunto
        
        msg.attach(MIMEText(corpo, 'plain'))
        
        # 3. Anexo
        # Verifica se o arquivo tem tamanho maior que 0
        if len(arquivo_bytes) == 0:
            return "Erro: O arquivo gerado está vazio (0 bytes)."

        part = MIMEBase('application', "octet-stream")
        part.set_payload(arquivo_bytes)
        encoders.encode_base64(part)
        part.add_header('Content-Disposition', f'attachment; filename="{nome_arquivo}"')
        msg.attach(part)

        # 4. Envio via TLS (Porta 587)
        # O Gmail prefere esse método para evitar SPAM
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls() # Criptografa a conexão
        server.login(usuario, senha)
        text = msg.as_string()
        server.sendmail(usuario, destinatario, text)
        server.quit()
            
        return True

    except Exception as e:
        return f"Erro técnico: {e}"
