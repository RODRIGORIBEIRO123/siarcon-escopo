import streamlit as st
import pandas as pd
import os
from datetime import datetime

# --- 1. CARREGAMENTO BLINDADO DO EXCEL ---
@st.cache_data
def carregar_banco_dados():
    # Lista de tentativas de nome e caminho
    nomes = ["DB_SIARCON.xlsx", "DB_SIARCON.xls"]
    pastas = [".", "dados", "..", "../dados"] # Raiz, pasta dados, pasta pai, pasta dados do pai
    
    diretorio_base = os.path.dirname(os.path.abspath(__file__))

    for pasta in pastas:
        for nome in nomes:
            caminho = os.path.join(diretorio_base, pasta, nome)
            if os.path.exists(caminho):
                try:
                    return pd.read_excel(caminho)
                except Exception as e:
                    print(f"Erro ao ler {caminho}: {e}")
    
    # Se não achar nada, retorna DataFrame vazio para não travar o app
    return pd.DataFrame(columns=["Categoria", "Item", "Fornecedor", "CNPJ"])

# --- 2. FUNÇÕES DE LEITURA ---
def carregar_opcoes():
    df = carregar_banco_dados()
    opcoes = {
        'tecnico': df[df['Categoria'] == 'Tecnico']['Item'].unique().tolist(),
        'qualidade': df[df['Categoria'] == 'Qualidade']['Item'].unique().tolist(),
        'sms': df[df['Categoria'] == 'SMS']['Item'].unique().tolist()
    }
    return opcoes

def listar_fornecedores():
    df = carregar_banco_dados()
    # Filtra apenas linhas que tem Fornecedor preenchido
    forn = df[['Fornecedor', 'CNPJ']].dropna(subset=['Fornecedor']).drop_duplicates()
    return forn.to_dict('records')

# --- 3. FUNÇÕES DE ESCRITA (SIMULADO - Para funcionar precisa salvar no Excel) ---
def aprender_novo_item(categoria, novo_item):
    # Aqui você implementaria a lógica para salvar no Excel de verdade
    # Por enquanto, salva na sessão para não perder durante o uso
    if 'opcoes_db' in st.session_state:
        if categoria in st.session_state['opcoes_db']:
            st.session_state['opcoes_db'][categoria].append(novo_item)
    return True

def cadastrar_fornecedor_db(nome, cnpj):
    # Aqui entraria o código para append no Excel
    return True

def registrar_projeto(dados, id_linha=None):
    # Aqui entraria o código para salvar o projeto na aba "Projetos" do Excel
    # Exibe no terminal para debug
    print(f"Salvo projeto de {dados['disciplina']} para {dados['fornecedor']}")
    return True
