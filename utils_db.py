import streamlit as st
import pandas as pd
import os
from datetime import datetime

# ==================================================
# 1. LOCALIZADOR DE ARQUIVO
# ==================================================
def _get_caminho_banco():
    """Procura o arquivo DB_SIARCON.xlsx na pasta atual, na dados ou na raiz."""
    nome_arquivo = "DB_SIARCON.xlsx"
    # Locais possíveis onde o arquivo pode estar
    diretorio_base = os.path.dirname(os.path.abspath(__file__))
    
    locais = [
        os.path.join(diretorio_base, nome_arquivo),           # Pasta atual
        os.path.join(diretorio_base, "dados", nome_arquivo),  # Pasta dados
        os.path.join(diretorio_base, "..", nome_arquivo),     # Pasta pai (raiz)
        os.path.join(diretorio_base, "..", "dados", nome_arquivo) # Pasta dados na raiz
    ]

    for caminho in locais:
        if os.path.exists(caminho):
            return caminho
            
    # Se não achar, retorna o caminho padrão na raiz para tentar criar/salvar
    return os.path.join(diretorio_base, "..", nome_arquivo)

# ==================================================
# 2. FUNÇÃO DO DASHBOARD (CORRIGIDA)
# ==================================================
def listar_todos_projetos():
    """
    Retorna um DATAFRAME (Tabela) para o Dashboard.
    Isso corrige o erro: 'AttributeError: ... has no attribute empty'
    """
    caminho = _get_caminho_banco()
    
    if not os.path.exists(caminho):
        return pd.DataFrame() # Retorna tabela vazia se não tiver arquivo

    try:
        df = pd.read_excel(caminho, sheet_name="Projetos")
        
        # Garante que as colunas existem para não dar erro de chave
        cols_obrigatorias = ['_id', 'status', 'disciplina', 'cliente', 'obra', 'fornecedor', 'valor_total']
        for col in cols_obrigatorias:
            if col not in df.columns:
                df[col] = "" 
        
        return df # <--- IMPORTANTE: Retorna DataFrame, não lista/dict
    except Exception as e:
        # Se a aba Projetos não existir, retorna vazio
        return pd.DataFrame()

def atualizar_status_projeto(id_projeto, novo_status):
    caminho = _get_caminho_banco()
    if not os.path.exists(caminho): return False

    try:
        df = pd.read_excel(caminho, sheet_name="Projetos")
        # Converte ID para string para garantir comparação correta
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
# 3. FUNÇÕES DOS GERADORES (CORRIGIDAS PARA MINÚSCULO)
# ==================================================
def carregar_opcoes():
    """Carrega as opções da aba Dados."""
    caminho = _get_caminho_banco()
    opcoes = {'tecnico': [], 'qualidade': [], 'sms': []}
    
    if not os.path.exists(caminho): return opcoes

    try:
        df = pd.read_excel(caminho, sheet_name="Dados")
        
        if 'Categoria' in df.columns and 'Item' in df.columns:
            # Normaliza para minúsculo para garantir que encontre 'tecnico' ou 'Tecnico'
            df['Categoria'] = df['Categoria'].astype(str).str.lower().str.strip()
            
            # Filtra baseado na sua planilha (que usa 'tecnico' minúsculo)
            opcoes['tecnico'] = sorted(df[df['Categoria'] == 'tecnico']['Item'].dropna().unique().tolist())
            opcoes['qualidade'] = sorted(df[df['Categoria'].str.contains('qualidade')]['Item'].dropna().unique().tolist())
            opcoes['sms'] = sorted(df[df['Categoria'] == 'sms']['Item'].dropna().unique().tolist())
            
    except Exception as e:
        print(f"Erro ao ler opções: {e}")
        pass
        
    return opcoes

def listar_fornecedores():
    caminho = _get_caminho_banco()
    if not os.path.exists(caminho): return []

    try:
        df = pd.read_excel(caminho, sheet_name="Dados")
        if 'Fornecedor' in df.columns:
            return df[['Fornecedor', 'CNPJ']].dropna(subset=['Fornecedor']).drop_duplicates().to_dict('records')
    except:
        pass
    return []

def aprender_novo_item(categoria, novo_item):
    caminho = _get_caminho_banco()
    
    try:
        # Se arquivo não existe, cria
        if not os.path.exists(caminho):
            df = pd.DataFrame(columns=['Categoria', 'Item'])
        else:
            df = pd.read_excel(caminho, sheet_name="Dados")
            
        # Adiciona item (força categoria minúscula para padronizar)
        novo = pd.DataFrame([{'Categoria': categoria.lower(), 'Item': novo_item}])
        df_final = pd.concat([df, novo], ignore_index=True)
        
        # Salva
        if os.path.exists(caminho):
            with pd.ExcelWriter(caminho, engine='openpyxl', mode='a', if_sheet_exists='replace') as writer:
                df_final.to_excel(writer, sheet_name="Dados", index=False)
        else:
            with pd.ExcelWriter(caminho, engine='xlsxwriter') as writer:
                df_final.to_excel(writer, sheet_name="Dados", index=False)
                # Cria aba projetos vazia para não dar erro depois
                pd.DataFrame(columns=['_id']).to_excel(writer, sheet_name="Projetos", index=False)
                
        return True
    except:
        return False

def cadastrar_fornecedor_db(nome, cnpj):
    caminho = _get_caminho_banco()
    
    try:
        if os.path.exists(caminho):
            df = pd.read_excel(caminho, sheet_name="Dados")
            if 'Fornecedor' in df.columns and not df[df['Fornecedor'] == nome].empty:
                return "Existe"
        else:
            df = pd.DataFrame(columns=['Fornecedor', 'CNPJ'])

        novo = pd.DataFrame([{'Fornecedor': nome, 'CNPJ': cnpj}])
        df_final = pd.concat([df, novo], ignore_index=True)
        
        if os.path.exists(caminho):
            with pd.ExcelWriter(caminho, engine='openpyxl', mode='a', if_sheet_exists='replace') as writer:
                df_final.to_excel(writer, sheet_name="Dados", index=False)
        else:
             with pd.ExcelWriter(caminho, engine='xlsxwriter') as writer:
                df_final.to_excel(writer, sheet_name="Dados", index=False)
                pd.DataFrame(columns=['_id']).to_excel(writer, sheet_name="Projetos", index=False)
        return True
    except:
        return False

def registrar_projeto(dados, id_linha=None):
    caminho = _get_caminho_banco()
    
    try:
        if os.path.exists(caminho):
            try:
                df_atual = pd.read_excel(caminho, sheet_name="Projetos")
            except:
                df_atual = pd.DataFrame()
        else:
            df_atual = pd.DataFrame()

        dados_salvar = dados.copy()
        for k, v in dados_salvar.items():
            if isinstance(v, (list, dict)): dados_salvar[k] = str(v)
            if isinstance(v, datetime): dados_salvar[k] = v.strftime("%Y-%m-%d")

        if '_id' not in dados_salvar or not dados_salvar['_id']:
            dados_salvar['_id'] = datetime.now().strftime("%Y%m%d%H%M%S")

        novo_registro = pd.DataFrame([dados_salvar])
        df_final = pd.concat([df_atual, novo_registro], ignore_index=True)

        if os.path.exists(caminho):
            with pd.ExcelWriter(caminho, engine='openpyxl', mode='a', if_sheet_exists='replace') as writer:
                df_final.to_excel(writer, sheet_name="Projetos", index=False)
        else:
            with pd.ExcelWriter(caminho, engine='xlsxwriter') as writer:
                # Garante que a aba Dados exista também
                pd.DataFrame(columns=['Categoria', 'Item']).to_excel(writer, sheet_name="Dados", index=False)
                df_final.to_excel(writer, sheet_name="Projetos", index=False)
        
        return True
    except Exception as e:
        st.error(f"Erro ao salvar: {e}")
        return False
