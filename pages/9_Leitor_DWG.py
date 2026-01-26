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
st.set_page_config(page_title="Leitor CAD Pro", page_icon="🏗️", layout="wide")

# ==================================================
# 🔑 CONFIGURAÇÃO (SIDEBAR)
# ==================================================
with st.sidebar:
    st.header("🧠 Configuração da IA")
    api_key = st.text_input("Sua API Key (OpenAI):", type="password")
    
    if api_key:
        openai.api_key = api_key
        st.success("✅ IA Pronta para Análise")
    else:
        st.warning("⚠️ Insira a chave para ativar a análise inteligente.")

# ==================================================
# 🧠 CÉREBRO DA IA (MODO JSON ESTRUTURADO)
# ==================================================
def processar_com_inteligencia(texto_sujo):
    if not api_key: return None

    # O segredo está aqui: Forçamos a IA a agir como um Orçamentista Sênior
    prompt_sistema = """
    Você é um Orçamentista Sênior de Engenharia (MEP - Mecânica, Elétrica, Hidráulica).
    Sua tarefa é analisar o texto bruto extraído de um arquivo DXF e transformá-lo em dados estruturados.
    
    O texto contém muito lixo (cotas, layers). Ignore isso. Foque nas especificações.
    
    SAÍDA OBRIGATÓRIA: Responda APENAS um JSON válido com a seguinte estrutura:
    {
        "resumo_executivo": "Breve descrição do que é este projeto (ex: Planta de Dutos do 2º andar).",
        "disciplina": "Qual a disciplina principal? (Elétrica, Hidráulica, AVAC, Civil)",
        "lista_materiais": [
            {"item": "Nome do item (ex: Tubo Cobre 1/2)", "detalhe": "Especificação técnica", "unidade": "m/pç/kg (estime se possível)"}
        ],
        "pontos_atencao": [
            "Lista de avisos importantes encontrados (ex: Notas de 'Não cotar', 'Verificar em obra', normas antigas)"
        ],
        "cliente_obra": "Nome do cliente ou obra se encontrar no carimbo."
    }
    """

    try:
        response = openai.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": prompt_sistema},
                {"role": "user", "content": f"Analise este texto cru e extraia o JSON:\n\n{texto_sujo[:25000]}"} 
            ],
            temperature=0.1, # Muito baixo para garantir que o JSON venha perfeito
            response_format={"type": "json_object"} # Força saída JSON
        )
        return json.loads(response.choices[0].message.content)
    except Exception as e:
        return {"erro": str(e)}

# ==================================================
# 🔧 FUNÇÕES AUXILIARES
# ==================================================
def limpar_texto_cad(lista_textos):
    """Limpeza pesada para economizar tokens e ajudar a IA"""
    texto_limpo = []
    ignorar = ["LAYER", "COTAS", "VIEWPORT", "STANDARD", "ISO-25", "BYLAYER"]
    
    for item in lista_textos:
        t = str(item).strip()
        # Remove números sozinhos (cotas), textos curtos ou palavras de sistema CAD
        if len(t) < 4 or t.replace('.', '', 1).isdigit() or any(x in t.upper() for x in ignorar):
            continue
        texto_limpo.append(t)
    
    # Remove duplicatas mantendo ordem
    return "\n".join(list(dict.fromkeys(texto_limpo)))

def salvar_temp(arquivo):
    with tempfile.NamedTemporaryFile(delete=False, suffix=".dxf") as tmp:
        tmp.write(arquivo.getbuffer())
        return tmp.name

# ==================================================
# 🖥️ INTERFACE PRINCIPAL
# ==================================================
st.title("🏗️ Extrator de Projetos CAD (IA Sênior)")
st.markdown("Transforma a 'bagunça' do DXF em **Listas de Materiais** e **Relatórios de Engenharia**.")

arquivo_cad = st.file_uploader("Arraste o DXF aqui", type=["dxf"])

if arquivo_cad:
    st.divider()
    path_temp = salvar_temp(arquivo_cad)

    try:
        # Leitura do Arquivo
        try:
            doc = ezdxf.readfile(path_temp)
        except:
            doc, auditor = recover.readfile(path_temp)

        if doc:
            msp = doc.modelspace()
            
            # 1. Extração
            textos_crus = []
            with st.spinner("Lendo vetores e textos do CAD..."):
                for entity in msp.query('TEXT MTEXT'):
                    if entity.dxf.text: textos_crus.append(entity.dxf.text)
            
            texto_pronto = limpar_texto_cad(textos_crus)

            # 2. Interface de Resultados
            col1, col2 = st.columns([1, 1.5])

            with col1:
                st.subheader("📋 Dados Brutos")
                st.info(f"{len(texto_pronto.splitlines())} linhas relevantes encontradas.")
                with st.expander("Ver texto extraído (Debug)"):
                    st.text_area("", texto_pronto, height=300)

            with col2:
                st.subheader("🤖 Análise Inteligente")
                
                if not api_key:
                    st.warning("👈 Insira sua API Key na barra lateral para gerar o relatório.")
                else:
                    if st.button("🚀 Gerar Relatório de Engenharia", type="primary"):
                        with st.spinner("O Engenheiro IA está analisando o projeto..."):
                            dados = processar_com_inteligencia(texto_pronto)
                            
                            if "erro" in dados:
                                st.error(f"Erro na IA: {dados['erro']}")
                            else:
                                # --- EXIBIÇÃO PROFISSIONAL ---
                                
                                # Cabeçalho
                                st.success("Análise Concluída!")
                                c_a, c_b = st.columns(2)
                                c_a.metric("Disciplina", dados.get("disciplina", "Geral"))
                                c_b.metric("Cliente/Obra", dados.get("cliente_obra", "Não detectado"))
                                
                                st.markdown(f"**Resumo:** {dados.get('resumo_executivo')}")
                                
                                st.divider()
                                
                                # Abas de Detalhe
                                tab_mat, tab_risco = st.tabs(["📦 Lista de Materiais (Estimada)", "🚨 Pontos de Atenção"])
                                
                                with tab_mat:
                                    materiais = dados.get("lista_materiais", [])
                                    if materiais:
                                        df_mat = pd.DataFrame(materiais)
                                        st.dataframe(df_mat, use_container_width=True)
                                        
                                        # Download Excel
                                        csv = df_mat.to_csv(index=False).encode('utf-8')
                                        st.download_button("📥 Baixar Lista (Excel/CSV)", csv, "materiais_cad.csv", "text/csv")
                                    else:
                                        st.info("Nenhuma especificação de material clara encontrada.")
                                
                                with tab_risco:
                                    riscos = dados.get("pontos_atencao", [])
                                    if riscos:
                                        for r in riscos:
                                            st.warning(f"⚠️ {r}")
                                    else:
                                        st.success("Nenhum ponto de atenção crítico detectado no texto.")

    except Exception as e:
        st.error(f"Erro ao processar: {e}")
    finally:
        if os.path.exists(path_temp): os.remove(path_temp)

else:
    c1, c2, c3 = st.columns(3)
    with c1: st.info("Use arquivos **.DXF** (Salvar Como > DXF 2010)")
    with c2: st.info("A IA ignora cotas e foca em **Especificações**.")
    with c3: st.info("Gera lista de materiais exportável para **Excel**.")
