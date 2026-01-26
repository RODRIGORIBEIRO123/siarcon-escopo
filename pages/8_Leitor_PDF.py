import streamlit as st
import pdfplumber
import pandas as pd
import io

st.set_page_config(page_title="Leitor de Orçamentos", page_icon="📂", layout="wide")

st.title("📂 Leitor Inteligente de Arquivos (PDF)")
st.markdown("Use esta ferramenta para extrair tabelas de orçamentos ou listas de materiais automaticamente.")

# --- ÁREA DE UPLOAD ---
arquivo_upload = st.file_uploader("Arraste seu PDF aqui (Orçamentos, Memoriais, etc)", type=["pdf"])

if arquivo_upload:
    # Mostra detalhes do arquivo
    st.info(f"Arquivo carregado: {arquivo_upload.name}")
    
    # --- PROCESSAMENTO COM PDFPLUMBER ---
    with st.spinner("Lendo o arquivo..."):
        try:
            # Abre o PDF da memória
            with pdfplumber.open(arquivo_upload) as pdf:
                todas_tabelas = []
                texto_completo = ""
                
                # Barra de progresso para PDFs grandes
                progresso = st.progress(0)
                total_paginas = len(pdf.pages)
                
                for i, page in enumerate(pdf.pages):
                    # 1. Extrair Tabelas (O foco principal)
                    tabelas_pagina = page.extract_tables()
                    
                    for tabela in tabelas_pagina:
                        # Limpeza básica: Remove linhas vazias e cria DataFrame
                        df = pd.DataFrame(tabela)
                        # Tenta usar a primeira linha como cabeçalho
                        if not df.empty:
                            df.columns = df.iloc[0] # Define primeira linha como Header
                            df = df[1:] # Remove a primeira linha dos dados
                            todas_tabelas.append(df)
                    
                    # 2. Extrair Texto (Para buscar palavras-chave depois)
                    texto_completo += page.extract_text() + "\n"
                    
                    # Atualiza barra
                    progresso.progress((i + 1) / total_paginas)

            # --- EXIBIÇÃO DOS RESULTADOS ---
            st.success("Leitura Concluída!")
            
            tab1, tab2 = st.tabs(["📊 Tabelas Encontradas", "📝 Texto Puro"])
            
            with tab1:
                if todas_tabelas:
                    st.write(f"Encontrei {len(todas_tabelas)} tabelas neste PDF.")
                    
                    for i, df in enumerate(todas_tabelas):
                        with st.expander(f"Tabela {i+1} (Clique para ver)", expanded=True):
                            st.dataframe(df, use_container_width=True)
                            
                            # Botão para baixar essa tabela específica em Excel
                            # Convertendo para CSV para download rápido
                            csv = df.to_csv(index=False).encode('utf-8')
                            st.download_button(
                                label="📥 Baixar como CSV (Excel)",
                                data=csv,
                                file_name=f"tabela_{i+1}.csv",
                                mime="text/csv",
                                key=f"dl_{i}"
                            )
                else:
                    st.warning("Não encontrei nenhuma tabela estruturada neste PDF. Tente ver a aba 'Texto Puro'.")
            
            with tab2:
                st.text_area("Conteúdo do PDF", texto_completo, height=400)
                
        except Exception as e:
            st.error(f"Erro ao ler o PDF: {e}")

else:
    # Dicas de uso quando não tem arquivo
    c1, c2, c3 = st.columns(3)
    with c1: st.info("💡 **Dica 1:**\nÓtimo para orçamentos que vêm em PDF mas você precisa jogar no Excel.")
    with c2: st.info("💡 **Dica 2:**\nSe o PDF for uma imagem escaneada (foto), este leitor não vai funcionar (precisaremos de OCR).")
    with c3: st.info("💡 **Dica 3:**\nFunciona melhor com arquivos gerados digitalmente (AutoCAD, Excel exportado para PDF).")
