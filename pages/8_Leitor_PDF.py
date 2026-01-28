import streamlit as st
import pdfplumber
from openai import OpenAI

st.set_page_config(page_title="Leitor IA | SIARCON", page_icon="🧠")

st.title("🧠 Leitor de PDF com Inteligência Artificial")
st.markdown("Carregue um memorial ou escopo técnico e deixe a IA extrair os dados e sugerir melhorias.")

# --- CONFIGURAÇÃO DA IA ---
def consultar_ia(texto_pdf):
    # Verifica se a chave existe
    if "openai" not in st.secrets:
        st.error("🚨 Chave da OpenAI não configurada nos Secrets!")
        return None
    
    client = OpenAI(api_key=st.secrets["openai"]["api_key"])
    
    prompt_sistema = """
    Você é um Engenheiro Sênior especialista em orçamentos e escopos técnicos (HVAC, Elétrica, Hidráulica).
    Sua missão é ler o texto técnico fornecido e gerar um relatório estruturado com:
    1. RESUMO: O que é a obra em poucas linhas.
    2. LISTA DE MATERIAIS: Extraia todos os itens quantificáveis em formato de lista.
    3. PONTOS DE ATENÇÃO: Identifique riscos, erros técnicos ou itens que parecem estar faltando no escopo.
    """

    try:
        response = client.chat.completions.create(
            model="gpt-4o", # Ou "gpt-3.5-turbo" se preferir economizar
            messages=[
                {"role": "system", "content": prompt_sistema},
                {"role": "user", "content": f"Analise este documento técnico:\n\n{texto_pdf[:15000]}"} # Limite de caracteres para não estourar
            ],
            temperature=0.3
        )
        return response.choices[0].message.content
    except Exception as e:
        st.error(f"Erro na IA: {e}")
        return None

# --- INTERFACE ---
uploaded_file = st.file_uploader("Carregar PDF Técnico", type="pdf")

if uploaded_file is not None:
    # 1. EXTRAÇÃO DO TEXTO
    with st.spinner("Lendo arquivo PDF..."):
        texto_completo = ""
        with pdfplumber.open(uploaded_file) as pdf:
            for page in pdf.pages:
                texto_completo += page.extract_text() + "\n"
        
    st.success(f"PDF Lido! Total de caracteres: {len(texto_completo)}")
    
    with st.expander("Ver texto bruto extraído"):
        st.text_area("Conteúdo", texto_completo, height=200)

    # 2. ANÁLISE DA IA
    st.divider()
    st.subheader("🤖 Análise Inteligente")
    
    if st.button("Gerar Análise Técnica (IA)", type="primary"):
        if len(texto_completo) < 50:
            st.warning("O PDF parece vazio ou é uma imagem escaneada. A IA precisa de texto selecionável.")
        else:
            with st.spinner("A IA está analisando o projeto... (Isso pode levar alguns segundos)"):
                analise = consultar_ia(texto_completo)
                
            if analise:
                st.markdown("### 📋 Relatório da Engenharia (IA)")
                st.markdown(analise)
                
                # Botão para baixar a análise
                st.download_button("📥 Baixar Relatório IA", analise, "relatorio_ia.txt")
