import streamlit as st
import pandas as pd
import gspread
from datetime import datetime

# ==================================================
# 1. LISTA PADRÃO NRs
# ==================================================
NRS_PADRAO = [
    "NR-01 (Disposições Gerais)", "NR-03 (Embargo e Interdição)", "NR-04 (SESMT)",
    "NR-05 (CIPA)", "NR-06 (EPI)", "NR-07 (PCMSO)", "NR-08 (Edificações)",
    "NR-09 (Avaliação e Controle de Exposições)", "NR-10 (Eletricidade)",
    "NR-11 (Transporte e Movimentação)", "NR-12 (Máquinas e Equipamentos)",
    "NR-13 (Vasos de Pressão)", "NR-15 (Insalubridade)", "NR-16 (Periculosidade)",
    "NR-17 (Ergonomia)", "NR-18 (Construção Civil)", "NR-23 (Incêndios)",
    "NR-24 (Condições Sanitárias)", "NR-26 (Sinalização)",
    "NR-33 (Espaços Confinados)", "NR-35 (Trabalho em Altura)"
]

# ==================================================
# 2. CONEXÃO
# ==================================================
def _conectar_gsheets():
    try:
        if "gcp_service_account" not in st.secrets: return None
        creds_dict = dict(st.secrets["gcp_service_account"])
        if "private_key" in creds_dict:
            chave = creds_dict["private_key"]
            if "\n" not in chave: creds_dict["private_key"] = chave.replace("\\n", "\n")
        gc = gspread.service_account_from_dict(creds_dict)
        return gc.open("DB_SIARCON") 
    except: return None

def _ler_aba_como_df(nome_aba):
    sh = _conectar_gsheets()
    if not sh: return pd.DataFrame()
    try:
        try: ws = sh.worksheet(nome_aba)
        except: 
            if nome_aba == "Dados":
                for n in ["Página1", "Sheet1", "Config"]:
                    try: ws = sh.worksheet(n); break
                    except: pass
                else: return pd.DataFrame()
            else: return pd.DataFrame()
        return pd.DataFrame(ws.get_all_records())
    except: return pd.DataFrame()

# ==================================================
# 3. LEITURA DE DADOS
# ==================================================
def carregar_opcoes():
    df = _ler_aba_como_df("Dados")
    opcoes = {'sms': NRS_PADRAO.copy()} 
    if not df.empty and 'Categoria' in df.columns and 'Item' in df.columns:
        df['Categoria'] = df['Categoria'].astype(str).str.lower().str.strip()
        for cat in df['Categoria'].unique():
            itens = sorted(df[df['Categoria'] == cat]['Item'].unique().tolist())
            if cat == 'sms': opcoes['sms'] = sorted(list(set(opcoes['sms'] + itens)))
            else: opcoes[cat] = itens     
    return opcoes

def listar_fornecedores():
    sh = _conectar_gsheets()
    if not sh: return []
    try:
        ws = sh.worksheet("FORNECEDORES")
        vals = ws.get_all_values()
        if len(vals) > 1:
            lista = []
            for row in vals[1:]:
                if row[0]: lista.append({'Fornecedor': row[0], 'CNPJ': row[1] if len(row) > 1 else ""})
            return lista
    except: pass
    df = _ler_aba_como_df("Dados")
    if not df.empty and 'Fornecedor' in df.columns:
        return df[['Fornecedor', 'CNPJ']].dropna(subset=['Fornecedor']).drop_duplicates().to_dict('records')
    return []

# ==================================================
# 4. FUNÇÕES DO PROJETO (DASHBOARD)
# ==================================================
def listar_todos_projetos():
    df = _ler_aba_como_df("Projetos")
    cols = ['_id', 'status', 'disciplina', 'cliente', 'obra', 'fornecedor', 'valor_total', 'data_inicio']
    if df.empty: return pd.DataFrame(columns=cols)
    for c in cols: 
        if c not in df.columns: df[c] = ""
    if '_id' in df.columns: df['_id'] = df['_id'].astype(str)
    return df

def buscar_projeto_por_id(id_projeto):
    """Busca os dados completos de um projeto pelo ID."""
    df = listar_todos_projetos()
    if df.empty: return None
    projeto = df[df['_id'] == str(id_projeto)]
    if not projeto.empty:
        return projeto.iloc[0].to_dict()
    return None

def atualizar_status_projeto(id_projeto, novo_status):
    sh = _conectar_gsheets()
    if not sh: return False
    try:
        ws = sh.worksheet("Projetos")
        cell = ws.find(str(id_projeto))
        if cell:
            headers = ws.row_values(1)
            if 'status' in headers:
                col_index = headers.index('status') + 1
                ws.update_cell(cell.row, col_index, novo_status)
                return True
    except: pass
    return False

# ==================================================
# 5. ESCRITA
# ==================================================
def aprender_novo_item(categoria, novo_item):
    sh = _conectar_gsheets()
    if not sh: return False
    try:
        try: ws = sh.worksheet("Dados")
        except: ws = sh.add_worksheet("Dados", 100, 10)
        ws.append_row([categoria.lower(), novo_item, "", ""])
        return True
    except: return False

def cadastrar_fornecedor_db(nome, cnpj):
    sh = _conectar_gsheets()
    if not sh: return False
    try:
        ws = sh.worksheet("FORNECEDORES")
        ws.append_row([nome, cnpj])
        return True
    except:
        try: ws = sh.worksheet("Dados"); ws.append_row(["", "", nome, cnpj]); return True
        except: return False

def registrar_projeto(dados):
    sh = _conectar_gsheets()
    if not sh: return False
    try:
        try: ws = sh.worksheet("Projetos")
        except: 
            ws = sh.add_worksheet("Projetos", 100, 20)
            ws.append_row(['_id', 'status', 'disciplina', 'cliente', 'obra', 'fornecedor', 'valor_total', 'data_inicio'])
        
        headers = ws.row_values(1)
        if not headers: 
            headers = ['_id', 'status', 'disciplina', 'cliente', 'obra', 'fornecedor', 'valor_total', 'data_inicio']
            ws.append_row(headers)

        if '_id' not in dados: dados['_id'] = datetime.now().strftime("%Y%m%d%H%M%S")

        # Se o projeto já existe (edição), atualizamos a linha. Se não, criamos nova.
        cell = None
        try: cell = ws.find(str(dados['_id']))
        except: pass

        row_data = []
        for h in headers: row_data.append(str(dados.get(h, "")))

        if cell: # Atualizar linha existente
            for i, val in enumerate(row_data):
                ws.update_cell(cell.row, i+1, val)
        else: # Inserir nova linha
            ws.append_row(row_data)
        return True
    except: return False
