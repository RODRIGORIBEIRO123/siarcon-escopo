import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
from datetime import datetime

# ==========================================
# 1. CONEXÃO
# ==========================================
def conectar_google_sheets():
    try:
        scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scope)
        client = gspread.authorize(creds)
        return client.open("DB_SIARCON")
    except Exception as e:
        st.error(f"Erro de conexão: {e}")
        return None

# ==========================================
# 2. CONFIGURAÇÕES & FORNECEDORES
# ==========================================
def carregar_opcoes():
    try:
        sh = conectar_google_sheets()
        if not sh: return {}
        ws = sh.worksheet("Config")
        data = ws.get_all_records()
        df = pd.DataFrame(data)
        
        def get_list(cat): return df[df["Categoria"] == cat]["Item"].tolist()
        
        return {
            "tecnico": get_list("tecnico"),
            "qualidade": get_list("qualidade"),
            "tecnico_hidraulica": get_list("tecnico_hidraulica"),
            "qualidade_hidraulica": get_list("qualidade_hidraulica"),
            "tecnico_eletrica": get_list("tecnico_eletrica"),
            "qualidade_eletrica": get_list("qualidade_eletrica"),
            "tecnico_automacao": get_list("tecnico_automacao"),
            "qualidade_automacao": get_list("qualidade_automacao"),
            "tecnico_tab": get_list("tecnico_tab"),
            "qualidade_tab": get_list("qualidade_tab"),
            "tecnico_movimentacao": get_list("tecnico_movimentacao"),
            "qualidade_movimentacao": get_list("qualidade_movimentacao"),
            "tecnico_cobre": get_list("tecnico_cobre"),
            "qualidade_cobre": get_list("qualidade_cobre"),
            "sms": get_list("sms")
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

# --- GESTÃO DE FORNECEDORES ---
def listar_fornecedores():
    try:
        sh = conectar_google_sheets()
        if not sh: return []
        ws = sh.worksheet("Fornecedores")
        # Retorna lista de dicionários [{'Fornecedor': 'Nome', 'CNPJ': '000...'}]
        return ws.get_all_records()
    except: return []

def cadastrar_fornecedor_db(nome, cnpj):
    try:
        sh = conectar_google_sheets()
        if not sh: return False
        ws = sh.worksheet("Fornecedores")
        # Verifica duplicidade simples pelo nome
        cell = ws.find(nome)
        if cell: return "Existe"
        
        ws.append_row([nome, cnpj])
        return True
    except: return False

# ==========================================
# 3. GESTÃO DE PROJETOS
# ==========================================
def listar_todos_projetos():
    try:
        sh = conectar_google_sheets()
        if not sh: return pd.DataFrame()
        ws = sh.worksheet("Projetos")
        rows = ws.get_all_values()
        if len(rows) < 2: return pd.DataFrame()
        
        colunas_padrao = ["Data", "Cliente", "Obra", "Fornecedor", "Responsavel", "Valor", "Status", "Resp_Obras", "Disciplina", "CNPJ"]
        
        dados_tratados = []
        for i, row in enumerate(rows[1:]):
            if len(row) < 3: continue
            if not str(row[1]).strip() and not str(row[2]).strip(): continue
            
            linha_normalizada = row + [""] * (len(colunas_padrao) - len(row))
            linha_final = linha_normalizada[:len(colunas_padrao)]
            dados_com_id = linha_final + [i + 2] 
            dados_tratados.append(dados_com_id)
            
        cols_df = colunas_padrao + ["_id_linha"]
        df = pd.DataFrame(dados_tratados, columns=cols_df)
        return df
    except Exception as e:
        st.error(f"Erro ao ler lista: {e}")
        return pd.DataFrame()

# ==========================================
# 4. CRIAR PACOTE
# ==========================================
def criar_pacote_obra(cliente, obra, lista_disciplinas):
    try:
        sh = conectar_google_sheets()
        if not sh: return False
        ws = sh.worksheet("Projetos")
        col_a = ws.col_values(1); proxima_linha = len(col_a) + 1
        
        novas_linhas = []
        data_hoje = datetime.now().strftime("%d/%m/%Y %H:%M")
        
        for disciplina in lista_disciplinas:
            # Inclui coluna vazia pro CNPJ no final (índice 9)
            linha = [str(data_hoje), str(cliente), str(obra), "", "", "", "Não Iniciado", "", str(disciplina), ""]
            novas_linhas.append(linha)
        
        linha_final = proxima_linha + len(novas_linhas) - 1
        range_name = f"A{proxima_linha}:J{linha_final}" # A até J agora
        ws.update(range_name=range_name, values=novas_linhas)
        return True
    except Exception as e:
        st.error(f"Erro ao criar obra: {e}")
        return False

# ==========================================
# 5. SALVAR/REGISTRAR
# ==========================================
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
            dados.get('disciplina', ''),
            dados.get('cnpj_fornecedor', '') # Novo Campo
        ]
        
        if id_linha:
            range_celulas = f"A{id_linha}:J{id_linha}" # Até J
            ws.update(range_name=range_celulas, values=[linha])
        else:
            col_a = ws.col_values(1); proxima_linha = len(col_a) + 1
            range_celulas = f"A{proxima_linha}:J{proxima_linha}"
            ws.update(range_name=range_celulas, values=[linha])
            
    except Exception as e:
        st.error(f"Erro ao salvar: {e}")

# ==========================================
# 6. EXCLUIR
# ==========================================
def excluir_projeto(id_linha):
    try:
        sh = conectar_google_sheets()
        if not sh: return False
        ws = sh.worksheet("Projetos")
        ws.delete_rows(id_linha)
        return True
    except: return False
