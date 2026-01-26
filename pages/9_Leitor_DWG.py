import streamlit as st
import ezdxf
from ezdxf import recover
import pandas as pd
import os
import tempfile
import openai
import json
import re

# Configuração da Página
st.set_page_config(page_title="Leitor CAD Pro V3", page_icon="🏗️", layout="wide")

# ==================================================
# 🔑 CONFIGURAÇÃO
# ==================================================
with st.sidebar:
    st.header("🧠 Configuração da IA")
    api_key = st.text_input("Sua API Key (OpenAI):", type="password")
    if api_key:
        openai.api_key = api_key
        st.success("✅ IA Pronta")

# ==================================================
# 🧠 CÉREBRO DA IA (COM QUANTITATIVOS)
# ==================================================
def processar_com_inteligencia(texto_sujo):
    if not api_key: return None

    prompt_sistema = """
    Você é um Engenheiro de Orçamentos Sênior. 
    Analise o texto desorganizado de um projeto CAD e gere uma Lista de Materiais precisa.

    REGRAS CRITICAS:
    1. Tente identificar QUANTIDADES. Se o texto diz "2 Tubos", a quantidade é 2. Se diz "Tubo", a quantidade é 1.
    2. Separe a UNIDADE (m, pç, vb, kg).
    3. Ignore cotas de parede (ex: 2.50, 1500) que não sejam materiais.
    4. O "item" deve ser curto (ex: "Tubo de Cobre"). O "detalhe" deve ter a especificação (ex: "3/4 com isolamento").

    SAÍDA OBRIGATÓRIA (JSON puro):
    {
        "resumo_executivo": "Descrição resumida do projeto.",
        "disciplina": "Elétrica, Hidráulica ou Mecânica",
        "lista_materiais": [
            {
                "item": "Nome do Material", 
                "detalhe": "Especificação Técnica", 
                "quantidade": 1, 
                "unidade": "pç/m/kg"
            }
        ],
        "pontos_atencao": ["Lista de avisos ou inconsistências"]
    }
    """

    try:
        response = openai.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": prompt_sistema},
                {"role": "user", "content": f"Extraia o quantitativo deste texto:\n\n{texto_sujo[:28000]}"} 
            ],
            temperature=0.1,
            response_format={"type": "json_object"}
        )
        return json.loads(response.choices[0].message.content)
    except Exception as e:
        return {"erro": str(e)}

# ==================================================
# 🔧 FUNÇÕES AUXILIARES
# ==================================================
def limpar_texto_cad(lista_textos):
    texto_limpo = []
    ignorar = ["LAYER", "COTAS", "VIEWPORT", "STANDARD", "ISO", "BYLAYER", "MODEL"]
    
    for item in lista_textos:
        t = str(item).strip()
        # Filtra lixo óbvio, mas mantem números que podem ser quantidades
        if len(t) < 3 or any(x in t.upper() for x in ignorar):
            continue
        texto_limpo.append(t)
    
    return "\n".join(list(dict.fromkeys(texto_limpo)))

def salvar_temp(arquivo):
    with tempfile.NamedTemporaryFile(delete=False, suffix=".dxf") as tmp:
        tmp.write(arquivo.getbuffer())
        return tmp.name

# Função para converter DataFrame para CSV Brasileiro (Excel)
def converter_para_csv_br(df):
    return df.to_csv(sep=';', decimal=',', index=False, encoding='utf-8-sig').encode('utf-8-sig')

# ==================================================
# 🖥️ INTERFACE
# ==================================================
st.title("🏗️ Extrator de Quantitativos (CAD + IA)")
st.markdown("Gera lista de materiais com **Quantidades**, pronta para Excel.")

arquivo_cad = st.file_uploader("Arraste o DXF aqui", type=["dxf"])

if arquivo_cad:
    st.divider()
    path_temp = salvar_temp(arquivo_cad)

    try:
        # Leitura
        try:
            doc = ezdxf.readfile(path_temp)
        except:
            doc, auditor = recover.readfile(path_temp)

        if doc:
            msp = doc.modelspace()
            
            # Extração
            textos_crus = []
            with st.spinner("Lendo projeto..."):
                for entity in msp.query('TEXT MTEXT'):
                    if entity.dxf.text: textos_crus.append(entity.dxf.text)
            
            texto_pronto = limpar_texto_cad(textos_crus)

            # Interface Lado a Lado
            c1, c2 = st.columns([1, 2])

            with c1:
                st.info(f"Texto bruto: {len(texto_pronto)} caracteres.")
                with st.expander("Ver Texto Cru"):
                    st.text_area("", texto_pronto, height=400)

            with c2:
                st.subheader("🤖 Lista de Materiais")
                
                if not api_key:
                    st.warning("Insira a API Key na barra lateral.")
                else:
                    if st.button("🚀 Gerar Lista Quantitativa", type="primary"):
                        with st.spinner("Engenheiro IA trabalhando..."):
                            dados = processar_com_inteligencia(texto_pronto)
                            
                            if "erro" in dados:
                                st.error(f"Erro: {dados['erro']}")
                            else:
                                # Cabeçalho
                                m1, m2, m3 = st.columns(3)
                                m1.metric("Disciplina", dados.get("disciplina", "-"))
                                m2.metric("Total Itens", len(dados.get("lista_materiais", [])))
                                m3.success("Processamento Concluído")
                                
                                st.markdown(f"**Resumo:** {dados.get('resumo_executivo')}")
                                
                                # Tabela Principal
                                materiais = dados.get("lista_materiais", [])
                                if materiais:
                                    df_mat = pd.DataFrame(materiais)
                                    
                                    # Reorganiza colunas para ficar bonito
                                    cols_order = ["quantidade", "unidade", "item", "detalhe"]
                                    # Garante que as colunas existem antes de ordenar
                                    cols_existentes = [c for c in cols_order if c in df_mat.columns]
                                    df_mat = df_mat[cols_existentes]
                                    
                                    st.dataframe(df_mat, use_container_width=True)
                                    
                                    # Botão Download Corrigido para Excel BR
                                    csv_br = converter_para_csv_br(df_mat)
                                    st.download_button(
                                        label="📥 Baixar Excel (CSV Formatado)",
                                        data=csv_br,
                                        file_name="lista_materiais_obra.csv",
                                        mime="text/csv"
                                    )
                                else:
                                    st.warning("A IA não conseguiu identificar materiais claros.")
                                
                                # Alertas
                                if dados.get("pontos_atencao"):
                                    with st.expander("🚨 Pontos de Atenção (Riscos)", expanded=True):
                                        for risco in dados["pontos_atencao"]:
                                            st.write(f"⚠️ {risco}")

    except Exception as e:
        st.error(f"Erro: {e}")
    finally:
        if os.path.exists(path_temp): os.remove(path_temp)
