import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
from datetime import datetime

# --- 1. CONEXÃO CENTRAL ---
def conectar_google_sheets():
    try:
        # Define o escopo de acesso
        scope = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive"
        ]
        # Carrega credenciais do secrets
        creds = Credentials.from_service_account_info(
            st.secrets["gcp_service_account"], 
            scopes=scope
        )
        # Autoriza e abre a planilha
        client = gspread.authorize(creds)
        return client.open("DB_SIARCON")
    except Exception as e:
        st.error(f"Erro de conexão com o Google Sheets: {e}")
        return None

# --- 2. CONFIGURAÇÕES (CARREGAR LISTAS) ---
def carregar_opcoes():
    try:
        sh = conectar_google_sheets()
        if not sh: return {"tecnico": [], "qualidade": [], "sms": []}
        
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
        if not sh: return False
        
        ws = sh.worksheet("Config")
        data = ws.get_all_records()
        df = pd.DataFrame(data)
        
        # Verifica duplicidade
        if not df.empty:
            ja_existe = df[
                (df['Categoria'] == categoria) & 
                (df['Item'].astype(str).str.lower() == novo_item.lower())
            ]
            if not ja_existe.empty:
                return "Duplicado"

        ws.append_row([categoria, novo_item])
        return True
    except:
        return False

# --- 3. GESTÃO DE PROJETOS ---
def listar_todos_projetos():
    try:
        sh = conectar_google_sheets()
        if not sh: return pd.DataFrame()
        
        ws = sh.worksheet("Projetos")
        rows = ws.get_all_values()
        
        if len(rows) < 2: return pd.DataFrame()
        
        header = rows[0]
        data = rows[1:]
        
        df = pd.DataFrame(data, columns=header)
        # Cria ID baseado na linha real (Header é 1, dados começam em 2)
        df['_id_linha'] = range(2, len(data) + 2) 
        return df
    except Exception as e:
        st.error(f"Erro ao ler lista de projetos: {e}")
        return pd.DataFrame()

# --- 4. SALVAR E ATUALIZAR ---
def registrar_projeto(dados, id_linha=None):
    try:
        sh = conectar_google_sheets()
        if not sh: return
        
        ws = sh.worksheet("Projetos")
        
        linha = [
            datetime.now().strftime("%d/%m/%Y %H:%M"),
            dados['cliente'],
            dados['obra'],
            dados['fornecedor'],
            dados['responsavel'],     
            dados['valor_total'],
            dados.get('status', 'Em Elaboração (Engenharia)'),
            dados.get('resp_obras', '')
        ]
        
        if id_linha:
            # Atualiza colunas A até H
            range_celulas = f"A{id_linha}:H{id_linha}"
            ws.update(range_name=range_celulas, values=[linha])
        else:
            ws.append_row(linha)
            
    except Exception as e:
        st.error(f"Erro ao salvar projeto: {e}")

# --- 5. EXCLUIR ---
def excluir_projeto(id_linha):
    try:
        sh = conectar_google_sheets()
        if not sh: return False
        
        ws = sh.worksheet("Projetos")
        ws.delete_rows(id_linha)
        return True
    except Exception as e:
        st.error(f"Erro ao excluir projeto: {e}")
        return False
