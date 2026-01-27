import streamlit as st
import pandas as pd
import gspread

# ==================================================
# 1. LISTA PADRÃO COMPLETA (FIXA NO CÓDIGO)
# ==================================================
NRS_PADRAO = [
    "NR-01 (Disposições Gerais)",
    "NR-03 (Embargo e Interdição)",
    "NR-04 (SESMT)",
    "NR-05 (CIPA)",
    "NR-06 (Equipamento de Proteção Individual - EPI)",
    "NR-07 (PCMSO)",
    "NR-08 (Edificações)",
    "NR-09 (Avaliação e Controle de Exposições Ocupacionais)",
    "NR-10 (Segurança em Instalações e Serviços em Eletricidade)",
    "NR-11 (Transporte, Movimentação, Armazenagem e Manuseio de Materiais)",
    "NR-12 (Segurança no Trabalho em Máquinas e Equipamentos)",
    "NR-13 (Caldeiras, Vasos de Pressão e Tubulações)",
    "NR-15 (Atividades e Operações Insalubres)",
    "NR-16 (Atividades e Operações Perigosas)",
    "NR-17 (Ergonomia)",
    "NR-18 (Condições e Meio Ambiente de Trabalho na Indústria da Construção)",
    "NR-23 (Proteção Contra Incêndios)",
    "NR-24 (Condições Sanitárias e de Conforto)",
    "NR-26 (Sinalização de Segurança)",
    "NR-33 (Segurança e Saúde nos Trabalhos em Espaços Confinados)",
    "NR-35 (Trabalho em Altura)"
]

# ==================================================
# 2. CONEXÃO COM GOOGLE SHEETS
# ==================================================
def _conectar_gsheets():
    try:
        if "gcp_service_account" not in st.secrets:
            st.error("🚨 Secrets não encontrados!")
            return None

        creds_dict = dict(st.secrets["gcp_service_account"])
        if "private_key" in creds_dict:
            chave = creds_dict["private_key"]
            if "\n" not in chave:
                creds_dict["private_key"] = chave.replace("\\n", "\n")

        gc = gspread.service_account_from_dict(creds_dict)
        return gc.open("DB_SIARCON") 
    except Exception:
        return None

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
# 3. FUNÇÕES DE LEITURA (GARANTINDO NRS)
# ==================================================
def carregar_opcoes():
    df = _ler_aba_como_df("Dados")
    opcoes = {'tecnico': [], 'qualidade': [], 'sms': []}
    
    # 1. Carrega NRs Padrão PRIMEIRO
    lista_nrs = NRS_PADRAO.copy()

    if not df.empty and 'Categoria' in df.columns and 'Item' in df.columns:
        df['Categoria'] = df['Categoria'].astype(str).str.lower().str.strip()
        
        tec_db = sorted(df[df['Categoria'] == 'tecnico']['Item'].unique().tolist())
        qual_db = sorted(df[df['Categoria'].str.contains('qualidade')]['Item'].unique().tolist())
        sms_db = sorted(df[df['Categoria'] == 'sms']['Item'].unique().tolist())
        
        opcoes['tecnico'] = tec_db
        opcoes['qualidade'] = qual_db
        
        # 2. Junta lista padrão com o banco e remove duplicadas
        lista_nrs.extend(sms_db)
    
    # Remove duplicatas e ordena
    opcoes['sms'] = sorted(list(set(lista_nrs)))
        
    return opcoes

def listar_fornecedores():
    df = _ler_aba_como_df("Dados")
    if df.empty or 'Fornecedor' not in df.columns: return []
    return df[['Fornecedor', 'CNPJ']].dropna(subset=['Fornecedor']).drop_duplicates().to_dict('records')

# ==================================================
# 4. FUNÇÕES DE ESCRITA
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
        try: ws = sh.worksheet("Dados")
        except: ws = sh.add_worksheet("Dados", 100, 10)
        try:
            col_forn = ws.col_values(3)
            if nome in col_forn: return "Existe"
        except: pass
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
        if not headers:
            headers = ['_id', 'status', 'disciplina', 'cliente', 'obra', 'fornecedor', 'valor_total']
            ws.append_row(headers)

        if '_id' not in dados or not dados['_id']:
            from datetime import datetime
            dados['_id'] = datetime.now().strftime("%Y%m%d%H%M%S")

        row_data = []
        for h in headers:
            row_data.append(str(dados.get(h, "")))
        ws.append_row(row_data)
        return True
    except: return False

def listar_todos_projetos():
    df = _ler_aba_como_df("Projetos")
    if df.empty: return pd.DataFrame(columns=['_id', 'status', 'disciplina', 'cliente', 'obra', 'fornecedor', 'valor_total'])
    cols = ['_id', 'status', 'disciplina', 'cliente', 'obra', 'fornecedor', 'valor_total']
    for c in cols: 
        if c not in df.columns: df[c] = ""
    if '_id' in df.columns: df['_id'] = df['_id'].astype(str)
    return df
