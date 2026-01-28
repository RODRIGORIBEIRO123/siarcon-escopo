import streamlit as st
import fitz  # PyMuPDF
from openai import OpenAI
import base64

# --- 🔒 BLOCO DE SEGURANÇA ---
if 'logado' not in st.session_state or not st.session_state['logado']:
    st.warning("🔒 Acesso negado. Faça login no Dashboard.")
    st.stop()

st.set_page_config(page_title="Leitor IA (Visão)", page_icon="👁️", layout="wide")

st.title("👁️ Levantamento de Dutos com IA (Visão)")
st.markdown("""
Esta ferramenta usa **Visão Computacional** (GPT-4o). Ela 'olha' para a página do projeto 
como um engenheiro humano faria, identificando tabelas de materiais e especificações 
que leitores de texto comuns não conseguem processar.
""")

# --- FUNÇÕES AUXILIARES ---

def pdf_page_to_base64(pdf_file, page_number):
    """Converte uma página específica do PDF em imagem Base64 para a IA ver."""
    doc = fitz.open(stream=pdf_file.read(), filetype="pdf")
    page = doc.load_page(page_number)
    pix = page.get_pixmap(matrix=fitz.Matrix(2, 2)) # Zoom 2x para melhor leitura
    img_data = pix.tobytes("png")
    return base64.b64encode(img_data).decode('utf-8')

def analisar_imagem_com_ia(base64_image):
    if "openai" not in st.secrets:
        st.error("🚨 Chave OpenAI não configurada.")
        return None
    
    client = OpenAI(api_key=st.secrets["openai"]["api_key"])
    
    prompt = """
    Você é um Engenheiro de Orçamentos Especialista em AVAC (Dutos de Ar Condicionado).
    Analise esta imagem técnica (que pode ser uma planta, um memorial ou uma planilha).
    
    SEU OBJETIVO: Extrair o Levantamento de Materiais de Dutos.
    
    Procure visualmente por:
    1. Tabelas de quantidades de dutos (M2 ou Kg) por material (Galvanizado, Inox, MPU).
    2. Especificações de espessuras de chapa (Bitolas #26, #24, #22, etc.).
    3. Isolamento Térmico (Espessura, Tipo, M2).
    4. Acessórios (Dampers, Grelhas, Difusores - se houver lista).
    
    SAÍDA ESPERADA (Em Markdown):
    - Crie uma tabela organizada com: Item | Descrição Técnica | Unidade | Quantidade Estimada.
    - Se a imagem estiver ruim ou não tiver dados, avise.
    - Seja preciso com os números.
    """
    
    try:
        response = client.chat.completions.create(
            model="gpt-4o", # Modelo com visão
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/png;base64,{base64_image}"
                            },
                        },
                    ],
                }
            ],
            max_tokens=2000,
            temperature=0.1 # Baixa criatividade para focar em precisão
        )
        return response.choices[0].message.content
    except Exception as e:
        st.error(f"Erro na IA: {e}")
        return None

# --- INTERFACE ---
uploaded_file = st.file_uploader("📂 Carregar PDF (Memorial ou Planta)", type="pdf")

if uploaded_file:
    # Mostra quantas páginas tem
    doc = fitz.open(stream=uploaded_file.read(), filetype="pdf")
    total_paginas = len(doc)
    uploaded_file.seek(0) # Reseta o ponteiro do arquivo
    
    st.info(f"O documento possui {total_paginas} páginas.")
    
    # Seleção da página para analisar (Para economizar custo e ser mais preciso)
    pagina_selecionada = st.number_input("Qual página contém a tabela/lista de dutos?", min_value=1, max_value=total_paginas, value=1)
    
    if st.button("🚀 Analisar Página Selecionada", type="primary"):
        with st.spinner("👀 A IA está 'lendo' a imagem da página... Aguarde."):
            # 1. Converte a página escolhida em imagem
            imagem_b64 = pdf_page_to_base64(uploaded_file, pagina_selecionada - 1)
            uploaded_file.seek(0) # Reseta arquivo
            
            # 2. Mostra a imagem para o usuário conferir
            st.image(base64.b64decode(imagem_b64), caption=f"Página {pagina_selecionada} enviada para análise", use_column_width=True)
            
            # 3. Envia para o GPT-4o Vision
            resultado = analisar_imagem_com_ia(imagem_b64)
            
        if resultado:
            st.divider()
            st.subheader("📋 Levantamento Extraído")
            st.markdown(resultado)
            st.download_button("📥 Baixar Levantamento", resultado, f"levantamento_pag_{pagina_selecionada}.txt")

st.markdown("---")
st.caption("Dica: Para melhor precisão, selecione a página exata onde está a tabela de resumo ou memorial de cálculo dos dutos.")
