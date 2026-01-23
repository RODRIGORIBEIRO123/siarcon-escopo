import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
from datetime import datetime

# --- 1. CONEXÃO ---
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
        if not sh: return {}
        ws = sh.worksheet("Config")
        data = ws.get_all_records()
        df = pd.DataFrame(data)
        return {
            "tecnico": df[df["Categoria"] == "tecnico"]["Item"].tolist(),
            "qualidade": df[df["Categoria"] == "qualidade"]["Item"].tolist(),
            "tecnico_hidraulica": df[df["Categoria"] == "tecnico_hidraulica"]["Item"].tolist(),
            "qualidade_hidraulica": df[df["Categoria"] == "qualidade_hidraulica"]["Item"].tolist(),
            "sms": df[df["Categoria"] == "sms"]["Item"].tolist()
        }
    except: return {}

def aprender_novo_item(categoria, novo_item):
    try:
        sh = conectar_google_sheets()
        if not sh: return False
        ws = sh.worksheet("Config")
        ws.append_row([categoria, novo_item])
        return True
    except: return False

# --- 3. GESTÃO DE PROJETOS (CORRIGIDO) ---
def listar_todos_projetos():
    try:
        sh = conectar_google_sheets()
        if not sh: return pd.DataFrame()
        ws = sh.worksheet("Projetos")
        rows = ws.get_all_values()
        
        if len(rows) < 2: return pd.DataFrame()
        
        header = rows[0]
        data = rows[1:]
        
        # CORREÇÃO: Garante que o cabeçalho tenha o tamanho dos dados
        # Se os dados têm 9 colunas e o header só tem 8, adiciona "Disciplina" na força
        max_cols = max([len(r) for r in data]) if data else len(header)
        
        while len(header) < max_cols:
            if len(header) == 8: # A 9ª coluna é sempre Disciplina
                header.append("Disciplina")
            else:
                header.append(f"Col_{len(header)+1}")
        
        # Normaliza linhas de dados para ter o mesmo tamanho do header
        data_normalizada = []
        for row in data:
            while len(row) < len(header):
                row.append("")
            data_normalizada.append(row)
            
        df = pd.DataFrame(data_normalizada, columns=header)
        df['_id_linha'] = range(2, len(data) + 2) 
        return df
    except Exception as e:
        st.error(f"Erro ao ler: {e}")
        return pd.DataFrame()

# --- 4. CRIAR PACOTE ---
def criar_pacote_obra(cliente, obra, lista_disciplinas):
    try:
        sh = conectar_google_sheets()
        if not sh: return False
        ws = sh.worksheet("Projetos")
        
        novas_linhas = []
        data_hoje = datetime.now().strftime("%d/%m/%Y %H:%M")
        
        for disciplina in lista_disciplinas:
            linha = [
                data_hoje, cliente, obra, "", "", "", 
                "Não Iniciado", "", disciplina
            ]
            novas_linhas.append(linha)
            
        ws.append_rows(novas_linhas)
        return True
    except Exception as e:
        st.error(f"Erro ao criar obra: {e}")
        return False

# --- 5. SALVAR ---
def registrar_projeto(dados, id_linha=None):
    try:
        sh = conectar_google_sheets()
        if not sh: return
        ws = sh.worksheet("Projetos")
        
        linha = [
            datetime.now().strftime("%d/%m/%Y %H:%M"),
            dados['cliente'], dados['obra'], dados['fornecedor'],
            dados['responsavel'], dados['valor_total'],
            dados.get('status', 'Em Elaboração (Engenharia)'),
            dados.get('resp_obras', ''),
            dados.get('disciplina', '')
        ]
        
        if id_linha:
            range_celulas = f"A{id_linha}:I{id_linha}"
            ws.update(range_name=range_celulas, values=[linha])
        else:
            ws.append_row(linha)
    except Exception as e:
        st.error(f"Erro ao salvar: {e}")

# --- 6. EXCLUIR ---
def excluir_projeto(id_linha):
    try:
        sh = conectar_google_sheets()
        if not sh: return False
        ws = sh.worksheet("Projetos")
        ws.delete_rows(id_linha)
        return True
    except: return False
