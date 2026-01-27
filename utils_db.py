import streamlit as st
import pandas as pd
import gspread

# ==================================================
# 1. CONEXÃO BLINDADA COM GOOGLE SHEETS
# ==================================================
def _conectar_gsheets():
    """Conecta ao Google Sheets com tratamento de erros de chave."""
    try:
        if "gcp_service_account" not in st.secrets:
            st.error("🚨 Secrets não encontrados!")
            return None

        creds_dict = dict(st.secrets["gcp_service_account"])

        # Correção híbrida da chave (funciona com ou sem aspas triplas)
        if "private_key" in creds_dict:
            chave = creds_dict["private_key"]
            if "\n" not in chave:
                creds_dict["private_key"] = chave.replace("\\n", "\n")

        gc = gspread.service_account_from_dict(creds_dict)
        
        # Abre a planilha
        sh = gc.open("DB_SIARCON") 
        return sh
        
    except Exception as e:
        # Erros amigáveis
        msg = str(e)
        if "Invalid JWT" in msg:
             st.error("🚨 Erro na Chave Privada. Verifique os Secrets.")
        elif "SpreadsheetNotFound" in msg:
             st.error("🚨 Planilha 'DB_SIARCON' não encontrada. Verifique o compartilhamento.")
        else:
            st.error(f"Erro de Conexão: {e}")
        return None

def _get_worksheet_segura(sh, nome_aba):
    """Tenta achar a aba. Se não achar 'Dados', tenta 'Página1' ou 'Sheet1'."""
    try:
        return sh.worksheet(nome_aba)
    except gspread.WorksheetNotFound:
        # Fallbacks inteligentes apenas para a aba de Dados
        if nome_aba == "Dados":
            try: return sh.worksheet("Página1")
            except: pass
            try: return sh.worksheet("Sheet1")
            except: pass
            # Última tentativa: pega a primeira aba que existir
            try: return sh.get_worksheet(0)
            except: pass
        return None

def _ler_aba_como_df(nome_aba):
    """Lê uma aba e retorna DataFrame (nunca falha, retorna vazio se erro)."""
    sh = _conectar_gsheets()
    if not sh: return pd.DataFrame()

    try:
        ws = _get_worksheet_segura(sh, nome_aba)
        if not ws: return pd.DataFrame()
        
        dados = ws.get_all_records()
        return pd.DataFrame(dados)
    except Exception as e:
        print(f"Erro ao ler aba {nome_aba}: {e}")
        return pd.DataFrame()

# ==================================================
# 2. FUNÇÕES DO DASHBOARD (KANBAN)
# ==================================================
def listar_todos_projetos():
    """Retorna DataFrame dos projetos (resolve erro do Dashboard)."""
    df = _ler_aba_como_df("Projetos")
    
    # Se estiver vazio, retorna DataFrame com colunas vazias para não quebrar o layout
    if df.empty:
        colunas_padrao = ['_id', 'status', 'disciplina', 'cliente', 'obra', 'fornecedor', 'valor_total']
        return pd.DataFrame(columns=colunas_padrao)

    # Garante colunas essenciais
    cols_obrigatorias = ['_id', 'status', 'disciplina', 'cliente', 'obra', 'fornecedor', 'valor_total']
    for col in cols_obrigatorias:
        if col not in df.columns:
            df[col] = ""
            
    # Converte ID para string
    if '_id' in df.columns:
        df['_id'] = df['_id'].astype(str)
        
    return df

def atualizar_status_projeto(id_projeto, novo_status):
    sh = _conectar_gsheets()
    if not sh: return False

    try:
        # Para salvar, precisamos da aba exata "Projetos"
        try:
            ws = sh.worksheet("Projetos")
        except:
            return False # Se não existir a aba Projetos, não dá pra atualizar

        cell = ws.find(str(id_projeto))
        if cell:
            headers = ws.row_values(1)
            if 'status' in headers:
                col_index = headers.index('status') + 1
                ws.update_cell(cell.row, col_index, novo_status)
                return True
    except:
        pass
    return False

# ==================================================
# 3. FUNÇÕES DOS GERADORES
# ==================================================
def carregar_opcoes():
    """Carrega as listas para os Selectbox."""
    df = _ler_aba_como_df("Dados")
    opcoes = {'tecnico': [], 'qualidade': [], 'sms': []}
    
    if df.empty: return opcoes

    if 'Categoria' in df.columns and 'Item' in df.columns:
        df['Categoria'] = df['Categoria'].astype(str).str.lower().str.strip()
        
        opcoes['tecnico'] = sorted(df[df['Categoria'] == 'tecnico']['Item'].unique().tolist())
        opcoes['qualidade'] = sorted(df[df['Categoria'].str.contains('qualidade')]['Item'].unique().tolist())
        opcoes['sms'] = sorted(df[df['Categoria'] == 'sms']['Item'].unique().tolist())
        
    return opcoes

def listar_fornecedores():
    df = _ler_aba_como_df("Dados")
    if df.empty or 'Fornecedor' not in df.columns: return []
    return df[['Fornecedor', 'CNPJ']].dropna(subset=['Fornecedor']).drop_duplicates().to_dict('records')

def aprender_novo_item(categoria, novo_item):
    sh = _conectar_gsheets()
    if not sh: return False
    try:
        ws = _get_worksheet_segura(sh, "Dados")
        if ws:
            ws.append_row([categoria.lower(), novo_item, "", ""])
            return True
    except: pass
    return False

def cadastrar_fornecedor_db(nome, cnpj):
    sh = _conectar_gsheets()
    if not sh: return False
    try:
        ws = _get_worksheet_segura(sh, "Dados")
        if ws:
            # Check duplicidade simples
            try:
                col_forn = ws.col_values(3) # Assume coluna C = Fornecedor
                if nome in col_forn: return "Existe"
            except: pass
            
            ws.append_row(["", "", nome, cnpj])
            return True
    except: pass
    return False

def registrar_projeto(dados, id_linha=None):
    sh = _conectar_gsheets()
    if not sh: return False

    try:
        try:
            ws = sh.worksheet("Projetos")
        except:
            ws = sh.add_worksheet(title="Projetos", rows="100", cols="20")
            ws.append_row(['_id', 'status', 'disciplina', 'cliente', 'obra', 'fornecedor', 'valor_total', 'revisao', 'data_inicio'])

        headers = ws.row_values(1)
        if not headers:
            headers = ['_id', 'status', 'disciplina', 'cliente', 'obra', 'fornecedor', 'valor_total']
            ws.append_row(headers)

        if '_id' not in dados or not dados['_id']:
            from datetime import datetime
            dados['_id'] = datetime.now().strftime("%Y%m%d%H%M%S")

        row_data = []
        for h in headers:
            val = dados.get(h, "")
            row_data.append(str(val))
            
        ws.append_row(row_data)
        return True
    except Exception as e:
        st.error(f"Erro ao salvar: {e}")
        return False
