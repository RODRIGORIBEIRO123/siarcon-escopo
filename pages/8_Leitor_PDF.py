import streamlit as st
import pdfplumber
import pandas as pd
import re
from io import BytesIO

st.set_page_config(page_title="Leitor Turbo PDF", page_icon="⚡", layout="wide")

# ==================================================
# ⚙️ BARRA LATERAL DE AJUSTES (O SEGREDO DA ROBUSTEZ)
# ==================================================
with st.sidebar:
    st.header("⚙️ Ajustes de Leitura")
    st.info("Se a tabela vier quebrada, mexa aqui:")
    
    # Escolha do método de extração
    metodo = st.radio(
        "Método de Detecção:",
        ("lattice", "stream"),
        index=0,
        help="'Lattice' = Para tabelas com linhas desenhadas.\n'Stream' = Para tabelas separadas por espaços em branco."
    )
    
    # Sensibilidade (Snap Tolerance)
    tolerancia = st.slider(
        "Tolerância de Alinhamento (x-tolerance)",
        min_value=1, max_value=10, value=3,
        help="Aumente se as colunas estiverem sendo quebradas erradas."
    )

# ==================================================
# 🧠 FUNÇÕES INTELIGENTES
# ==================================================
def limpar_cabecalho(lista_colunas):
    """Renomeia colunas vazias ou duplicadas"""
    colunas_limpas = []
    contagem = {}
    for i, col in enumerate(lista_colunas):
        nome_base = str(col).strip() if col and str(col).strip() != "" else f"Dado_{i+1}"
        # Remove quebras de linha no nome da coluna
        nome_base = nome_base.replace('\n', ' ')
        
        if nome_base in contagem:
            contagem[nome_base] += 1
            novo_nome = f"{nome_base}_{contagem[nome_base]}"
        else:
            contagem[nome_base] = 0
            novo_nome = nome_base
        colunas_limpas.append(novo_nome)
    return colunas_limpas

def minerar_metadados(texto_completo):
    """Procura informações vitais fora das tabelas"""
    info = {}
    # Expressões Regulares simples para tentar achar padrões
    # Procura por "Cliente:" seguido de qualquer coisa até o fim da linha
    match_cliente = re.search(r'(?i)(cliente|tomador|destinatário)[:\s]+(.+)', texto_completo)
    if match_cliente: info['Possível Cliente'] = match_cliente.group(2).strip()

    match_obra = re.search(r'(?i)(obra|projeto|referência)[:\s]+(.+)', texto_completo)
    if match_obra: info['Possível Obra'] = match_obra.group(2).strip()

    # Tenta achar valores monetários grandes (Totais)
    valores = re.findall(r'R\$\s?[\d\.,]+', texto_completo)
    if valores:
        info['Valores Encontrados (R$)'] = ", ".join(valores[-3:]) # Pega os últimos 3 (geralmente totais estão no fim)
        
    return info

# ==================================================
# 🖥️ APLICAÇÃO PRINCIPAL
# ==================================================
st.title("⚡ Leitor Turbo de Arquivos (PDF)")
st.markdown("Extração avançada de tabelas e metadados.")

arquivo = st.file_uploader("Arraste o PDF aqui", type=["pdf"])

if arquivo:
    st.divider()
    with st.spinner("Processando com inteligência aumentada..."):
        try:
            with pdfplumber.open(arquivo) as pdf:
                tabelas_finais = []
                texto_geral = ""
                
                # Barra de progresso
                bar = st.progress(0)
                total_p = len(pdf.pages)
                
                for i, page in enumerate(pdf.pages):
                    # 1. Extração de Texto Puro (para mineração)
                    texto_geral += (page.extract_text() or "") + "\n"
                    
                    # 2. Extração de Tabelas com Configuração do Usuário
                    # Aqui aplicamos as configs da barra lateral
                    tabelas = page.extract_tables({
                        "vertical_strategy": "lines" if metodo == "lattice" else "text",
                        "horizontal_strategy": "lines" if metodo == "lattice" else "text",
                        "snap_tolerance": tolerancia,
                    })
                    
                    for tab in tabelas:
                        df = pd.DataFrame(tab)
                        # Limpeza: Remove linhas que estão 100% vazias
                        df = df.dropna(how='all')
                        
                        if not df.empty and len(df) > 1:
                            # Tratamento de Cabeçalho
                            cols = df.iloc[0].tolist()
                            df.columns = limpar_cabecalho(cols)
                            df = df[1:].reset_index(drop=True)
                            tabelas_finais.append(df)
                    
                    bar.progress((i + 1) / total_p)

            # --- RESULTADOS ---
            
            # BLOCO 1: O que ele achou fora da tabela (Cabeçalho/Rodapé)
            metadados = minerar_metadados(texto_geral)
            if metadados:
                with st.container(border=True):
                    st.subheader("🕵️‍♂️ Informações Detectadas (Fora da Tabela)")
                    c_meta = st.columns(len(metadados))
                    for idx, (chave, valor) in enumerate(metadados.items()):
                        c_meta[idx].metric(chave, valor if len(valor) < 30 else f"{valor[:30]}...")

            # BLOCO 2: Tabelas
            tab_vis, tab_txt = st.tabs(["📊 Tabelas Estruturadas", "📝 Texto Completo (Debug)"])
            
            with tab_vis:
                if tabelas_finais:
                    st.success(f"Sucesso! {len(tabelas_finais)} tabelas extraídas.")
                    for j, df in enumerate(tabelas_finais):
                        with st.expander(f"Tabela {j+1} ({len(df)} linhas)", expanded=(j==0)):
                            st.dataframe(df, use_container_width=True)
                            
                            # Download
                            csv = df.to_csv(index=False).encode('utf-8')
                            st.download_button(f"📥 Baixar CSV", csv, f"tabela_{j+1}.csv", "text/csv")
                else:
                    st.warning("⚠️ Nenhuma tabela perfeita encontrada.")
                    st.markdown("**Tente mudar na Barra Lateral:**\n1. Troque de 'Lattice' para 'Stream'\n2. Aumente a tolerância.")

            with tab_txt:
                st.text_area("Tudo que consegui ler:", texto_geral, height=400)

        except Exception as e:
            st.error(f"Erro crítico
