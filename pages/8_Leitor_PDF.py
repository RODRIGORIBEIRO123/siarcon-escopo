import streamlit as st
import pdfplumber
import pandas as pd
import io

st.set_page_config(page_title="Leitor de Orçamentos", page_icon="📂", layout="wide")

st.title("📂 Leitor Inteligente de Arquivos (PDF)")
st.markdown("Use esta ferramenta para extrair tabelas de orçamentos ou listas de materiais automaticamente.")

# --- FUNÇÃO AUXILIAR PARA CORRIGIR NOMES DUPLICADOS ---
def limpar_cabecalho(lista_colunas):
    """
    Recebe uma lista de colunas (que pode ter None ou nomes repetidos)
    e retorna uma lista única e limpa.
    """
    colunas_limpas = []
    contagem = {}

    for i, col in enumerate(lista_colunas):
        # 1. Trata None ou Vazio
        if col is None or str(col).strip() == "":
            nome_base = f"Coluna_{i+1}" # Cria um nome genérico se estiver vazio
        else:
            nome_base = str(col).strip()

        # 2. Trata Duplicatas (Adiciona um número no final se já existir)
        if nome_base in contagem:
            contagem[nome_base] += 1
            novo_nome = f"{nome_base}_{contagem[nome_base]}"
        else:
            contagem[nome_base] = 0
            novo_nome = nome_base

        colunas_limpas.append(novo_nome)

    return colunas_limpas

# --- ÁREA DE UPLOAD ---
arquivo_upload = st.file_uploader("Arraste seu PDF aqui (Orçamentos, Memoriais, etc)", type=["pdf"])

if arquivo_upload:
    st.info(f"Arquivo carregado: {arquivo_upload.name}")
    
    # --- PROCESSAMENTO ---
    with st.spinner("Lendo e processando tabelas..."):
        try:
            with pdfplumber.open(arquivo_upload) as pdf:
                todas_tabelas = []
                texto_completo = ""
                
                progresso = st.progress(0)
                total_paginas = len(pdf.pages)
                
                for i, page in enumerate(pdf.pages):
                    # 1. Extração de Tabelas
                    tabelas_pagina = page.extract_tables()
                    
                    for tabela in tabelas_pagina:
                        # Cria DataFrame bruto primeiro
                        df = pd.DataFrame(tabela)
                        
                        if not df.empty and len(df) > 1:
                            # Pega a primeira linha como cabeçalho bruto
                            cabecalho_bruto = df.iloc[0].tolist()
                            
                            # --- AQUI ESTÁ A CORREÇÃO MÁGICA ---
                            # Limpa os nomes antes de aplicar
                            cabecalho_limpo = limpar_cabecalho(cabecalho_bruto)
                            
                            df.columns = cabecalho_limpo # Aplica nomes únicos
                            df = df[1:] # Remove a primeira linha (que era o header)
                            
                            # Reseta o index para ficar bonito
                            df.reset_index(drop=True, inplace=True)
                            
                            todas_tabelas.append(df)
                    
                    # 2. Extração de Texto
                    texto_completo += (page.extract_text() or "") + "\n"
                    progresso.progress((i + 1) / total_paginas)

            # --- EXIBIÇÃO ---
            st.success("Leitura Concluída!")
            
            tab1, tab2 = st.tabs(["📊 Tabelas Encontradas", "📝 Texto Puro"])
            
            with tab1:
                if todas_tabelas:
                    st.write(f"Encontrei {len(todas_tabelas)} tabelas neste PDF.")
                    
                    for i, df in enumerate(todas_tabelas):
                        with st.expander(f"Tabela {i+1} - {len(df)} linhas (Clique para expandir)", expanded=True):
                            # Mostra a tabela
                            st.dataframe(df, use_container_width=True)
                            
                            # Botão de Download
                            csv = df.to_csv(index=False).encode('utf-8')
                            st.download_button(
                                label=f"📥 Baixar Tabela {i+1} (CSV)",
                                data=csv,
                                file_name=f"tabela_{i+1}.csv",
                                mime="text/csv",
                                key=f"dl_{i}"
                            )
                else:
                    st.warning("Não consegui identificar tabelas estruturadas. Tente ver a aba 'Texto Puro'.")
            
            with tab2:
                st.text_area("Conteúdo do PDF", texto_completo, height=400)
                
        except Exception as e:
            st.error(f"Erro ao processar o arquivo: {e}")

else:
    # Dicas iniciais
    c1, c2, c3 = st.columns(3)
    with c1: st.info("💡 **Dica:** Tabelas com células mescladas podem gerar colunas extras.")
    with c2: st.info("💡 **Dica:** Se o PDF for imagem (escaneado), não funcionará.")
    with c3: st.info("💡 **Dica:** O sistema renomeia colunas vazias automaticamente.")
