import streamlit as st
import pandas as pd
import gspread

# ==================================================
# 1. LISTA PADRÃO NRs (FIXA)
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
                try: ws = sh.worksheet("Página1")
                except: return pd.DataFrame()
            else: return pd.DataFrame()
        return pd.DataFrame(ws.get_all_records())
    except: return pd.DataFrame()

# ==================================================
# 3. LEITURA INTELIGENTE (CORREÇÃO AQUI)
# ==================================================
def carregar_opcoes():
    df = _ler_aba_como_df("Dados")
    opcoes = {'sms': NRS_PADRAO.copy()} # Começa com NRs padrão

    if not df.empty and 'Categoria' in df.columns and 'Item' in df.columns:
        # Normaliza para minúsculo
        df['Categoria'] = df['Categoria'].astype(str).str.lower().str.strip()
        
        # AGORA ELE CRIA LISTAS SEPARADAS PARA CADA CATEGORIA QUE ACHAR
        # Ex: vai criar opcoes['tecnico_dutos'], opcoes['tecnico_hidraulica'] automaticamente
        categorias_encontradas = df['Categoria'].unique()
        
        for cat in categorias_encontradas:
            itens = sorted(df[df['Categoria'] == cat]['Item'].unique().tolist())
            
            # Se for SMS, junta com o padrão
            if cat == 'sms':
                opcoes['sms'] = sorted(list(set(opcoes['sms'] + itens)))
            else:
                opcoes[cat] = itens
                
    return opcoes

def listar_fornecedores():
    df = _ler_aba_como_df("Dados")
    if df.empty or 'Fornecedor' not in df.columns: return []
    return df[['Fornecedor', 'CNPJ']].dropna(subset=['Fornecedor']).drop_duplicates().to_dict('records')

# ==================================================
# 4. ESCRITA
# ==================================================
def aprender_novo_item(categoria, novo_item):
    sh = _conectar_gsheets()
    if not sh: return False
    try:
        try: ws = sh.worksheet("Dados")
        except: ws = sh.add_worksheet("Dados", 100, 10)
        # Salva a categoria exata (ex: 'tecnico_hidraulica')
        ws.append_row([categoria.lower(), novo_item, "", ""])
        return True
    except: return False

def cadastrar_fornecedor_db(nome, cnpj):
    sh = _conectar_gsheets()
    if not sh: return False
    try:
        try: ws = sh.worksheet("Dados")
        except: ws = sh.add_worksheet("Dados", 100, 10)
        ws.append_row(["", "", nome, cnpj])
        return True
    except: return False

def registrar_projeto(dados):
    sh = _conectar_gsheets()
    if not sh: return False
    try:
        try: ws = sh.worksheet("Projetos")
        except: 
            ws = sh.add_worksheet("Projetos", 100, 20)
            ws.append_row(['_id', 'status', 'disciplina', 'cliente', 'obra', 'fornecedor', 'valor_total'])
        
        headers = ws.row_values(1)
        if not headers: ws.append_row(['_id', 'status', 'disciplina', 'cliente', 'obra', 'fornecedor', 'valor_total'])

        if '_id' not in dados: 
            from datetime import datetime
            dados['_id'] = datetime.now().strftime("%Y%m%d%H%M%S")

        row_data = []
        for h in headers: row_data.append(str(dados.get(h, "")))
        ws.append_row(row_data)
        return True
    except: return False
