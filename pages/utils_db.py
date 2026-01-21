import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
from datetime import datetime

# --- CONEXÃO ---
def conectar_google_sheets():
    scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scope)
    client = gspread.authorize(creds)
    # Abre a planilha pelo nome
    return client.open("DB_SIARCON")

# --- FUNÇÕES DE LEITURA (CARREGAR OPÇÕES) ---
def carregar_opcoes():
    """Lê a aba 'Config' e retorna as listas de opções para os selects."""
    try:
        sh = conectar_google_sheets()
        ws = sh.worksheet("Config")
        data = ws.get_all_records()
        df = pd.DataFrame(data)
        
        # Filtra por categoria
        opcoes = {
            "tecnico": df[df["Categoria"] == "tecnico"]["Item"].tolist(),
            "qualidade": df[df["Categoria"] == "qualidade"]["Item"].tolist(),
            "sms": df[df["Categoria"] == "sms"]["Item"].tolist()
        }
        return opcoes
    except Exception as e:
        st.error(f"Erro ao carregar opções: {e}")
        return {"tecnico": [], "qualidade": [], "sms": []}

# --- FUNÇÕES DE ESCRITA (APRENDER E SALVAR) ---
def aprender_novo_item(categoria, novo_item):
    """Adiciona um novo item na aba 'Config'."""
    try:
        sh = conectar_google_sheets()
        ws = sh.worksheet("Config")
        # Adiciona linha: [Categoria, Item]
        ws.append_row([categoria, novo_item])
        return True
    except Exception as e:
        st.error(f"Erro ao salvar novo item: {e}")
        return False

def registrar_projeto(dados):
    """Salva o log do projeto na aba 'Projetos'."""
    try:
        sh = conectar_google_sheets()
        ws = sh.worksheet("Projetos")
        # [Data, Cliente, Obra, Fornecedor, Responsável, Valor, Status]
        linha = [
            datetime.now().strftime("%d/%m/%Y %H:%M"),
            dados['cliente'],
            dados['obra'],
            dados['fornecedor'],
            dados['responsavel'],
            dados['valor_total'],
            "Gerado"
        ]
        ws.append_row(linha)
    except Exception as e:
        st.warning(f"O documento foi gerado, mas houve erro ao salvar no histórico: {e}")
