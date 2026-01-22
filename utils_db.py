import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
from datetime import datetime

# --- 1. CONEXÃO CENTRAL ---
def conectar_google_sheets():
    """Conecta ao Google Sheets usando as credenciais do Streamlit Secrets."""
    scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scope)
    client = gspread.authorize(creds)
    # Abre a planilha pelo nome exato
    return client.open("DB_SIARCON")

# --- 2. GERENCIAMENTO DE OPÇÕES (Aba 'Config') ---
def carregar_opcoes():
    """Lê a aba 'Config' e retorna as listas de opções para os selects."""
    try:
        sh = conectar_google_sheets()
        ws = sh.worksheet("Config")
        data = ws.get_all_records()
        df = pd.DataFrame(data)
        
        # Cria um dicionário filtrando por categoria
        opcoes = {
            "tecnico": df[df["Categoria"] == "tecnico"]["Item"].tolist(),
            "qualidade": df[df["Categoria"] == "qualidade"]["Item"].tolist(),
            "sms": df[df["Categoria"] == "sms"]["Item"].tolist()
        }
        return opcoes
    except Exception as e:
        # Se der erro (ex: aba vazia), retorna listas vazias para não travar o app
        return {"tecnico": [], "qualidade": [], "sms": []}

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

# --- 3. GERENCIAMENTO DE PROJETOS (Aba 'Projetos') ---
def registrar_projeto(dados):
    """Salva o log do projeto na aba 'Projetos' quando a Engenharia gera o escopo."""
    try:
        sh = conectar_google_sheets()
        ws = sh.worksheet("Projetos")
        # Ordem das colunas: Data | Cliente | Obra | Fornecedor | Responsável | Valor | Status
        linha = [
            datetime.now().strftime("%d/%m/%Y %H:%M"),
            dados['cliente'],
            dados['obra'],
            dados['fornecedor'],
            dados['responsavel'],
            dados['valor_total'],
            "Gerado" # Status inicial
        ]
        ws.append_row(linha)
    except Exception as e:
        st.warning(f"O documento foi gerado, mas houve erro ao salvar no histórico: {e}")

def listar_todos_projetos():
    """Lê a aba 'Projetos' inteira e retorna um DataFrame (tabela) para o Dashboard."""
    try:
        sh = conectar_google_sheets()
        ws = sh.worksheet("Projetos")
        data = ws.get_all_records()
        
        # Converte para tabela do Pandas
        df = pd.DataFrame(data)
        return df
    except Exception as e:
        st.error(f"Erro ao ler lista de projetos: {e}")
        return pd.DataFrame() # Retorna tabela vazia se der erro
