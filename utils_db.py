import streamlit as st
import pandas as pd
import gspread

# ==================================================
# 1. CONEXÃO BLINDADA COM GOOGLE SHEETS
# ==================================================
def _conectar_gsheets():
    """Conecta ao Google Sheets com correção automática de chave."""
    try:
        # Verifica se os secrets existem
        if "gcp_service_account" not in st.secrets:
            st.error("🚨 Secrets 'gcp_service_account' não encontrados!")
            return None

        # Carrega as credenciais como dicionário
        creds_dict = dict(st.secrets["gcp_service_account"])

        # --- CORREÇÃO HÍBRIDA DA CHAVE ---
        # Isso garante que funcione se você colou com '\n' (texto) ou com 'Enter' (aspas triplas)
        if "private_key" in creds_dict:
            chave = creds_dict["private_key"]
            # Se a chave NÃO tiver quebras de linha reais, nós aplicamos a correção
            if "\n" not in chave:
                creds_dict["private_key"] = chave.replace("\\n", "\n")
            # Se já tiver quebras reais (usou aspas triplas), mantém como está

        # Conecta usando gspread
        gc = gspread.service_account_from_dict(creds_dict)
        
        # Abre a planilha pelo nome exato
        # IMPORTANTE: A planilha deve estar compartilhada com o 'client_email' dos secrets
        sh = gc.open("DB_SIARCON") 
        return sh
        
    except Exception as e:
        err_msg = str(e)
        if "Invalid JWT" in err_msg:
             st.error("🚨 Erro na Chave Privada (JWT). A chave nos Secrets está incorreta ou revogada. Gere uma nova chave JSON no Google Cloud e atualize os Secrets.")
        elif "SpreadsheetNotFound" in err_msg:
             st.error("🚨 Planilha 'DB_SIARCON' não encontrada! Verifique se você compartilhou ela com o email da conta de serviço.")
        else:
            st.error(f"Erro de Conexão: {e}")
        return None

def _ler_aba_como_df(nome_aba):
    """Lê uma aba específica e retorna como DataFrame Pandas."""
    sh = _conectar_gsheets()
    if not sh: return pd.DataFrame()

    try:
        worksheet = sh.worksheet(nome_aba)
        dados = worksheet.get_all_records()
        df = pd.DataFrame(dados)
        return df
    except gspread.WorksheetNotFound:
        # Se a aba não existir, retorna vazio
        return pd.DataFrame()
    except Exception as e:
        return pd.DataFrame()

# ==================================================
# 2. FUNÇÕES DO DASHBOARD (KANBAN)
# ==================================================
def listar_todos_projetos():
    """Retorna todos os projetos para o Dashboard."""
    df = _ler_aba_como_df("Projetos")
    
    if df.empty:
        return pd.DataFrame()

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
    """Atualiza o status na nuvem."""
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
    except Exception as e:
        st.error(f"Erro ao atualizar status: {e}")
    return False

# ==================================================
# 3. FUNÇÕES DOS GERADORES (DUTOS, ETC.)
# ==================================================
def carregar_opcoes():
    """Carrega Técnico, Qualidade e SMS da aba 'Dados'."""
    df = _ler_aba_como_df("Dados")
    opcoes = {'tecnico': [], 'qualidade': [], 'sms': []}
    
    if df.empty: return opcoes

    if 'Categoria' in df.columns and 'Item' in df.columns:
        # Normaliza categoria para minúsculo
        df['Categoria'] = df['Categoria'].astype(str).str.lower().str.strip()
        
        opcoes['tecnico'] = sorted(df[df['Categoria'] == 'tecnico']['Item'].unique().tolist())
        opcoes['qualidade'] = sorted(df[df['Categoria'].str.contains('qualidade')]['Item'].unique().tolist())
        opcoes['sms'] = sorted(df[df['Categoria'] == 'sms']['Item'].unique().tolist())
        
    return opcoes

def listar_fornecedores():
    """Lista fornecedores únicos."""
    df = _ler_aba_como_df("Dados")
    if df.empty or 'Fornecedor' not in df.columns: return []

    return df[['Fornecedor', 'CNPJ']].dropna(subset=['Fornecedor']).drop_duplicates().to_dict('records')

def aprender_novo_item(categoria, novo_item):
    """Adiciona novo item na aba 'Dados'."""
    sh = _conectar_gsheets()
    if not sh: return False
    
    try:
        ws = sh.worksheet("Dados")
        ws.append_row([categoria.lower(), novo_item, "", ""])
        return True
    except Exception as e:
        st.error(f"Erro ao salvar item: {e}")
        return False

def cadastrar_fornecedor_db(nome, cnpj):
    """Adiciona novo fornecedor na aba 'Dados'."""
    sh = _conectar_gsheets()
    if not sh: return False
    
    try:
        ws = sh.worksheet("Dados")
        records = ws.get_all_records()
        df = pd.DataFrame(records)
        
        if not df.empty and 'Fornecedor' in df.columns:
            if nome in df['Fornecedor'].values:
                return "Existe"
        
        ws.append_row(["", "", nome, cnpj])
        return True
    except Exception as e:
        st.error(f"Erro ao salvar fornecedor: {e}")
        return False

def registrar_projeto(dados, id_linha=None):
    """Salva o projeto na aba 'Projetos'."""
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
        st.error(f"Erro ao salvar projeto: {e}")
        return False
