import streamlit as st
import pandas as pd
import os
from datetime import datetime

# ==================================================
# 1. NÚCLEO: GESTÃO DO ARQUIVO EXCEL
# ==================================================
def _get_caminho_banco():
    """Retorna o caminho absoluto do DB_SIARCON.xlsx."""
    nome_arquivo = "DB_SIARCON.xlsx"
    diretorio_base = os.path.dirname(os.path.abspath(__file__))
    
    # Procura na raiz, na pasta dados ou na pasta pai
    locais = [
        os.path.join(diretorio_base, nome_arquivo),
        os.path.join(diretorio_base, "dados", nome_arquivo),
        os.path.join(diretorio_base, "..", nome_arquivo)
    ]

    for caminho in locais:
        if os.path.exists(caminho):
            return caminho
            
    # Padrão: cria na raiz
    return os.path.join(diretorio_base, nome_arquivo)

def _criar_dados_padrao():
    """Gera dados iniciais para não deixar os selects vazios."""
    dados_iniciais = [
        # TÉCNICO
        {'Categoria': 'Tecnico', 'Item': 'Conforme projeto executivo'},
        {'Categoria': 'Tecnico', 'Item': 'Conforme especificação técnica'},
        {'Categoria': 'Tecnico', 'Item': 'Inclui suportação e fixação'},
        {'Categoria': 'Tecnico', 'Item': 'Inclui testes de estanqueidade'},
        # QUALIDADE
        {'Categoria': 'Qualidade', 'Item': 'Databook completo'},
        {'Categoria': 'Qualidade', 'Item': 'Certificado de calibração'},
        {'Categoria': 'Qualidade', 'Item': 'Relatório fotográfico'},
        # SMS
        {'Categoria': 'SMS', 'Item': 'NR-06 (EPI)'},
        {'Categoria': 'SMS', 'Item': 'NR-10 (Elétrica)'},
        {'Categoria': 'SMS', 'Item': 'NR-35 (Altura)'},
        {'Categoria': 'SMS', 'Item': 'ASO e Fichas de Registro'}
    ]
    return pd.DataFrame(dados_iniciais)

def _garantir_banco_existe():
    """Cria o Excel com dados padrão se ele não existir."""
    caminho = _get_caminho_banco()
    
    if not os.path.exists(caminho):
        try:
            # 1. Cria Aba DADOS (com itens padrão)
            df_dados = _criar_dados_padrao()
            
            # 2. Cria Aba PROJETOS (vazia, mas com colunas certas)
            df_projetos = pd.DataFrame(columns=[
                '_id', 'status', 'disciplina', 'cliente', 'obra', 
                'fornecedor', 'valor_total', 'revisao', 'data_inicio'
            ])
            
            # 3. Salva
            with pd.ExcelWriter(caminho, engine='xlsxwriter') as writer:
                df_dados.to_excel(writer, sheet_name='Dados', index=False)
                df_projetos.to_excel(writer, sheet_name='Projetos', index=False)
                
            print(f"✅ Banco criado e populado em: {caminho}")
        except Exception as e:
            st.error(f"Erro fatal ao criar DB: {e}")
            return None
            
    return caminho

# ==================================================
# 2. FUNÇÕES DO DASHBOARD (Correção do AttributeError)
# ==================================================
def listar_todos_projetos():
    """
    IMPORTANTE: Retorna sempre um DataFrame pandas.
    Resolve o erro 'AttributeError: list object has no attribute empty'.
    """
    caminho = _garantir_banco_existe()
    if not caminho: return pd.DataFrame()

    try:
        df = pd.read_excel(caminho, sheet_name="Projetos")
        
        # Garante colunas mínimas para o Dashboard não quebrar
        cols_obrigatorias = ['_id', 'status', 'disciplina', 'cliente', 'obra', 'fornecedor', 'valor_total']
        for col in cols_obrigatorias:
            if col not in df.columns:
                df[col] = "" 
        
        return df # <--- RETORNA DATAFRAME
    except Exception as e:
        st.error(f"Erro ao ler Projetos: {e}")
        return pd.DataFrame()

def atualizar_status_projeto(id_projeto, novo_status):
    caminho = _garantir_banco_existe()
    if not caminho: return False

    try:
        df = pd.read_excel(caminho, sheet_name="Projetos")
        # Converte ID para string para garantir match
        df['_id'] = df['_id'].astype(str)
        mask = df['_id'] == str(id_projeto)
        
        if mask.any():
            df.loc[mask, 'status'] = novo_status
            with pd.ExcelWriter(caminho, engine='openpyxl', mode='a', if_sheet_exists='replace') as writer:
                df.to_excel(writer, sheet_name="Projetos", index=False)
            return True
    except:
        pass
    return False

# ==================================================
# 3. FUNÇÕES DOS GERADORES (Dutos, Hidraulica...)
# ==================================================
def carregar_opcoes():
    """Lê opções para preencher os Selectbox."""
    caminho = _garantir_banco_existe()
    opcoes = {'tecnico': [], 'qualidade': [], 'sms': []}
    
    if not caminho: return opcoes

    try:
        df = pd.read_excel(caminho, sheet_name="Dados")
        if 'Categoria' in df.columns and 'Item' in df.columns:
            opcoes['tecnico'] = sorted(df[df['Categoria'] == 'Tecnico']['Item'].dropna().unique().tolist())
            opcoes['qualidade'] = sorted(df[df['Categoria'] == 'Qualidade']['Item'].dropna().unique().tolist())
            opcoes['sms'] = sorted(df[df['Categoria'] == 'SMS']['Item'].dropna().unique().tolist())
    except:
        pass
        
    return opcoes

def listar_fornecedores():
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
    caminho = _garantir_banco_existe()
    if not caminho: return False
    
    try:
        df = pd.read_excel(caminho, sheet_name="Dados")
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
    caminho = _garantir_banco_existe()
    if not caminho: return False

    try:
        try:
            df_atual = pd.read_excel(caminho, sheet_name="Projetos")
        except:
            df_atual = pd.DataFrame()

        # Limpeza de dados
        dados_salvar = dados.copy()
        for k, v in dados_salvar.items():
            if isinstance(v, (list, dict)): dados_salvar[k] = str(v)
            if isinstance(v, datetime): dados_salvar[k] = v.strftime("%Y-%m-%d")

        if '_id' not in dados_salvar or not dados_salvar['_id']:
            dados_salvar['_id'] = datetime.now().strftime("%Y%m%d%H%M%S")

        novo_registro = pd.DataFrame([dados_salvar])
        df_final = pd.concat([df_atual, novo_registro], ignore_index=True)

        with pd.ExcelWriter(caminho, engine='openpyxl', mode='a', if_sheet_exists='replace') as writer:
            df_final.to_excel(writer, sheet_name="Projetos", index=False)
        
        return True
    except Exception as e:
        st.error(f"Erro ao salvar: {e}")
        return False
