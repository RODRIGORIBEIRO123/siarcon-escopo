import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
from datetime import datetime

# --- 1. CONEXÃO CENTRAL ---
def conectar_google_sheets():
    scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scope)
    client = gspread.authorize(creds)
    return client.open("DB_SIARCON")

# --- 2. CONFIGURAÇÕES (CARREGAR LISTAS) ---
def carregar_opcoes():
    try:
        sh = conectar_google_sheets()
        ws = sh.worksheet("Config")
        data = ws.get_all_records()
        df = pd.DataFrame(data)
        return {
            "tecnico": df[df["Categoria"] == "tecnico"]["Item"].tolist(),
            "qualidade": df[df["Categoria"] == "qualidade"]["Item"].tolist(),
            "sms": df[df["Categoria"] == "sms"]["Item"].tolist()
        }
    except:
        return {"tecnico": [], "qualidade": [], "sms": []}

def aprender_novo_item(categoria, novo_item):
    try:
        sh = conectar_google_sheets()
        ws = sh.worksheet("Config")
        ws.append_row([categoria, novo_item])
        return True
    except: return False

# --- 3. GESTÃO DE PROJETOS (LEITURA INTELIGENTE) ---
def listar_todos_projetos():
    try:
        sh = conectar_google_sheets()
        ws = sh.worksheet("Projetos")
        # Pega todos os valores (lista de listas)
        rows = ws.get_all_values()
        
        if len(rows) < 2: return pd.DataFrame()
        
        # Cria DataFrame manual
        header = rows[0]
        data = rows[1:]
        
        df = pd.DataFrame(data, columns=header)
        # Adiciona ID da linha (Excel começa em 1, Header é 1, dados começam em 2)
        df['_id_linha'] = range(2, len(data) + 2) 
        return df
    except Exception as e:
        st.error(f"Erro ao ler lista: {e}")
        return pd.DataFrame()

# --- 4. SALVAR E ATUALIZAR ---
def registrar_projeto(dados, id_linha=None):
    """
    Se id_linha for None -> Cria nova linha.
    Se id_linha existir -> Atualiza a linha existente.
    """
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
            dados.get('status', 'Em Elaboração (Engenharia)')
        ]
        
        if id_linha:
            # --- CORREÇÃO AQUI ---
            # O parâmetro correto é range_name, não range_cells
            range_celulas = f"A{id_linha}:G{id_linha}"
            ws.update(range_name=range_celulas, values=[linha])
        else:
            # Cria nova
            ws.append_row(linha)
            
    except Exception as e:
        st.error(f"Erro ao salvar: {e}")
