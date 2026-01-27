import streamlit as st
import pandas as pd
import os
from datetime import datetime

# ==================================================
# 1. NÚCLEO DO BANCO DE DADOS (CRIA SE NÃO EXISTIR)
# ==================================================
def _get_caminho_banco():
    """Retorna o caminho do arquivo. Se não existir, define onde criar."""
    nome_arquivo = "DB_SIARCON.xlsx"
    # Tenta achar na raiz ou em pastas comuns
    pastas_busca = [".", "dados", "..", "../dados"]
    
    diretorio_base = os.path.dirname(os.path.abspath(__file__))

    # 1. Tenta encontrar arquivo existente
    for pasta in pastas_busca:
        caminho_teste = os.path.join(diretorio_base, pasta, nome_arquivo)
        if os.path.exists(caminho_teste):
            return caminho_teste
            
    # 2. Se não achou, define o caminho padrão para criar (na raiz do app)
    # Tenta salvar na raiz onde está o utils_db.py
    return os.path.join(diretorio_base, nome_arquivo)

def _inicializar_banco_se_necessario():
    """Cria o Excel com as abas certas se ele não existir."""
    caminho = _get_caminho_banco()
    
    if not os.path.exists(caminho):
        # Cria DataFrames vazios com as colunas necessárias
        df_dados = pd.DataFrame(columns=['Categoria', 'Item', 'Fornecedor', 'CNPJ'])
        df_projetos = pd.DataFrame(columns=[
            '_id', 'status', 'disciplina', 'cliente', 'obra', 'fornecedor', 
            'valor_total', 'data_inicio', 'revisao'
        ])
        
        # Salva o arquivo novo
        try:
            with pd.ExcelWriter(caminho, engine='xlsxwriter') as writer:
                df_dados.to_excel(writer, sheet_name='Dados', index=False)
                df_projetos.to_excel(writer, sheet_name='Projetos', index=False)
            print(f"✅ Banco de dados criado em: {caminho}")
        except Exception as e:
            st.error(f"Erro ao criar banco de dados: {e}")
            return None
            
    return caminho

# ==================================================
# 2. FUNÇÕES PARA O DASHBOARD (KANBAN)
# ==================================================
def listar_todos_projetos():
    """Lê a aba 'Projetos' e retorna lista de dicionários."""
    caminho = _inicializar_banco_se_necessario()
    if not caminho: return []

    try:
        df = pd.read_excel(caminho, sheet_name="Projetos")
        # Garante que colunas essenciais existem
        cols_check = ['_id', 'status', 'disciplina', 'cliente', 'obra', 'fornecedor']
        for col in cols_check:
            if col not in df.columns: df[col] = ""
            
        return df.to_dict('records')
    except Exception as e:
        st.error(f"Erro ao ler Projetos: {e}")
        return []

def atualizar_status_projeto(id_projeto, novo_status):
    """Atualiza o status no Kanban."""
    caminho = _inicializar_banco_se_necessario()
    if not caminho: return False

    try:
        df = pd.read_excel(caminho, sheet_name="Projetos")
        mask = df['_id'].astype(str) == str(id_projeto)
        
        if mask.any():
            df.loc[mask, 'status'] = novo_status
            with pd.ExcelWriter(caminho, engine='openpyxl', mode='a', if_sheet_exists='replace') as writer:
                df.to_excel(writer, sheet_name="Projetos", index=False)
            return True
    except:
        pass
    return False

# ==================================================
# 3. FUNÇÕES PARA OS FORMULÁRIOS (ESC. DUTOS, HIDRÁULICA...)
# ==================================================
def carregar_opcoes():
    """Carrega itens técnicos/qualidade/SMS."""
    caminho = _inicializar_banco_se_necessario()
    opcoes = {'tecnico': [], 'qualidade': [], 'sms': []}
    
    if not caminho: return opcoes

    try:
        df = pd.read_excel(caminho, sheet_name="Dados")
        if 'Categoria' in df.columns and 'Item' in df.columns:
            opcoes['tecnico'] = df[df['Categoria'] == 'Tecnico']['Item'].dropna().unique().tolist()
            opcoes['qualidade'] = df[df['Categoria'] == 'Qualidade']['Item'].dropna().unique().tolist()
            opcoes['sms'] = df[df['Categoria'] == 'SMS']['Item'].dropna().unique().tolist()
    except:
        pass # Se der erro, retorna listas vazias mas não trava
        
    return opcoes

def listar_fornecedores():
    """Lista fornecedores cadastrados."""
    caminho = _inicializar_banco_se_necessario()
    if not caminho: return []

    try:
        df = pd.read_excel(caminho, sheet_name="Dados")
        if 'Fornecedor' in df.columns:
            return df[['Fornecedor', 'CNPJ']].dropna(subset=['Fornecedor']).drop_duplicates().to_dict('records')
    except:
        pass
    return []

def aprender_novo_item(categoria, novo_item):
    """Salva novo item técnico no banco."""
    caminho = _inicializar_banco_se_necessario()
    if not caminho: return False
    
    try:
        df = pd.read_excel(caminho, sheet_name="Dados")
        novo = pd.DataFrame([{'Categoria': categoria, 'Item': novo_item}])
        df_final = pd.concat([df, novo], ignore_index=True)
        
        with pd.ExcelWriter(caminho, engine='openpyxl', mode='a', if_sheet_exists='replace') as writer:
            df_final.to_excel(writer, sheet_name="Dados", index=False)
        return True
    except:
        return False

def cadastrar_fornecedor_db(nome, cnpj):
    """Salva novo fornecedor."""
    caminho = _inicializar_banco_se_necessario()
    if not caminho: return False
    
    try:
        df = pd.read_excel(caminho, sheet_name="Dados")
        # Verifica duplicidade
        if 'Fornecedor' in df.columns and not df[df['Fornecedor'] == nome].empty:
            return "Existe"
            
        novo = pd.DataFrame([{'Fornecedor': nome, 'CNPJ': cnpj}])
        df_final = pd.concat([df, novo], ignore_index=True)
        
        with pd.ExcelWriter(caminho, engine='openpyxl', mode='a', if_sheet_exists='replace') as writer:
            df_final.to_excel(writer, sheet_name="Dados", index=False)
        return True
    except:
        return False

def registrar_projeto(dados, id_linha=None):
    """Salva o escopo na aba Projetos."""
    caminho = _inicializar_banco_se_necessario()
    if not caminho: return False

    try:
        try:
            df_atual = pd.read_excel(caminho, sheet_name="Projetos")
        except:
            df_atual = pd.DataFrame()

        # Limpa dados para salvar (converte listas/datas para string)
        dados_salvar = dados.copy()
        for k, v in dados_salvar.items():
            if isinstance(v, (list, dict)): dados_salvar[k] = str(v)
            if isinstance(v, datetime): dados_salvar[k] = v.strftime("%Y-%m-%d")

        # Gera ID se não tiver
        if '_id' not in dados_salvar or not dados_salvar['_id']:
            dados_salvar['_id'] = datetime.now().strftime("%Y%m%d%H%M%S")

        # Adiciona nova linha (append)
        novo_registro = pd.DataFrame([dados_salvar])
        df_final = pd.concat([df_atual, novo_registro], ignore_index=True)

        with pd.ExcelWriter(caminho, engine='openpyxl', mode='a', if_sheet_exists='replace') as writer:
            df_final.to_excel(writer, sheet_name="Projetos", index=False)
        
        return True
    except Exception as e:
        st.error(f"Erro ao salvar: {e}")
        return False
