import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
from datetime import datetime

# ==========================================
# 1. CONEXÃO
# ==========================================
def conectar_google_sheets():
    try:
        scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scope)
        client = gspread.authorize(creds)
        return client.open("DB_SIARCON")
    except Exception as e:
        st.error(f"Erro de conexão: {e}")
        return None

# ==========================================
# 2. CONFIGURAÇÕES
# ==========================================
def carregar_opcoes():
    try:
        sh = conectar_google_sheets()
        if not sh: return {}
        ws = sh.worksheet("Config")
        data = ws.get_all_records()
        df = pd.DataFrame(data)
        
        def get_list(cat): return df[df["Categoria"] == cat]["Item"].tolist()
        
        return {
            "tecnico": get_list("tecnico"),
            "qualidade": get_list("qualidade"),
            "tecnico_hidraulica": get_list("tecnico_hidraulica"),
            "qualidade_hidraulica": get_list("qualidade_hidraulica"),
            "tecnico_eletrica": get_list("tecnico_eletrica"),
            "qualidade_eletrica": get_list("qualidade_eletrica"),
            "tecnico_automacao": get_list("tecnico_automacao"),
            "qualidade_automacao": get_list("qualidade_automacao"),
            "tecnico_tab": get_list("tecnico_tab"),
            "tecnico_movimentacao": get_list("tecnico_movimentacao"),
            "qualidade_movimentacao": get_list("qualidade_movimentacao"),
            "tecnico_cobre": get_list("tecnico_cobre"),
            "qualidade_cobre": get_list("qualidade_cobre"),
            "sms": get_list("sms")
        }
    except: return {}

def aprender_novo_item(categoria, novo_item):
    try:
        sh = conectar_google_sheets()
        if not sh: return False
        ws = sh.worksheet("Config")
        ws.append_row([categoria, novo_item])
        return True
    except: return False

# ==========================================
# 3. GESTÃO DE PROJETOS (CORRIGIDO)
# ==========================================
def listar_todos_projetos():
    try:
        sh = conectar_google_sheets()
        if not sh: return pd.DataFrame()
        ws = sh.worksheet("Projetos")
        
        # Pega tudo como lista de listas
        rows = ws.get_all_values()
        
        if len(rows) < 2: return pd.DataFrame()
        
        # Define colunas esperadas (9 colunas)
        colunas_padrao = ["Data", "Cliente", "Obra", "Fornecedor", "Responsavel", "Valor", "Status", "Resp_Obras", "Disciplina"]
        
        dados_tratados = []
        
        # Loop para limpar linhas vazias
        # 'rows[1:]' ignora o cabeçalho
        for i, row in enumerate(rows[1:]):
            
            # --- PROTEÇÃO CONTRA LINHAS VAZIAS ---
            # Se a linha tiver menos de 3 colunas, ignoramos
            if len(row) < 3:
                continue
            
            # Converte para string antes de verificar (evita AttributeError se vier número)
            cli_str = str(row[1]).strip()
            obra_str = str(row[2]).strip()
            
            # Se Cliente e Obra estiverem vazios, pula a linha
            if not cli_str and not obra_str:
                continue
            
            # Normaliza tamanho (enche com vazio se faltar colunas)
            linha_normalizada = row + [""] * (len(colunas_padrao) - len(row))
            linha_final = linha_normalizada[:len(colunas_padrao)]
            
            # Adiciona o ID real da linha (i + 2) para controle
            dados_com_id = linha_final + [i + 2] 
            dados_tratados.append(dados_com_id)
            
        # Cria DataFrame
        cols_df = colunas_padrao + ["_id_linha"]
        df = pd.DataFrame(dados_tratados, columns=cols_df)
        
        return df

    except Exception as e:
        st.error(f"Erro ao ler lista: {e}")
        return pd.DataFrame()

# ==========================================
# 4. CRIAR PACOTE
# ==========================================
def criar_pacote_obra(cliente, obra, lista_disciplinas):
    try:
        sh = conectar_google_sheets()
        if not sh: return False
        ws = sh.worksheet("Projetos")
        
        novas_linhas = []
        data_hoje = datetime.now().strftime("%d/%m/%Y %H:%M")
        
        for disciplina in lista_disciplinas:
            # Estrutura: [Data, Cli, Obra, Forn, RespEng, Valor, Status, RespObras, DISCIPLINA]
            linha = [
                data_hoje, 
                cliente, 
                obra, 
                "", "", "", 
                "Não Iniciado", 
                "", 
                disciplina
            ]
            novas_linhas.append(linha)
            
        ws.append_rows(novas_linhas)
        return True
    except Exception as e:
        st.error(f"Erro ao criar obra: {e}")
        return False

# ==========================================
# 5. SALVAR
# ==========================================
def registrar_projeto(dados, id_linha=None):
    try:
        sh = conectar_google_sheets()
        if not sh: return
        ws = sh.worksheet("Projetos")
        
        linha = [
            datetime.now().strftime("%d/%m/%Y %H:%M"),
            dados['cliente'], dados['obra'], dados['fornecedor'],
            dados['responsavel'], dados['valor_total'],
            dados.get('status', 'Em Elaboração (Engenharia)'),
            dados.get('resp_obras', ''),
            dados.get('disciplina', '')
        ]
        
        if id_linha:
            range_celulas = f"A{id_linha}:I{id_linha}"
            ws.update(range_name=range_celulas, values=[linha])
        else:
            ws.append_row(linha)
    except Exception as e:
        st.error(f"Erro ao salvar: {e}")

# ==========================================
# 6. EXCLUIR
# ==========================================
def excluir_projeto(id_linha):
    try:
        sh = conectar_google_sheets()
        if not sh: return False
        ws = sh.worksheet("Projetos")
        ws.delete_rows(id_linha)
        return True
    except: return False
