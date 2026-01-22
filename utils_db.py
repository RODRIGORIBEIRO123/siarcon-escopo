O erro SyntaxError indica que houve algum problema na cópia do código (talvez um parêntese faltando ou indentação incorreta). Além disso, para garantir que o botão de excluir fique ao lado do editar, vamos ajustar a distribuição das colunas dentro do cartão do Kanban.

Vamos corrigir isso agora mesmo.
1. Atualizar utils_db.py (Garantia)

Só para garantir que a função de excluir existe e não há erros de sintaxe aqui.
Python

import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
from datetime import datetime

# --- 1. CONEXÃO CENTRAL ---
def conectar_google_sheets():
    try:
        scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scope)
        client = gspread.authorize(creds)
        return client.open("DB_SIARCON")
    except Exception as e:
        st.error(f"Erro de conexão: {e}")
        return None

# --- 2. CONFIGURAÇÕES ---
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
        
        if not df.empty:
            ja_existe = df[(df['Categoria'] == categoria) & (df['Item'].astype(str).str.lower() == novo_item.lower())]
            if not ja_existe.empty: return "Duplicado"

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
        # Recalcula o ID baseado na linha real do sheets (linha 1 é header, dados começam na 2)
        df['_id_linha'] = range(2, len(data) + 2) 
        return df
    except Exception as e:
        st.error(f"Erro ao ler lista: {e}")
        return pd.DataFrame()

# --- 4. SALVAR ---
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
            range_celulas = f"A{id_linha}:H{id_linha}"
            ws.update(range_name=range_celulas, values=[linha])
        else:
            ws.append_row(linha)
            
    except Exception as e:
        st.error(f"Erro ao salvar: {e}")

# --- 5. EXCLUIR ---
def excluir_projeto(id_linha):
    try:
        sh = conectar_google_sheets()
        if not sh: return False
        ws = sh.worksheet("Projetos")
        ws.delete_rows(id_linha)
        return True
    except Exception as e:
        st.error(f"Erro ao excluir: {e}")
        return False
