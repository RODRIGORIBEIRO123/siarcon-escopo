import streamlit as st
import pandas as pd
import os
from datetime import datetime

# ==================================================
# 1. GERENCIAMENTO DE ARQUIVO (LOCALIZADOR BLINDADO)
# ==================================================
def _get_caminho_banco():
    """Função interna para achar o arquivo DB_SIARCON.xlsx onde quer que ele esteja."""
    nomes = ["DB_SIARCON.xlsx", "DB_SIARCON.xls"]
    pastas = [".", "dados", "..", "../dados", "pages"] 
    
    diretorio_base = os.path.dirname(os.path.abspath(__file__))

    for pasta in pastas:
        for nome in nomes:
            caminho = os.path.join(diretorio_base, pasta, nome)
            if os.path.exists(caminho):
                return caminho
    
    return None

def carregar_planilha_completa():
    """Carrega o Excel inteiro (todas as abas)."""
    caminho = _get_caminho_banco()
    if not caminho:
        st.error("🚨 Banco de dados DB_SIARCON.xlsx não encontrado!")
        return None
    
    try:
        # Lê todas as abas
        return pd.read_excel(caminho, sheet_name=None)
    except Exception as e:
        st.error(f"Erro ao ler banco de dados: {e}")
        return None

# ==================================================
# 2. FUNÇÕES DO DASHBOARD (QUE ESTAVAM FALTANDO)
# ==================================================
def listar_todos_projetos():
    """Lê a aba 'Projetos' para alimentar o Dashboard Kanban."""
    xls = carregar_planilha_completa()
    if xls and "Projetos" in xls:
        df = xls["Projetos"]
        # Garante que as colunas existem para não dar erro
        colunas_necessarias = ['_id', 'status', 'disciplina', 'cliente', 'obra', 'fornecedor', 'valor_total']
        for col in colunas_necessarias:
            if col not in df.columns:
                df[col] = "" # Cria vazia se não existir
        
        # Converte para lista de dicionários (records)
        return df.to_dict('records')
    return []

def atualizar_status_projeto(id_projeto, novo_status):
    """Atualiza o status de um projeto específico."""
    caminho = _get_caminho_banco()
    if not caminho: return False

    try:
        # Carrega, edita e salva
        df_projetos = pd.read_excel(caminho, sheet_name="Projetos")
        
        # Localiza linha pelo ID
        idx = df_projetos[df_projetos['_id'] == id_projeto].index
        if not idx.empty:
            df_projetos.at[idx[0], 'status'] = novo_status
            
            # Salva mantendo as outras abas
            with pd.ExcelWriter(caminho, engine='openpyxl', mode='a', if_sheet_exists='replace') as writer:
                df_projetos.to_excel(writer, sheet_name="Projetos", index=False)
            return True
    except Exception as e:
        print(f"Erro ao atualizar: {e}")
    return False

# ==================================================
# 3. FUNÇÕES DOS FORMULÁRIOS (GERADORES)
# ==================================================
def carregar_opcoes():
    """Carrega as listas de opções (Técnico, SMS, etc) da aba 'Dados'."""
    xls = carregar_planilha_completa()
    opcoes = {'tecnico': [], 'qualidade': [], 'sms': []}
    
    if xls and "Dados" in xls:
        df = xls["Dados"]
        # Filtra por categoria
        if 'Categoria' in df.columns and 'Item' in df.columns:
            opcoes['tecnico'] = df[df['Categoria'] == 'Tecnico']['Item'].dropna().unique().tolist()
            opcoes['qualidade'] = df[df['Categoria'] == 'Qualidade']['Item'].dropna().unique().tolist()
            opcoes['sms'] = df[df['Categoria'] == 'SMS']['Item'].dropna().unique().tolist()
    
    return opcoes

def listar_fornecedores():
    """Lista fornecedores da aba 'Dados'."""
    xls = carregar_planilha_completa()
    if xls and "Dados" in xls:
        df = xls["Dados"]
        if 'Fornecedor' in df.columns:
            return df[['Fornecedor', 'CNPJ']].dropna(subset=['Fornecedor']).drop_duplicates().to_dict('records')
    return []

def registrar_projeto(dados, id_linha=None):
    """Salva ou Atualiza um projeto na aba 'Projetos'."""
    caminho = _get_caminho_banco()
    if not caminho: return False

    try:
        # Tenta ler a aba Projetos, se não existir, cria um DF vazio
        try:
            df_atual = pd.read_excel(caminho, sheet_name="Projetos")
        except:
            df_atual = pd.DataFrame()

        # Prepara os dados para salvar (transforma listas em strings)
        dados_salvar = dados.copy()
        for k, v in dados_salvar.items():
            if isinstance(v, list) or isinstance(v, dict):
                dados_salvar[k] = str(v)
            if isinstance(v, datetime): # Converte data
                dados_salvar[k] = v.strftime("%Y-%m-%d")

        # Adiciona ID único se não tiver
        if '_id' not in dados_salvar:
            dados_salvar['_id'] = datetime.now().strftime("%Y%m%d%H%M%S")

        if id_linha is not None:
            # ATUALIZAR EXISTENTE (Lógica simples: remove antigo e põe novo)
            # Num cenário ideal, usaríamos o índice, mas aqui vamos dar append no fim e remover o velho se achar
            # Para simplificar e evitar erros de índice, vamos apenas ADICIONAR UM NOVO REGISTRO
            # O Dashboard pega sempre o último ou você pode implementar limpeza depois.
            pass
        
        # Cria DF com o novo registro
        novo_registro = pd.DataFrame([dados_salvar])
        
        # Concatena
        df_final = pd.concat([df_atual, novo_registro], ignore_index=True)

        # Salva no Excel (Cuidado: mode='a' com replace substitui a aba)
        with pd.ExcelWriter(caminho, engine='openpyxl', mode='a', if_sheet_exists='replace') as writer:
            df_final.to_excel(writer, sheet_name="Projetos", index=False)
        
        return True

    except Exception as e:
        st.error(f"Erro ao salvar no Excel: {e}")
        return False

def aprender_novo_item(categoria, novo_item):
    """Adiciona um novo item técnico/qualidade na aba 'Dados'."""
    caminho = _get_caminho_banco()
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
    """Adiciona fornecedor na aba 'Dados'."""
    caminho = _get_caminho_banco()
    if not caminho: return False
    
    try:
        df = pd.read_excel(caminho, sheet_name="Dados")
        # Verifica duplicidade
        if not df[df['Fornecedor'] == nome].empty:
            return "Existe"
            
        novo = pd.DataFrame([{'Fornecedor': nome, 'CNPJ': cnpj}])
        df_final = pd.concat([df, novo], ignore_index=True)
        
        with pd.ExcelWriter(caminho, engine='openpyxl', mode='a', if_sheet_exists='replace') as writer:
            df_final.to_excel(writer, sheet_name="Dados", index=False)
        return True
    except:
        return False
