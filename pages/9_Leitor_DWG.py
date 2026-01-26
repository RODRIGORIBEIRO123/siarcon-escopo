import streamlit as st
import ezdxf
from ezdxf import recover
import pandas as pd
import os
import tempfile
import openai

# Configuração da Página
st.set_page_config(page_title="Leitor CAD com IA", page_icon="🧠", layout="wide")

# ==================================================
# 🔑 CONFIGURAÇÃO DA IA (BARRA LATERAL)
# ==================================================
with st.sidebar:
    st.header("🧠 Inteligência Artificial")
    api_key = st.text_input("Insira sua API Key (OpenAI):", type="password", help="Necessário para organizar a bagunça do CAD.")
    
    if api_key:
        openai.api_key = api_key
        st.success("IA Conectada!")
    else:
        st.warning("Sem a chave, faremos apenas a leitura básica (bagunçada).")

# ==================================================
# 🧠 CÉREBRO DA IA
# ==================================================
def processar_texto_com_ia(texto_sujo):
    """Envia a 'sopa de letrinhas' do CAD para o GPT-4 organizar."""
    if not api_key:
        return "⚠️ Erro: API Key não configurada."

    prompt_sistema = """
    Você é um Engenheiro Sênior Especialista em Orçamentos e Projetos (HVAC, Elétrica, Hidráulica).
    Sua missão é analisar um texto desorganizado extraído de um arquivo CAD (DXF) e estruturá-lo.
    
    O texto contém muito 'lixo' (cotas, layers, números soltos). IGNORE o lixo.
    Foque em encontrar:
    1. ESCOPO: Do que se trata o projeto? (Dutos, Elétrica, etc).
    2. CLIENTE/OBRA: Se houver menção em carimbos.
    3. LISTA DE MATERIAIS: Extraia tudo que parece especificação técnica (Ex: 'Tubo Cobre 1/2"', 'Chapa #26', 'Disjuntor 50A').
    4. NOTAS TÉCNICAS: Avisos importantes (Ex: 'Solda foscoper', 'Isolamento 25mm').

    Saída OBRIGATÓRIA em Markdown limpo. Seja direto. Se não achar algo, diga 'Não detectado'.
    """

    try:
        response = openai.chat.completions.create(
            model="gpt-4o", # O modelo mais inteligente disponível
            messages=[
                {"role": "system", "content": prompt_sistema},
                {"role": "user", "content": f"Analise este texto cru do CAD:\n\n{texto_sujo[:15000]}"} # Limite de caracteres para não estourar tokens
            ],
            temperature=0.2 # Baixa criatividade (queremos precisão)
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"Erro na IA: {e}"

# ==================================================
# 🔧 FUNÇÕES DE CAD
# ==================================================
def salvar_temp(arquivo):
    sulfixo = ".dxf"
    with tempfile.NamedTemporaryFile(delete=False, suffix=sulfixo) as tmp:
        tmp.write(arquivo.getbuffer())
        return tmp.name

def limpar_texto_cad(lista_textos):
    """Remove lixo óbvio (números sozinhos, textos de 1 letra) antes de mandar pra IA"""
    texto_limpo = []
    for item in lista_textos:
        t = str(item).strip()
        # Remove números puros (cotas) ex: "300", "5.4"
        if t.replace('.', '', 1).isdigit():
            continue
        # Remove textos muito curtos (nomes de eixos A, B, C)
        if len(t) < 3:
            continue
        texto_limpo.append(t)
    return "\n".join(set(texto_limpo)) # Remove duplicatas

# ==================================================
# 🖥️ INTERFACE PRINCIPAL
# ==================================================
st.title("🧠 Leitor de Projetos CAD (IA Powered)")
st.markdown("Extração de dados de **.DXF** utilizando GPT-4 para estruturar as informações.")

arquivo_cad = st.file_uploader("Arraste seu arquivo .DXF aqui", type=["dxf"])

if arquivo_cad:
    st.divider()
    path_temp = salvar_temp(arquivo_cad)

    try:
        # Tenta ler o DXF
        try:
            doc = ezdxf.readfile(path_temp)
        except:
            doc, auditor = recover.readfile(path_temp)

        if doc:
            msp = doc.modelspace()
            
            # 1. EXTRAÇÃO DO TEXTO BRUTO
            textos_crus = []
            with st.spinner("Extraindo texto bruto do desenho..."):
                for entity in msp.query('TEXT MTEXT'):
                    if entity.dxf.text:
                        textos_crus.append(entity.dxf.text)
            
            # 2. LIMPEZA INICIAL
            texto_compilado = limpar_texto_cad(textos_crus)
            
            col_esq, col_dir = st.columns(2)

            # LADO ESQUERDO: TEXTO EXTRAÍDO (DEBUG)
            with col_esq:
                st.subheader("📝 Texto Extraído (Bruto)")
                st.caption(f"Encontrei {len(textos_crus)} objetos de texto. Após limpeza: {len(texto_compilado.splitlines())} linhas.")
                st.text_area("Prévia do conteúdo:", texto_compilado, height=400)

            # LADO DIREITO: ANÁLISE DA IA
            with col_dir:
                st.subheader("🤖 Análise da IA (Estruturada)")
                
                if api_key:
                    if st.button("🚀 Processar com IA", type="primary"):
                        if not texto_compilado:
                            st.warning("O arquivo parece não ter textos legíveis (pode ser um bloco explodido ou imagem).")
                        else:
                            with st.spinner("A IA está lendo o projeto e organizando os dados..."):
                                relatorio = processar_texto_com_ia(texto_compilado)
                                st.markdown(relatorio)
                                
                                # Botão para baixar o relatório
                                st.download_button("📥 Baixar Relatório", relatorio, "relatorio_cad.md")
                else:
                    st.info("👈 Insira sua API Key na barra lateral para ativar a Inteligência Artificial.")
                    st.warning("Sem a IA, você só consegue ver o texto bruto ao lado.")

    except Exception as e:
        st.error(f"Erro ao ler arquivo: {e}")
    
    finally:
        if os.path.exists(path_temp): os.remove(path_temp)

else:
    c1, c2 = st.columns(2)
    with c1: st.info("💡 **Como funciona:** O Python extrai todo texto solto do desenho.")
    with c2: st.info("💡 **Onde a IA entra:** Ela pega esse texto solto e descobre o que é Material, o que é Cliente e o que é Lixo.")
