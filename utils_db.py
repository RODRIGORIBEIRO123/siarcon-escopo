import streamlit as st
import pandas as pd
import os
import json
from datetime import datetime

# --- CONFIGURAÇÃO DOS ARQUIVOS (JSON) ---
DB_FILE = "dados_projetos.json"
FORNECEDORES_FILE = "dados_fornecedores.json"
ITENS_FILE = "dados_itens.json"

# --- FUNÇÕES BÁSICAS DE ARQUIVO ---
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

# --- FUNÇÕES DE PROJETOS ---
def listar_todos_projetos():
    dados = carregar_dados(DB_FILE)
    if not dados:
        # Retorna DataFrame vazio com as colunas certas para não quebrar o Kanban
        return pd.DataFrame(columns=["_id_linha", "Cliente", "Obra", "Disciplina", "Status", "Fornecedor"])
    
    df = pd.DataFrame(dados)
    # Garante colunas mínimas
    cols = ["_id_linha", "Cliente", "Obra", "Disciplina", "Status", "Fornecedor"]
    for c in cols:
        if c not in df.columns: df[c] = ""
    return df

def criar_pacote_obra(cliente, obra, disciplinas):
    dados = carregar_dados(DB_FILE)
    for disc in disciplinas:
        novo = {
            "_id_linha": f"{int(datetime.now().timestamp())}_{disc}", 
            "Cliente": cliente, "Obra": obra, "Disciplina": disc,
            "Status": "Não Iniciado", "Fornecedor": "",
            "Data Criacao": datetime.now().strftime("%Y-%m-%d")
        }
        dados.append(novo)
    salvar_dados(DB_FILE, dados)
    return True

def registrar_projeto(dados_novos, id_linha):
    lista = carregar_dados(DB_FILE)
    for i, proj in enumerate(lista):
        if proj.get("_id_linha") == id_linha:
            # Atualiza dicionário existente com novos dados
            proj.update(dados_novos)
            # Garante campos chave para o Kanban
            proj["Cliente"] = dados_novos.get("cliente", proj["Cliente"])
            proj["Obra"] = dados_novos.get("obra", proj["Obra"])
            proj["Status"] = dados_novos.get("status", proj["Status"])
            proj["Disciplina"] = dados_novos.get("disciplina", proj["Disciplina"])
            proj["Fornecedor"] = dados_novos.get("fornecedor", proj["Fornecedor"])
            
            lista[i] = proj
            salvar_dados(DB_FILE, lista)
            return True
    return False

def excluir_projeto(id_linha):
    lista = carregar_dados(DB_FILE)
    nova_lista = [p for p in lista if p.get("_id_linha") != id_linha]
    salvar_dados(DB_FILE, nova_lista)
    return True

# --- FUNÇÕES DE APRENDIZADO (TÉCNICO) ---
def carregar_opcoes():
    padrao = {
        "tecnico_dutos": ["Dutos Galvanizados", "Difusores"],
        "tecnico_hidraulica": ["Tubulação Aço Carbono", "Válvulas"],
        "tecnico_eletrica": ["Quadros", "Cabos", "Eletrocalhas"],
        "tecnico_automacao": ["Sensores", "Controladores", "Atuadores"],
        "tecnico_tab": ["Balanceamento Ar", "Balanceamento Água"],
        "tecnico_movimentacoes": ["Guindaste", "Munck"],
        "tecnico_cobre": ["Tubos Cobre", "Isolamento", "Solda"],
        "sms": ["NR-10", "NR-35", "NR-06", "NR-12", "NR-18", "NR-33"],
        "qualidade_dutos": ["Teste Estanqueidade"],
        "qualidade_cobre": ["Teste Pressão N2"]
    }
    salvos = carregar_dados(ITENS_FILE)
    if not salvos: return padrao
    # Mescla dicionários
    for k, v in salvos.items():
        if k in padrao: padrao[k].extend([x for x in v if x not in padrao[k]])
        else: padrao[k] = v
    return padrao

def aprender_novo_item(categoria, item):
    if not item: return False
    dic_itens = carregar_dados(ITENS_FILE)
    if not isinstance(dic_itens, dict): dic_itens = {}
    
    if categoria not in dic_itens: dic_itens[categoria] = []
    
    if item not in dic_itens[categoria]:
        dic_itens[categoria].append(item)
        salvar_dados(ITENS_FILE, dic_itens)
        return True
    return False

# --- FUNÇÕES DE FORNECEDORES ---
def listar_fornecedores():
    return carregar_dados(FORNECEDORES_FILE)

def cadastrar_fornecedor_db(nome, cnpj):
    lista = listar_fornecedores()
    for f in lista:
        if f.get("Fornecedor", "").upper() == nome.upper(): return "Existe"
    lista.append({"Fornecedor": nome, "CNPJ": cnpj})
    salvar_dados(FORNECEDORES_FILE, lista)
    return True
