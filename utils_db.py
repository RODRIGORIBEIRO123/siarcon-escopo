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
        print(f"Erro conexão: {e}")
        return None

def _ler_aba_como_df(nome_aba):
    sh = _conectar_gsheets()
    if not sh: return pd.DataFrame()
    try:
        try: ws = sh.worksheet(nome_aba)
        except: 
            # Tenta criar se não existir ou procura nomes alternativos
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
    cols = ['_id', 'status', 'disciplina', 'cliente', 'obra', 'prazo', 'fornecedor', 'valor_total', 'data_inicio']
    
    if df.empty: return pd.DataFrame(columns=cols)
    
    # Garante colunas mínimas
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

# --- AQUI ESTÁ A CORREÇÃO DO ERRO ---
# O Dashboard chama 'salvar_projeto'. As páginas internas chamam 'registrar_projeto'.
# Mantemos as duas apontando para a mesma lógica para não quebrar nada.

def salvar_projeto(dados):
    return registrar_projeto(dados)

def registrar_projeto(dados):
    """Salva ou Atualiza um projeto no Google Sheets"""
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

        # Gera ID se não tiver
        if '_id' not in dados or not dados['_id']: 
            dados['_id'] = datetime.now().strftime("%Y%m%d%H%M%S")

        # Prepara linha na ordem das colunas
        row_data = []
        for h in headers:
            row_data.append(str(dados.get(h, "")))

        # Verifica se atualiza ou cria
        cell = None
        try: cell = ws.find(str(dados['_id']))
        except: pass

        if cell: 
            # Atualiza linha existente
            ws.update(range_name=f"A{cell.row}", values=[row_data])
        else: 
            # Cria nova linha
            ws.append_row(row_data)
        
        return True
    except Exception as e: 
        print(f"Erro ao salvar: {e}")
        return False

# ==================================================
# 3. AUXILIARES (FORNECEDORES E LISTAS)
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
    
    # Fallback
    df = _ler_aba_como_df("Dados")
    if not df.empty and 'Fornecedor' in df.columns:
        return df[['Fornecedor', 'CNPJ']].dropna(subset=['Fornecedor']).drop_duplicates().to_dict('records')
    return []

def carregar_opcoes():
    # Carrega listas técnicas do banco
    df = _ler_aba_como_df("Dados")
    opcoes = {'sms': []}
    if not df.empty and 'Categoria' in df.columns and 'Item' in df.columns:
        df['Categoria'] = df['Categoria'].astype(str).str.lower().str.strip()
        for cat in df['Categoria'].unique():
            itens = sorted(df[df['Categoria'] == cat]['Item'].unique().tolist())
            opcoes[cat] = itens
    return opcoes

def aprender_novo_item(categoria, novo_item):
    sh = _conectar_gsheets()
    if not sh: return False
    try:
        try: ws = sh.worksheet("Dados")
        except: ws = sh.add_worksheet("Dados", 100, 10)
        ws.append_row([categoria.lower(), novo_item, "", ""])
        return True
    except: return False
