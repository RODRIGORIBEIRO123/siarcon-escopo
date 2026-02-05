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
            return None
        
        creds_dict = dict(st.secrets["gcp_service_account"])
        if "private_key" in creds_dict:
            chave = creds_dict["private_key"]
            if "\n" not in chave: creds_dict["private_key"] = chave.replace("\\n", "\n")
        
        gc = gspread.service_account_from_dict(creds_dict)
        return gc.open("DB_SIARCON") 
    except Exception as e:
        print(f"Erro Conexão: {e}")
        return None

def _ler_aba_como_df(nome_aba):
    sh = _conectar_gsheets()
    if not sh: return pd.DataFrame()
    try:
        try: ws = sh.worksheet(nome_aba)
        except: 
            try: ws = sh.add_worksheet(nome_aba, 100, 20)
            except: return pd.DataFrame()
        
        data = ws.get_all_records()
        return pd.DataFrame(data)
    except: return pd.DataFrame()

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
# 3. FUNÇÕES DE PROJETO (COM AUTO-CORREÇÃO DE COLUNAS)
# ==================================================
def listar_todos_projetos():
    df = _ler_aba_como_df("Projetos")
    # Garante colunas mínimas para o dashboard não quebrar
    cols_minimas = ['_id', 'status', 'disciplina', 'cliente', 'obra', 'prazo']
    if df.empty: return pd.DataFrame(columns=cols_minimas)
    
    for c in cols_minimas: 
        if c not in df.columns: df[c] = ""
        
    if '_id' in df.columns: df['_id'] = df['_id'].astype(str)
    return df

def buscar_projeto_por_id(id_projeto):
    df = listar_todos_projetos()
    if df.empty: return None
    projeto = df[df['_id'] == str(id_projeto)]
    if not projeto.empty:
        # Preenche vazios com string vazia para não travar os campos de texto
        return projeto.fillna("").iloc[0].to_dict()
    return None

def salvar_projeto(dados):
    return registrar_projeto(dados)

def registrar_projeto(dados):
    sh = _conectar_gsheets()
    if not sh: return False
    try:
        # 1. Tenta pegar a aba ou criar
        try: ws = sh.worksheet("Projetos")
        except: 
            ws = sh.add_worksheet("Projetos", 100, 20)
        
        # 2. Pega os headers atuais (cabeçalho)
        headers_atuais = ws.row_values(1)
        if not headers_atuais:
            headers_atuais = ['_id', 'status', 'disciplina', 'cliente', 'obra']
            ws.append_row(headers_atuais)

        # --- A MÁGICA ACONTECE AQUI ---
        # 3. Verifica se tem alguma chave nova (ex: itens_tecnicos) que não tem coluna ainda
        novas_colunas = []
        for chave in dados.keys():
            if chave not in headers_atuais:
                novas_colunas.append(chave)
        
        # Se tiver coluna nova faltando, cria ela na planilha
        if novas_colunas:
            # Adiciona colunas extras
            ws.add_cols(len(novas_colunas))
            # Atualiza a lista local de headers e escreve na linha 1
            headers_atuais.extend(novas_colunas)
            ws.update(range_name="A1", values=[headers_atuais])

        # 4. Gera ID se não tiver
        if '_id' not in dados or not dados['_id']: 
            dados['_id'] = datetime.now().strftime("%Y%m%d%H%M%S")

        # 5. Prepara a linha de dados na ordem correta dos headers
        row_data = []
        for h in headers_atuais:
            valor = str(dados.get(h, "")) # Converte tudo para string para evitar erro
            row_data.append(valor)

        # 6. Busca se já existe para atualizar
        cell = None
        try: cell = ws.find(str(dados['_id']), in_column=1)
        except: pass

        if cell: 
            # Atualiza linha existente
            ws.update(range_name=f"A{cell.row}", values=[row_data])
        else: 
            # Cria nova linha
            ws.append_row(row_data)
            
        return True
    except Exception as e:
        print(f"ERRO CRÍTICO AO SALVAR: {e}")
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
    except: pass
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
    
    # Fallback para aprender da aba Dados se não tiver aba fornecedores
    df = _ler_aba_como_df("Dados")
    if not df.empty and 'Fornecedor' in df.columns:
        return df[['Fornecedor', 'CNPJ']].dropna(subset=['Fornecedor']).drop_duplicates().to_dict('records')
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
    except: return False
