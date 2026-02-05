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
        if "gcp_service_account" not in st.secrets: 
            st.error("Secret 'gcp_service_account' não encontrada!")
            return None
        
        creds_dict = dict(st.secrets["gcp_service_account"])
        if "private_key" in creds_dict:
            chave = creds_dict["private_key"]
            if "\n" not in chave: creds_dict["private_key"] = chave.replace("\\n", "\n")
        
        gc = gspread.service_account_from_dict(creds_dict)
        return gc.open("DB_SIARCON") 
    except Exception as e:
        st.error(f"Erro de Conexão com Google Sheets: {e}")
        return None

def _ler_aba_como_df(nome_aba):
    sh = _conectar_gsheets()
    if not sh: return pd.DataFrame()
    try:
        try: ws = sh.worksheet(nome_aba)
        except: 
            # Se não existe, cria
            try: ws = sh.add_worksheet(nome_aba, 100, 20)
            except: return pd.DataFrame()
        
        data = ws.get_all_records()
        return pd.DataFrame(data)
    except Exception as e:
        print(f"Erro ao ler aba {nome_aba}: {e}")
        return pd.DataFrame()

# ==================================================
# 2. AUTENTICAÇÃO
# ==================================================
def verificar_login_db(usuario, senha):
    df = _ler_aba_como_df("Usuarios")
    if df.empty:
        if usuario == "admin" and senha == "1234": return True
        return False
    
    df['Usuario'] = df['Usuario'].astype(str)
    df['Senha'] = df['Senha'].astype(str)
    
    user_encontrado = df[(df['Usuario'] == str(usuario)) & (df['Senha'] == str(senha))]
    return not user_encontrado.empty

# ==================================================
# 3. FUNÇÕES DE PROJETO (SALVAR E LER)
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
        # Preenche vazios com None ou string vazia para não quebrar o front
        return projeto.fillna("").iloc[0].to_dict()
    return None

def salvar_projeto(dados):
    return registrar_projeto(dados)

def registrar_projeto(dados):
    sh = _conectar_gsheets()
    if not sh: return False
    try:
        # Tenta pegar a aba, se não existir, cria
        try: ws = sh.worksheet("Projetos")
        except: 
            ws = sh.add_worksheet("Projetos", 100, 20)
            ws.append_row(['_id', 'status', 'disciplina', 'cliente', 'obra', 'prazo', 'fornecedor', 'valor_total', 'criado_por'])
        
        # Garante headers se a aba for nova/vazia
        if not ws.row_values(1):
             ws.append_row(['_id', 'status', 'disciplina', 'cliente', 'obra', 'prazo', 'fornecedor', 'valor_total', 'criado_por'])

        # Gera ID se novo
        if '_id' not in dados or not dados['_id']: 
            dados['_id'] = datetime.now().strftime("%Y%m%d%H%M%S")

        # Pega os headers atuais da planilha para saber a ordem das colunas
        headers = ws.row_values(1)
        
        # Prepara a linha de dados na ordem exata das colunas
        row_data = []
        for h in headers:
            valor = str(dados.get(h, ""))
            row_data.append(valor)

        # Procura se o projeto já existe (pelo ID)
        cell = None
        try: cell = ws.find(str(dados['_id']), in_column=1) # Busca na coluna 1 (ID)
        except: pass

        if cell: 
            # ATUALIZA A LINHA EXISTENTE
            # range_name ex: "A2"
            col_letras = gspread.utils.rowcol_to_a1(cell.row, 1) # A{row}
            # Atualiza a linha inteira
            ws.update(range_name=f"A{cell.row}", values=[row_data])
        else: 
            # CRIA NOVA LINHA
            ws.append_row(row_data)
            
        return True
    except Exception as e:
        st.error(f"ERRO AO SALVAR NO GOOGLE SHEETS: {e}")
        return False

def excluir_projeto(id_projeto):
    sh = _conectar_gsheets()
    if not sh: return False
    try:
        ws = sh.worksheet("Projetos")
        cell = ws.find(str(id_projeto), in_column=1)
        if cell:
            ws.delete_rows(cell.row)
            return True
    except Exception as e:
        st.error(f"Erro ao excluir: {e}")
    return False

# ==================================================
# 4. AUXILIARES
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
    return []

def carregar_opcoes():
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
        
        if not ws.row_values(1): ws.append_row(["Categoria", "Item"])
        
        ws.append_row([categoria.lower(), novo_item])
        return True
    except Exception as e:
        st.error(f"Erro ao aprender item: {e}")
        return False
