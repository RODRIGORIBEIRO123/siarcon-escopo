import streamlit as st
import pandas as pd
import os
from datetime import datetime

# ==================================================
# 1. NÚCLEO: ENCONTRAR OU CRIAR O ARQUIVO
# ==================================================
def _get_caminho_banco():
    """Retorna o caminho absoluto do DB_SIARCON.xlsx."""
    nome_arquivo = "DB_SIARCON.xlsx"
    diretorio_base = os.path.dirname(os.path.abspath(__file__))
    
    # Lista de locais para procurar
    locais = [
        os.path.join(diretorio_base, nome_arquivo),           # Raiz do app
        os.path.join(diretorio_base, "dados", nome_arquivo),  # Pasta dados
        os.path.join(diretorio_base, "..", nome_arquivo)      # Pasta pai
    ]

    # 1. Tenta achar arquivo existente
    for caminho in locais:
        if os.path.exists(caminho):
            return caminho
            
    # 2. Se não achar, define o caminho padrão na Raiz para criar
    return os.path.join(diretorio_base, nome_arquivo)

def _garantir_banco_existe():
    """Se o arquivo não existir, CRIA ele com as abas certas."""
    caminho = _get_caminho_banco()
    
    if not os.path.exists(caminho):
        print(f"⚠️ Banco de dados não encontrado. Criando novo em: {caminho}")
        try:
            # Cria DataFrames vazios com as colunas obrigatórias
            df_dados = pd.DataFrame(columns=['Categoria', 'Item', 'Fornecedor', 'CNPJ'])
            df_projetos = pd.DataFrame(columns=[
                '_id', 'status', 'disciplina', 'cliente', 'obra', 
                'fornecedor', 'valor_total', 'revisao', 'data_inicio'
            ])
            
            # Salva o arquivo físico usando xlsxwriter (mais estável para criar)
            with pd.ExcelWriter(caminho, engine='xlsxwriter') as writer:
                df_dados.to_excel(writer, sheet_name='Dados', index=False)
                df_projetos.to_excel(writer, sheet_name='Projetos', index=False)
                
        except Exception as e:
            st.error(f"Erro fatal ao criar banco de dados: {e}")
            return None
            
    return caminho

# ==================================================
# 2. FUNÇÕES DO DASHBOARD (CORRIGIDAS)
# ==================================================
def listar_todos_projetos():
    """
    Retorna um DataFrame com todos os projetos.
    CORREÇÃO: Retorna DataFrame, não lista (para funcionar com df.empty).
    """
    caminho = _garantir_banco_existe()
    if not caminho: 
        return pd.DataFrame() # Retorna DF vazio para não quebrar o dashboard

    try:
        # Lê a aba Projetos
        df = pd.read_excel(caminho, sheet_name="Projetos")
        
        # Garante que as colunas existem (evita KeyError)
        colunas_obrigatorias = ['_id', 'status', 'disciplina', 'cliente', 'obra', 'fornecedor', 'valor_total']
        for col in colunas_obrigatorias:
            if col not in df.columns:
                df[col] = "" # Cria coluna vazia se faltar
                
        return df # <--- AGORA RETORNA DATAFRAME
        
    except Exception as e:
        print(f"Erro ao ler Projetos: {e}")
        return pd.DataFrame()

def atualizar_status_projeto(id_projeto, novo_status):
    """Atualiza o status de um projeto no Excel."""
    caminho = _garantir_banco_existe()
    if not caminho: return False

    try:
        df = pd.read_excel(caminho, sheet_name="Projetos")
        # Localiza e atualiza
        mask = df['_id'].astype(str) == str(id_projeto)
        if mask.any():
            df.loc[mask, 'status'] = novo_status
            
            # Salva preservando a aba Dados
            with pd.ExcelWriter(caminho, engine='openpyxl', mode='a', if_sheet_exists='replace') as writer:
                df.to_excel(writer, sheet_name="Projetos", index=False)
            return True
    except Exception as e:
        st.error(f"Erro ao atualizar status: {e}")
    return False

# ==================================================
# 3. FUNÇÕES DOS GERADORES (ESC. DUTOS, ETC)
# ==================================================
def carregar_opcoes():
    """Carrega listas de opções (Técnico, SMS) para os selectbox."""
    caminho = _garantir_banco_existe()
    opcoes = {'tecnico': [], 'qualidade': [], 'sms': []}
    
    if not caminho: return opcoes

    try:
        df = pd.read_excel(caminho, sheet_name="Dados")
        if 'Categoria' in df.columns and 'Item' in df.columns:
            opcoes['tecnico'] = df[df['Categoria'] == 'Tecnico']['Item'].dropna().unique().tolist()
            opcoes['qualidade'] = df[df['Categoria'] == 'Qualidade']['Item'].dropna().unique().tolist()
            opcoes['sms'] = df[df['Categoria'] == 'SMS']['Item'].dropna().unique().tolist()
    except:
        pass
    return opcoes

def listar_fornecedores():
    """Retorna lista de dicionários com fornecedores."""
    caminho = _garantir_banco_existe()
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
    caminho = _garantir_banco_existe()
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
    """Cadastra novo fornecedor."""
    caminho = _garantir_banco_existe()
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
    caminho = _garantir_banco_existe()
    if not caminho: return False

    try:
        try:
            df_atual = pd.read_excel(caminho, sheet_name="Projetos")
        except:
            df_atual = pd.DataFrame()

        # Prepara dados (converte tudo para string para evitar erro de objeto)
        dados_salvar = dados.copy()
        for k, v in dados_salvar.items():
            if isinstance(v, (list, dict)): dados_salvar[k] = str(v)
            if isinstance(v, datetime): dados_salvar[k] = v.strftime("%Y-%m-%d")

        # Gera ID único se for novo
        if '_id' not in dados_salvar or not dados_salvar['_id']:
            dados_salvar['_id'] = datetime.now().strftime("%Y%m%d%H%M%S")

        # Adiciona nova linha
        novo_registro = pd.DataFrame([dados_salvar])
        df_final = pd.concat([df_atual, novo_registro], ignore_index=True)

        with pd.ExcelWriter(caminho, engine='openpyxl', mode='a', if_sheet_exists='replace') as writer:
            df_final.to_excel(writer, sheet_name="Projetos", index=False)
        
        return True
    except Exception as e:
        st.error(f"Erro ao salvar: {e}")
        return False
