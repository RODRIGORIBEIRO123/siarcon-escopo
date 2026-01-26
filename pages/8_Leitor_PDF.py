import streamlit as st
import pdfplumber
import pandas as pd
import re
from io import BytesIO

st.set_page_config(page_title="Auditor Turbo PDF", page_icon="⚡", layout="wide")

# ==================================================
# ⚙️ BARRA LATERAL (DO TURBO) - AJUSTES DE LEITURA
# ==================================================
with st.sidebar:
    st.header("⚙️ Ajustes de Leitura")
    st.info("Se as tabelas vierem bagunçadas, ajuste aqui:")
    
    metodo = st.radio(
        "Método de Detecção:",
        ("lattice", "stream"),
        index=0,
        help="'Lattice' = Tabelas com linhas desenhadas.\n'Stream' = Tabelas com espaços em branco."
    )
    
    tolerancia = st.slider(
        "Tolerância (x-tolerance)",
        min_value=1, max_value=10, value=3,
        help="Aumente se as colunas estiverem quebrando."
    )

# ==================================================
# 🧠 FUNÇÕES ROBUSTAS (DO TURBO)
# ==================================================
def limpar_cabecalho(lista_colunas):
    """
    Função vital: Impede o erro 'Duplicate column names'
    Renomeia colunas vazias ou repetidas automaticamente.
    """
    colunas_limpas = []
    contagem = {}

    for i, col in enumerate(lista_colunas):
        # 1. Trata None ou Vazio
        if col is None or str(col).strip() == "":
            nome_base = f"Coluna_{i+1}"
        else:
            nome_base = str(col).strip().replace('\n', ' ')

        # 2. Trata Duplicatas
        if nome_base in contagem:
            contagem[nome_base] += 1
            novo_nome = f"{nome_base}_{contagem[nome_base]}"
        else:
            contagem[nome_base] = 0
            novo_nome = nome_base

        colunas_limpas.append(novo_nome)

    return colunas_limpas

# ==================================================
# 🧠 CÉREBRO ANALÍTICO (DO AUDITOR)
# ==================================================
def analisar_texto_inteligente(texto_completo):
    analise = {
        "resumo": "Não identificado.",
        "escopo_detectado": [],
        "alertas": [],
        "sugestoes": []
    }

    # 1. RESUMO
    match_resumo = re.search(r'(?i)(ref\.|assunto|objeto|referência)[:\s]+(.+)', texto_completo)
    if match_resumo:
        analise["resumo"] = match_resumo.group(2).split('\n')[0]
    else:
        analise["resumo"] = texto_completo[:300].replace('\n', ' ') + "..."

    # 2. ESCOPO
    palavras_chave = ["Escopo", "Descrição dos Serviços", "Objeto", "Serviços Inclusos", "Premissas"]
    linhas = texto_completo.split('\n')
    capturando = False
    
    for linha in linhas:
        if any(key in linha for key in palavras_chave) and len(linha) < 60:
            capturando = True
            analise["escopo_detectado"].append(f"📌 **{linha.strip()}**")
            continue
        
        if capturando:
            if any(x in linha for x in ["Valor", "Total", "Condições", "Pagamento"]):
                capturando = False
            elif len(linha.strip()) > 3:
                analise["escopo_detectado"].append(linha.strip())
    
    if not analise["escopo_detectado"]:
        analise["escopo_detectado"].append("Não consegui isolar o texto do escopo automaticamente.")

    # 3. ALERTAS (RISCOS)
    obrigatorios = {
        "Validade Proposta": ["validade", "vencimento"],
        "Prazo Entrega": ["prazo", "entrega", "cronograma"],
        "Pagamento": ["pagamento", "faturamento"],
        "Impostos": ["impostos", "icms", "iss", "tributos"]
    }

    for item, keywords in obrigatorios.items():
        if not any(k in texto_completo.lower() for k in keywords):
            analise["alertas"].append(f"⚠️ **{item}** não encontrado.")
            analise["sugestoes"].append(f"Pedir clareza sobre: **{item}**.")

    # 4. DATA ANTIGA
    anos = re.findall(r'202[0-9]', texto_completo)
    if anos:
        ano_atual = pd.Timestamp.now().year
        if any(int(a) < (ano_atual - 1) for a in anos):
            analise["alertas"].append(f"🚨 Possível documento antigo detectado (Anos: {set(anos)}).")

    return analise

# ==================================================
# 🖥
