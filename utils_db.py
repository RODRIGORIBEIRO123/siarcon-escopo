import streamlit as st
import pandas as pd
import os
import json
from datetime import datetime

# Nome do arquivo onde os dados serão salvos localmente
DB_FILE = "dados_projetos.json"
FORNECEDORES_FILE = "dados_fornecedores.json"
ITENS_FILE = "dados_itens.json"

# --- FUNÇÕES AUXILIARES ---
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

# --- GERENCIAMENTO DE PROJETOS ---
def listar_todos_projetos():
    dados = carregar_dados(DB_FILE)
    if not dados:
        return pd.DataFrame(columns=["_id_linha", "Cliente", "Obra", "Disciplina", "Status", "Fornecedor"])
    
    # Converte para DataFrame
    df = pd.DataFrame(dados)
    # Garante que as colunas principais existam para não dar erro no display
    cols_obrigatorias = ["_id_linha", "Cliente", "Obra", "Disciplina", "Status", "Fornecedor"]
    for col in cols_obrigatorias:
        if col not in df.columns:
            df[col] = ""
            
    return df

def criar_pacote_obra(cliente, obra, disciplinas):
    dados = carregar_dados(DB_FILE)
    
    for disc in disciplinas:
        novo_projeto = {
            "_id_linha": str(datetime.now().timestamp()) + "_" + disc, # ID único
            "Cliente": cliente,
            "Obra": obra,
            "Disciplina": disc,
            "Status": "Não Iniciado",
            "Fornecedor": "",
            "Data Criacao": datetime.now().strftime("%Y-%m-%d")
        }
        dados.append(novo_projeto)
    
    salvar_dados(DB_FILE, dados)
    return True

def registrar_projeto(dados_projeto, id_linha=None):
    """Atualiza ou cria um projeto completo"""
    lista_projetos = carregar_dados(DB_FILE)
    
    # Se já tem ID, é atualização
    if id_linha:
        for i, proj in enumerate(lista_projetos):
            if proj.get("_id_linha") == id_linha:
                # Atualiza mantendo o ID
                dados_atualizados = {**proj, **dados_projeto}
                # Garante que campos chave fiquem maiúsculos para o Kanban
                dados_atualizados["Cliente"] = dados_projeto.get("cliente", proj["Cliente"])
                dados_atualizados["Obra"] = dados_projeto.get("obra", proj["Obra"])
                dados_atualizados["Status"] = dados_projeto.get("status", proj["Status"])
                dados_atualizados["Fornecedor"] = dados_projeto.get("fornecedor", proj["Fornecedor"])
                dados_atualizados["Disciplina"] = dados_projeto.get("disciplina", proj["Disciplina"])
                
                lista_projetos[i] = dados_atualizados
                salvar_dados(DB_FILE, lista_projetos)
                return True
    
    return False

def excluir_projeto(id_linha):
    lista = carregar_dados(DB_FILE)
    nova_lista = [p for p in lista if p.get("_id_linha") != id_linha]
    salvar_dados(DB_FILE, nova_lista)
    return True

# --- GERENCIAMENTO DE APRENDIZADO (ITENS TÉCNICOS) ---
def carregar_opcoes():
    padrao = {
        "tecnico_dutos": ["Dutos em chapa galvanizada", "Grelhas e Difusores"],
        "tecnico_hidraulica": ["Tubulação de Aço Carbono", "Válvulas de Controle"],
        "tecnico_eletrica": ["Quadros Elétricos", "Cabos de Força", "Infraestrutura (Eletrocalhas)"],
        "tecnico_automacao": ["Controladores DDC", "Sensores de Temperatura", "Atuadores"],
        "tecnico_tab": ["Balanceamento de Ar", "Balanceamento de Água"],
        "tecnico_movimentacoes": ["Guindaste", "Munck", "Equipe de Remoção"],
        "tecnico_cobre": ["Tubulação de Cobre", "Isolamento Térmico", "Solda Phoscoper"],
        "sms": ["NR-10", "NR-35", "NR-12"],
        "qualidade_dutos": ["Teste de Estanqueidade", "Relatório Fotográfico"],
        "qualidade_cobre": ["Teste de Pressão (N2)", "Vácuo < 500 microns"]
    }
    salvos = carregar_dados(ITENS_FILE)
    if not salvos: return padrao
    # Mescla o que salvou com o padrão para garantir chaves
    return {**padrao, **salvos}

def aprender_novo_item(categoria, novo_item):
    opcoes = carregar_opcoes()
    if categoria not in opcoes:
        opcoes[categoria] = []
    
    if novo_item not in opcoes[categoria]:
        opcoes[categoria].append(novo_item)
        salvar_dados(ITENS_FILE, opcoes)
        return True
    return False # Já existia

# --- GERENCIAMENTO DE FORNECEDORES ---
def listar_fornecedores():
    return carregar_dados(FORNECEDORES_FILE)

def cadastrar_fornecedor_db(nome, cnpj):
    fornecedores = listar_fornecedores()
    # Verifica duplicidade
    for f in fornecedores:
        if f['Fornecedor'].upper() == nome.upper() or f['CNPJ'] == cnpj:
            return "Existe"
    
    fornecedores.append({"Fornecedor": nome, "CNPJ": cnpj})
    salvar_dados(FORNECEDORES_FILE, fornecedores)
    return True
