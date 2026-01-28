import streamlit as st
import ezdxf
from openai import OpenAI
import pandas as pd
import io

# --- 🔒 BLOCO DE SEGURANÇA ---
if 'logado' not in st.session_state or not st.session_state['logado']:
    st.warning("🔒 Acesso negado. Faça login no Dashboard.")
    st.stop()

st.set_page_config(page_title="Leitor DXF (Tags)", page_icon="📐", layout="wide")

st.title("📐 Leitor de Projetos CAD (DXF)")
st.markdown("""
**Atenção:** Esta ferramenta foca na leitura das **ETIQUETAS (TAGS)** de texto do projeto.
Ela é ideal para listar quais bitolas/medidas existem no desenho.

1. No AutoCAD, salve seu projeto como **.DXF** (versão 2010 ou superior).
2. Faça o upload abaixo.
""")

# --- FUNÇÃO DE EXTRAÇÃO DE TEXTO DO DXF ---
def extrair_textos_dxf(dxf_file):
    try:
        # Carrega o DXF da memória
        doc = ezdxf.read(dxf_file)
        msp = doc.modelspace()
        
        textos_encontrados = []
        
        # Procura por TEXT e MTEXT (Textos simples e múltiplos)
        for entity in msp.query('TEXT MTEXT'):
            # Limpa caracteres estranhos de formatação do AutoCAD
            conteudo = entity.dxf.text if entity.dxftype() == 'TEXT' else entity.text
            # Remove códigos de formatação comuns em MTEXT (ex: \A1;)
            if conteudo:
                textos_encontrados.append(conteudo.strip())
                
        return textos_encontrados
    except Exception as e:
        st.error(f"Erro ao ler DXF: {e}")
        return []

# --- FUNÇÃO IA ---
def analisar_textos_com_ia(lista_textos):
    if "openai" not in st.secrets:
        st.error("🚨 Chave OpenAI não configurada.")
        return None
    
    client = OpenAI(api_key=st.secrets["openai"]["api_key"])
    
    # Transforma a lista em uma string única para o prompt (limitando tamanho para não estourar)
    texto_bruto = "\n".join(lista_textos[:3000]) # Limite de segurança
    
    prompt = """
    Você é um Engenheiro de Orçamentos de HVAC.
    Abaixo está uma lista de textos extraídos de um projeto CAD (DXF).
    A lista está suja (contém nomes de salas, cotas, arquitetura, etc.).
    
    SEU OBJETIVO:
    1. Filtrar APENAS as textos que parecem dimensões de dutos (ex: "300x200", "500x400", "ø200", "12x12").
    2. Contar a ocorrência de cada bitola encontrada.
    3. Ignorar cotas de parede, níveis (h=280), nomes de ambientes.
    
    SAÍDA ESPERADA (Markdown):
    - Tabela com: Bitola Identificada | Quantidade de Tags Encontradas | Tipo Provável (Retangular/Circular).
    - Nota: Avise que isso é uma contagem de TAGS, não a metragem linear exata.
    """
    
    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": f"Analise esta lista de textos do CAD:\n\n{texto_bruto}"}
            ],
            temperature=0.1
        )
        return response.choices[0].message.content
    except Exception as e:
        st.error(f"Erro na IA: {e}")
        return None

# --- INTERFACE ---
uploaded_dxf = st.file_uploader("📂 Carregar Arquivo .DXF", type=["dxf"])

if uploaded_dxf:
    # Hack para ler o arquivo em memória para o ezdxf
    # O Streamlit entrega um BytesIO, mas o ezdxf prefere string ou stream de texto
    with st.spinner("Extraindo textos do CAD..."):
        # Precisamos ler como string (utf-8 ou latin-1 dependendo do CAD)
        try:
            # Tenta converter stream para texto para o ezdxf ler
            content = uploaded_dxf.getvalue().decode("cp1252", errors="ignore") # Codificação comum de Windows/AutoCAD
            stream = io.StringIO(content)
            lista_textos = extrair_textos_dxf(stream)
            
        except Exception as e:
            st.error(f"Erro na codificação do arquivo: {e}")
            lista_textos = []

    if lista_textos:
        st.success(f"Foram encontrados {len(lista_textos)} elementos de texto no desenho.")
        
        with st.expander("Ver lista bruta de textos extraídos (Debug)"):
            st.write(lista_textos)
            
        if st.button("🚀 Filtrar Dutos com IA", type="primary"):
            with st.spinner("A IA está separando o que é duto do que é arquitetura..."):
                resultado = analisar_textos_com_ia(lista_textos)
                
            if resultado:
                st.divider()
                st.subheader("📊 Resultado da Análise")
                st.markdown(resultado)
                st.warning("⚠️ Nota: Esta ferramenta conta quantas vezes a ETIQUETA aparece. Ela não calcula o comprimento do duto (metros lineares), pois isso depende da geometria da linha.")
    else:
        st.warning("Nenhum texto legível encontrado. Verifique se o arquivo está em DXF e se os textos não estão explodidos em linhas.")
