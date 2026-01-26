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
# 🖥️ APLICAÇÃO PRINCIPAL
# ==================================================
st.title("⚡ Leitor & Auditor de Propostas")
st.markdown("Extração robusta de tabelas + Análise de contrato.")

arquivo = st.file_uploader("Carregue o PDF aqui", type=["pdf"])

if arquivo:
    st.divider()
    with st.spinner("Processando (Modo Turbo + Auditor)..."):
        try:
            texto_full = ""
            tabelas_finais = []
            
            with pdfplumber.open(arquivo) as pdf:
                total_paginas = len(pdf.pages)
                bar = st.progress(0)
                
                for i, page in enumerate(pdf.pages):
                    # A. Extração de Texto (Para o Auditor)
                    texto_full += (page.extract_text() or "") + "\n"
                    
                    # B. Extração de Tabelas (Modo Turbo)
                    # Usa as configurações da Barra Lateral para evitar erros
                    tabelas = page.extract_tables({
                        "vertical_strategy": "lines" if metodo == "lattice" else "text",
                        "horizontal_strategy": "lines" if metodo == "lattice" else "text",
                        "snap_tolerance": tolerancia,
                    })
                    
                    for tab in tabelas:
                        df = pd.DataFrame(tab)
                        # Remove linhas vazias
                        df = df.dropna(how='all')
                        
                        if not df.empty and len(df) > 1:
                            # --- AQUI ESTÁ A CORREÇÃO DO ERRO ---
                            cabecalho_bruto = df.iloc[0].tolist()
                            
                            # Limpa nomes duplicados ou None ANTES de criar as colunas
                            cabecalho_limpo = limpar_cabecalho(cabecalho_bruto)
                            
                            df.columns = cabecalho_limpo
                            df = df[1:].reset_index(drop=True) # Remove a linha do header
                            
                            tabelas_finais.append(df)
                    
                    bar.progress((i + 1) / total_paginas)

            # --- EXIBIÇÃO: PARTE 1 (AUDITORIA) ---
            resultado = analisar_texto_inteligente(texto_full)
            
            st.markdown(f"### 📄 Resumo: {resultado['resumo']}")
            
            col1, col2 = st.columns(2)
            with col1:
                st.subheader("🔍 Escopo Detectado")
                with st.container(border=True):
                    for linha in resultado["escopo_detectado"]:
                        if "📌" in linha: st.markdown(f"**{linha}**")
                        else: st.write(linha)

            with col2:
                st.subheader("🚨 Riscos & Alertas")
                with st.container(border=True):
                    if resultado["alertas"]:
                        for a in resultado["alertas"]: st.error(a)
                    else: st.success("✅ Documento parece completo.")
                    
                    if resultado["sugestoes"]:
                        st.caption("Sugestões:")
                        for s in resultado["sugestoes"]: st.info(s)

            st.divider()

            # --- EXIBIÇÃO: PARTE 2 (MATERIAIS / TABELAS) ---
            st.subheader(f"📦 Listas de Materiais ({len(tabelas_finais)} encontradas)")
            
            if tabelas_finais:
                for idx, df in enumerate(tabelas_finais):
                    with st.expander(f"📋 Tabela {idx+1} ({len(df)} linhas) - Clique para ver", expanded=(idx==0)):
                        st.dataframe(df, use_container_width=True)
                        csv = df.to_csv(index=False).encode('utf-8')
                        st.download_button(f"📥 Baixar CSV", csv, f"tabela_{idx+1}.csv", "text/csv")
            else:
                st.warning("Nenhuma tabela estruturada encontrada. Tente mudar para 'Stream' na barra lateral.")

        except Exception as e:
            st.error(f"Erro crítico no processamento: {e}")
