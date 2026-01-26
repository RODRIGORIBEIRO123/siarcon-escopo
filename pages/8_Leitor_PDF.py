import streamlit as st
import pdfplumber
import pandas as pd
import re
from io import BytesIO

st.set_page_config(page_title="Auditor de Propostas", page_icon="🧐", layout="wide")

# ==================================================
# 🧠 CÉREBRO ANALÍTICO (Regras de Negócio)
# ==================================================
def analisar_texto_inteligente(texto_completo):
    analise = {
        "resumo": "Não identificado.",
        "escopo_detectado": [],
        "alertas": [],
        "sugestoes": []
    }

    # 1. TENTA EXTRAIR UM RESUMO / OBJETIVO
    # Geralmente vem após "Ref.:", "Assunto:", "Objeto:"
    match_resumo = re.search(r'(?i)(ref\.|assunto|objeto|referência)[:\s]+(.+)', texto_completo)
    if match_resumo:
        analise["resumo"] = match_resumo.group(2).split('\n')[0] # Pega a primeira linha do assunto
    else:
        # Se não achar, pega os primeiros 300 caracteres como resumo provisório
        analise["resumo"] = texto_completo[:300].replace('\n', ' ') + "..."

    # 2. EXTRAÇÃO DETALHADA DO ESCOPO
    # Procura blocos de texto que comecem com palavras chave
    palavras_chave_escopo = ["Escopo", "Descrição dos Serviços", "Objeto", "Serviços Inclusos", "Premissas"]
    linhas = texto_completo.split('\n')
    capturando = False
    buffer_escopo = []

    for linha in linhas:
        # Se encontrar um título de seção, começa a capturar
        if any(key in linha for key in palavras_chave_escopo) and len(linha) < 50:
            capturando = True
            buffer_escopo.append(f"📌 **{linha.strip()}**") # Marca como título
            continue
        
        # Se capturando, guarda a linha
        if capturando:
            # Se encontrar outro título grande ou "Valor", "Total", para de capturar
            if "Valor" in linha or "Total" in linha or "Condições" in linha:
                capturando = False
            else:
                if len(linha.strip()) > 3: # Ignora linhas vazias
                    buffer_escopo.append(linha.strip())
    
    if buffer_escopo:
        analise["escopo_detectado"] = buffer_escopo
    else:
        analise["escopo_detectado"].append("Não consegui isolar o texto do escopo automaticamente.")

    # 3. VERIFICAÇÃO DE INCONSISTÊNCIAS (O Auditor)
    termos_obrigatorios = {
        "Validade": ["validade", "val.", "vencimento"],
        "Prazo de Entrega": ["prazo", "entrega", "cronograma"],
        "Condição de Pagamento": ["pagamento", "faturamento", "condição"],
        "Impostos": ["impostos", "tributos", "icms", "iss"],
        "Valor Total": ["valor total", "total global", "preço total"]
    }

    for item, keywords in termos_obrigatorios.items():
        encontrou = any(k in texto_completo.lower() for k in keywords)
        if not encontrou:
            analise["alertas"].append(f"⚠️ **{item}** não foi encontrado explicitamente.")
            analise["sugestoes"].append(f"Solicitar ao fornecedor que inclua a informação de **{item}**.")

    # 4. VERIFICAÇÃO DE DATAS (Inconsistência Temporal)
    anos_encontrados = re.findall(r'202[0-9]', texto_completo)
    if anos_encontrados:
        ano_atual = pd.Timestamp.now().year
        anos_int = [int(a) for a in anos_encontrados]
        if any(a < (ano_atual - 1) for a in anos_int):
            analise["alertas"].append(f"🚨 Atenção: Encontrei menção a anos antigos ({set(anos_int)}). Verifique se a proposta não é antiga.")

    return analise

# ==================================================
# 🧹 FUNÇÃO DE LIMPEZA DE TABELAS
# ==================================================
def limpar_df(df):
    # Remove linhas totalmente vazias
    df = df.dropna(how='all')
    # Remove colunas totalmente vazias
    df = df.dropna(axis=1, how='all')
    # Tenta definir cabeçalho
    if not df.empty:
        # Se a primeira linha tiver muitos 'None', tentamos renomear
        df.columns = [f"{str(c).strip() if c else f'Col_{i}'}" for i, c in enumerate(df.columns)]
    return df

# ==================================================
# 🖥️ INTERFACE
# ==================================================
st.title("🧐 Auditor de Propostas e Contratos")
st.markdown("Análise automática de escopo, materiais e inconsistências contratuais.")

arquivo = st.file_uploader("Carregue o PDF (Orçamento/Contrato)", type=["pdf"])

if arquivo:
    st.divider()
    with st.spinner("O Auditor está lendo o documento..."):
        try:
            texto_full = ""
            tabelas_full = []
            
            with pdfplumber.open(arquivo) as pdf:
                for page in pdf.pages:
                    # Texto
                    texto_full += (page.extract_text() or "") + "\n"
                    # Tabelas
                    tabs = page.extract_tables()
                    for t in tabs:
                        df = pd.DataFrame(t)
                        df_limpo = limpar_df(df)
                        if len(df_limpo) > 1: # Só aceita tabelas com dados
                            # Pega a 1ª linha como header
                            new_header = df_limpo.iloc[0] 
                            df_limpo = df_limpo[1:] 
                            df_limpo.columns = new_header 
                            tabelas_full.append(df_limpo)

            # --- RODA A ANÁLISE ---
            resultado = analisar_texto_inteligente(texto_full)

            # --- EXIBIÇÃO EM DASHBOARD ---
            
            # 1. CABEÇALHO RESUMO
            st.markdown(f"### 📄 Resumo: {resultado['resumo']}")
            
            col_a, col_b = st.columns([1, 1])
            
            # 2. ESCOPO DETALHADO (Lado Esquerdo)
            with col_a:
                st.subheader("🔍 Escopo Identificado")
                with st.container(border=True):
                    if resultado["escopo_detectado"]:
                        for linha in resultado["escopo_detectado"]:
                            if "📌" in linha:
                                st.markdown(f"**{linha}**")
                            else:
                                st.write(linha)
                    else:
                        st.warning("Não consegui isolar o texto do escopo.")

            # 3. ALERTA DE INCONSISTÊNCIAS (Lado Direito)
            with col_b:
                st.subheader("🚨 Auditoria & Riscos")
                with st.container(border=True):
                    if resultado["alertas"]:
                        for alerta in resultado["alertas"]:
                            st.error(alerta)
                    else:
                        st.success("✅ O documento parece conter todas as cláusulas padrão.")

                    if resultado["sugestoes"]:
                        st.markdown("---")
                        st.markdown("**💡 Sugestões de melhoria:**")
                        for sug in resultado["sugestoes"]:
                            st.info(sug)

            st.divider()

            # 4. LISTAS DE MATERIAIS (TABELAS)
            st.subheader(f"📦 Listas de Materiais / Quantitativos ({len(tabelas_full)} encontradas)")
            
            if tabelas_full:
                for i, df in enumerate(tabelas_full):
                    with st.expander(f"📋 Lista {i+1} (Clique para ver)", expanded=True):
                        st.dataframe(df, use_container_width=True)
                        csv = df.to_csv(index=False).encode('utf-8')
                        st.download_button(f"📥 Baixar Lista {i+1}", csv, "lista.csv", "text/csv")
            else:
                st.info("Nenhuma tabela de materiais foi detectada no formato padrão.")

        except Exception as e:
            st.error(f"Erro na leitura: {e}")
