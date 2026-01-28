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
        # Tenta achar a aba pelo nome exato, ou tenta variações
        try: ws = sh.worksheet(nome_aba)
        except: 
            if nome_aba == "Dados":
                # Fallbacks para a aba de Configuração
                for n in ["Página1", "Sheet1", "Config"]:
                    try: 
                        ws = sh.worksheet(n)
                        break
                    except: pass
                else: return pd.DataFrame()
            else: return pd.DataFrame()
        
        dados = ws.get_all_records()
        return pd.DataFrame(dados)
    except: return pd.DataFrame()

# ==================================================
# 3. LEITURA DE ITENS (CATEGORIAS)
# ==================================================
def carregar_opcoes():
    """Lê itens técnicos e NRs da aba 'Dados' ou 'DUTOS' se configurado."""
    df = _ler_aba_como_df("Dados")
    opcoes = {'sms': NRS_PADRAO.copy()} 

    if not df.empty and 'Categoria' in df.columns and 'Item' in df.columns:
        df['Categoria'] = df['Categoria'].astype(str).str.lower().str.strip()
        categorias = df['Categoria'].unique()
        
        for cat in categorias:
            itens = sorted(df[df['Categoria'] == cat]['Item'].unique().tolist())
            if cat == 'sms':
                opcoes['sms'] = sorted(list(set(opcoes['sms'] + itens)))
            else:
                opcoes[cat] = itens     
    return opcoes

# ==================================================
# 4. LEITURA DE FORNECEDORES (INTELIGENTE)
# ==================================================
def listar_fornecedores():
    """
    Procura fornecedores na aba 'FORNECEDORES' (Col A=Nome, B=CNPJ)
    Se não achar, procura na aba 'Dados' (Col C=Fornecedor, D=CNPJ)
    """
    sh = _conectar_gsheets()
    if not sh: return []
    
    # 1. TENTA A ABA ESPECÍFICA 'FORNECEDORES'
    try:
        ws = sh.worksheet("FORNECEDORES")
        # Assume que Coluna 1 é Nome, Coluna 2 é CNPJ
        vals = ws.get_all_values()
        if len(vals) > 1: # Tem cabeçalho e dados
            lista = []
            # Pula cabeçalho (index 0)
            for row in vals[1:]:
                if row[0]: # Se tem nome
                    cnpj = row[1] if len(row) > 1 else ""
                    lista.append({'Fornecedor': row[0], 'CNPJ': cnpj})
            return lista
    except:
        pass # Se der erro, tenta o método antigo

    # 2. FALLBACK: TENTA A ABA 'Dados'
    df = _ler_aba_como_df("Dados")
    if not df.empty and 'Fornecedor' in df.columns:
        return df[['Fornecedor', 'CNPJ']].dropna(subset=['Fornecedor']).drop_duplicates().to_dict('records')
    
    return []

# ==================================================
# 5. ESCRITA (CADASTROS)
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
    
    # Tenta salvar na aba FORNECEDORES se ela existir
    try:
        ws = sh.worksheet("FORNECEDORES")
        ws.append_row([nome, cnpj])
        return True
    except:
        # Se não, salva na aba Dados
        try:
            ws = sh.worksheet("Dados")
            ws.append_row(["", "", nome, cnpj])
            return True
        except: 
            return False

# ==================================================
# 6. REGISTRO DE PROJETOS (RECRIAR ABA SE PRECISAR)
# ==================================================
def listar_todos_projetos():
    df = _ler_aba_como_df("Projetos")
    cols_esperadas = ['_id', 'status', 'disciplina', 'cliente', 'obra', 'fornecedor', 'valor_total', 'data_inicio']
    
    if df.empty: return pd.DataFrame(columns=cols_esperadas)
    for col in cols_esperadas:
        if col not in df.columns: df[col] = ""
    if '_id' in df.columns: df['_id'] = df['_id'].astype(str)
    return df

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

        row_data = []
        for h in headers: row_data.append(str(dados.get(h, "")))
        ws.append_row(row_data)
        return True
    except: return False
