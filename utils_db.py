import streamlit as st
import pandas as pd
import os
import json
from datetime import datetime

# --- CONFIGURAÇÃO (JSON LOCAL) ---
DB_FILE = "dados_projetos.json"

# --- FUNÇÕES BÁSICAS ---
def carregar_dados(arquivo):
    if os.path.exists(arquivo):
        try:
            with open(arquivo, "r", encoding="utf-8") as f:
                return json.load(f)
        except: return []
    return []

def salvar_dados(arquivo, dados):
    with open(arquivo, "w", encoding="utf-8") as f:
        json.dump(dados, f, ensure_ascii=False, indent=4)

# --- FUNÇÕES DO KANBAN ---
def listar_todos_projetos():
    # Carrega dados brutos
    dados = carregar_dados(DB_FILE)
    
    # Se vazio, retorna estrutura vazia para não quebrar o Kanban
    if not dados:
        return pd.DataFrame(columns=["_id_linha", "Cliente", "Obra", "Disciplina", "Status", "Fornecedor"])
    
    df = pd.DataFrame(dados)
    
    # Garante que as colunas essenciais existam
    colunas_obrigatorias = ["_id_linha", "Cliente", "Obra", "Disciplina", "Status", "Fornecedor"]
    for col in colunas_obrigatorias:
        if col not in df.columns:
            df[col] = ""
            
    return df

def criar_pacote_obra(cliente, obra, disciplinas):
    dados = carregar_dados(DB_FILE)
    for disc in disciplinas:
        novo = {
            "_id_linha": f"{int(datetime.now().timestamp())}_{disc}", 
            "Cliente": cliente,
            "Obra": obra,
            "Disciplina": disc,
            "Status": "Não Iniciado",
            "Fornecedor": "",
            "Data Criacao": datetime.now().strftime("%Y-%m-%d")
        }
        dados.append(novo)
    salvar_dados(DB_FILE, dados)
    return True

def excluir_projeto(id_linha):
    lista = carregar_dados(DB_FILE)
    nova_lista = [p for p in lista if p.get("_id_linha") != id_linha]
    salvar_dados(DB_FILE, nova_lista)
    return True

# --- FUNÇÕES DE DETALHES (SALVAR ESCOPO) ---
def registrar_projeto(dados_novos, id_linha):
    lista = carregar_dados(DB_FILE)
    for i, proj in enumerate(lista):
        if proj.get("_id_linha") == id_linha:
            # Atualiza os dados
            proj.update(dados_novos)
            # Garante que os campos do Kanban sejam atualizados também
            proj["Cliente"] = dados_novos.get("cliente", proj["Cliente"])
            proj["Obra"] = dados_novos.get("obra", proj["Obra"])
            proj["Status"] = dados_novos.get("status", proj["Status"])
            
            lista[i] = proj
            salvar_dados(DB_FILE, lista)
            return True
    return False

# --- FUNÇÕES AUXILIARES (FORNECEDORES/ITENS) ---
def listar_fornecedores():
    # Simples para evitar erro, pode expandir depois
    return [{"Fornecedor": "Teste", "CNPJ": "000"}]

def cadastrar_fornecedor_db(nome, cnpj):
    return True

def aprender_novo_item(cat, item):
    return True

def carregar_opcoes():
    return {}
