import streamlit as st
import pandas as pd
import gspread
from datetime import datetime

# ==================================================
# 1. CONEXÃO E CACHE
# ==================================================
@st.cache_resource(ttl=600)
def _conectar_gsheets():
    try:
        if "gcp_service_account" not in st.secrets: return None
        creds_dict = dict(st.secrets["gcp_service_account"])
        if "private_key" in creds_dict:
            chave = creds_dict["private_key"]
            if "\n" not in chave: creds_dict["private_key"] = chave.replace("\\n", "\n")
        
        gc = gspread.service_account_from_dict(creds_dict)
        return gc.open("DB_SIARCON") 
    except Exception as e:
        # print(f"Erro conexão: {e}") # Comentado para limpar log
        return None

def _ler_aba_como_df(nome_aba):
    sh = _conectar_gsheets()
    if not sh: return pd.DataFrame()
    try:
        try: ws = sh.worksheet(nome_aba)
        except: 
            if nome_aba == "Dados":
                for n in ["Página1", "Sheet1"]:
                    try: ws = sh.worksheet(n); break
                    except: pass
                else: return pd.DataFrame()
            else: return pd.DataFrame()
        
        data = ws.get_all_records()
        return pd.DataFrame(data)
    except: return pd.DataFrame()

# ==================================================
# 2. FUNÇÕES PRINCIPAIS (PROJETOS)
# ==================================================

def listar_todos_projetos():
    df = _ler_aba_como_df("Projetos")
    cols = ['_id', 'status', 'disciplina', 'cliente', 'obra', 'prazo', 'fornecedor', 'valor_total', 'data_inicio', 'criado_por']
    if df.empty: return pd.DataFrame(columns=cols)
    for c in cols: 
        if c not in df.columns: df[c] = ""
    if '_id' in df.columns: df['_id'] = df['_id'].astype(str)
    return df

def buscar_projeto_por_id(id_projeto):
    df = listar_todos_projetos()
    if df.empty: return None
    projeto = df[df['_id'] == str(id_projeto)]
    if not projeto.empty:
        return projeto.iloc[0].to_dict()
    return None

def salvar_projeto(dados):
    return registrar_projeto(dados)

def registrar_projeto(dados):
    sh = _conectar_gsheets()
    if not sh: return False
    try:
        try: ws = sh.worksheet("Projetos")
        except: 
            ws = sh.add_worksheet("Projetos", 100, 20)
            ws.append_row(['_id', 'status', 'disciplina', 'cliente', 'obra', 'prazo', 'fornecedor', 'valor_total'])
        
        headers = ws.row_values(1)
        if not headers: 
            headers = ['_id', 'status', 'disciplina', 'cliente', 'obra', 'prazo']
            ws.append_row(headers)

        if '_id' not in dados or not dados['_id']: 
            dados['_id'] = datetime.now().strftime("%Y%m%d%H%M%S")

        row_data = []
        for h in headers:
            row_data.append(str(dados.get(h, "")))

        cell = None
        try: cell = ws.find(str(dados['_id']))
        except: pass

        if cell: 
            ws.update(range_name=f"A{cell.row}", values=[row_data])
        else: 
            ws.append_row(row_data)
        return True
    except Exception as e: 
        print(f"Erro ao salvar: {e}")
        return False

# --- FUNÇÃO DE EXCLUSÃO (ESSENCIAL PARA A LIXEIRA) ---
def excluir_projeto(id_projeto):
    sh = _conectar_gsheets()
    if not sh: return False
    try:
        ws = sh.worksheet("Projetos")
        cell = ws.find(str(id_projeto))
        if cell:
            ws.delete_rows(cell.row)
            return True
    except: pass
    return False

# ==================================================
# 3. AUXILIARES
# ==================================================

def listar_fornecedores():
    sh = _conectar_gsheets()
    if not sh: return []
    try:
        ws = sh.worksheet("FORNECEDORES")
        vals = ws.get_all_values()
        if len(vals) > 1:
            lista = []
            for row in vals[1:]:
                if row and row[0]: 
                    cnpj = row[1] if len(row) > 1 else ""
                    lista.append({'Fornecedor': row[0], 'CNPJ': cnpj})
            return lista
    except: pass
    df = _ler_aba_como_df("Dados")
    if not df.empty and 'Fornecedor' in df.columns:
        return df[['Fornecedor', 'CNPJ']].dropna(subset=['Fornecedor']).drop_duplicates().to_dict('records')
    return []

def carregar_opcoes():
    df = _ler_aba_como_df("Dados")
    opcoes
