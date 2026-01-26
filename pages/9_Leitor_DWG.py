import streamlit as st
import ezdxf
from ezdxf import recover
import pandas as pd
import os
import tempfile
import openai
import json

# Configuração da Página
st.set_page_config(page_title="Leitor CAD Quantitativo", page_icon="📏", layout="wide")

# ==================================================
# 🔑 GERENCIAMENTO INTELIGENTE DA CHAVE (SECRETS)
# ==================================================
# Tenta pegar a chave do "Cofre" (secrets.toml)
api_key_sistema = st.secrets.get("OPENAI_API_KEY", None)

with st.sidebar:
    st.header("🧠 Configuração")
    
    if api_key_sistema:
        st.success("🔑 Chave de API carregada do sistema com segurança.")
        openai.api_key = api_key_sistema
        api_key = api_key_sistema # Variável para controle
    else:
        # Se não tiver no sistema, pede manual
        api_key_manual = st.text_input("Insira API Key (OpenAI):", type="password")
        if api_key_manual:
            openai.api_key = api_key_manual
            api_key = api_key_manual
            st.success("✅ IA Pronta")
        else:
            api_key = None
            st.warning("⚠️ Configure o 'secrets.toml' para não precisar digitar a senha.")

# ==================================================
# 🧠 CÉREBRO DA IA (FOCADO EM METRAGEM)
# ==================================================
def processar_com_inteligencia(texto_sujo):
    if not api_key: return None

    # Prompt Ajustado para Medição Linear
    prompt_sistema = """
    Você é um Engenheiro de Custos Especialista.
    Analise os textos de um projeto CAD e gere uma Lista de Materiais com foco em QUANTITATIVOS.

    REGRAS DE OURO PARA MEDIÇÃO:
    1. Procure agressivamente por COMPRIMENTOS (m, mts, metros).
    2. Se houver vários itens iguais (ex: vários textos "Duto 30x20"), tente contar quantas vezes aparece.
    3. Se encontrar texto explícito de comprimento (ex: "Tubo Cobre 15m"), use "15" na quantidade e "m" na unidade.
    4. Se for contagem (ex: "Difusor"), use "pç".
    
    IMPORTANTE: Ignore números soltos que pareçam ser cotas de parede (ex: 2.80, 150, 300). Foque no que está perto de nomes de materiais.

    SAÍDA JSON OBRIGATÓRIA:
    {
        "resumo_executivo": "Resumo técnico do projeto.",
        "disciplina": "Elétrica, Hidráulica, Dutos ou Civil",
        "lista_materiais": [
            {
                "item": "Nome Curto (ex: Tubo Cobre 3/4)", 
                "detalhe": "Especificação completa encontrada", 
                "quantidade": 1.0, 
                "unidade": "m/pç/kg/vb"
            }
        ],
        "alertas": ["Avisos sobre itens que parecem faltar medida ou especificação"]
    }
    """

    try:
        response = openai.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": prompt_sistema},
                {"role": "user", "content": f"Extraia quantitativos lineares e unitários deste texto cru:\n\n{texto_sujo[:30000]}"} 
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
    # Ignora lixo de CAD
    ignorar = ["LAYER", "COTAS", "VIEWPORT", "STANDARD", "ISO", "BYLAYER", "MODEL", "A1", "A0", "TITLE"]
    
    for item in lista_textos:
        t = str(item).strip()
        # Filtros: Remove textos muito curtos ou palavras reservadas
        if len(t) < 2 or any(x in t.upper() for x in ignorar):
            continue
        # Remove números que parecem coordenadas sozinhas (ex: 100, 200) mas mantem "100m"
        if t.replace('.', '', 1).isdigit() and len(t) < 4:
            continue
            
        texto_limpo.append(t)
    
    # Mantém duplicatas propositalmente! (Para a IA conseguir contar quantas vezes aparece)
    # Mas limitamos para não estourar o limite de tokens se for gigante
    return "\n".join(texto_limpo[:2000]) 

def salvar_temp(arquivo):
    with tempfile.NamedTemporaryFile(delete=False, suffix=".dxf") as tmp:
        tmp.write(arquivo.getbuffer())
        return tmp.name

def converter_csv_br(df):
    return df.to_csv(sep=';', decimal=',', index=False, encoding='utf-8-sig').encode('utf-8-sig')

# ==================================================
# 🖥️ INTERFACE
# ==================================================
st.title("📏 Extrator de Metragem e Materiais (CAD AI)")
st.markdown("Extração automática de **Metragem Linear (m)** e **Contagem (pç)** via Inteligência Artificial.")

arquivo_cad = st.file_uploader("Arraste o DXF aqui", type=["dxf"])

if arquivo_cad:
    st.divider()
    path_temp = salvar_temp(arquivo_cad)

    try:
        try:
            doc = ezdxf.readfile(path_temp)
        except:
            doc, auditor = recover.readfile(path_temp)

        if doc:
            msp = doc.modelspace()
            
            textos_crus = []
            with st.spinner("Lendo anotações do projeto..."):
                for entity in msp.query('TEXT MTEXT'):
                    if entity.dxf.text: textos_crus.append(entity.dxf.text)
            
            # Aqui mandamos as duplicatas para a IA tentar contar
            texto_pronto = limpar_texto_cad(textos_crus)

            c1, c2 = st.columns([1, 2])

            with c1:
                st.info(f"Elementos de texto lidos: {len(textos_crus)}")
                with st.expander("Ver Texto Bruto (Para conferência)"):
                    st.text_area("", texto_pronto, height=450)

            with c2:
                st.subheader("🤖 Levantamento Quantitativo")
                
                if not api_key:
                    st.error("🔒 Chave API não detectada. Configure o 'secrets.toml' ou insira na barra lateral.")
                else:
                    if st.button("🚀 Calcular Metragens e Itens", type="primary"):
                        with st.spinner("Analisando especificações e somando itens..."):
                            dados = processar_com_inteligencia(texto_pronto)
                            
                            if "erro" in dados:
                                st.error(f"Erro IA: {dados['erro']}")
                            else:
                                st.success("Levantamento Concluído!")
                                st.markdown(f"**Resumo:** {dados.get('resumo_executivo')}")
                                
                                # TABELA DE MATERIAIS
                                materiais = dados.get("lista_materiais", [])
                                if materiais:
                                    df = pd.DataFrame(materiais)
                                    
                                    # Formatação visual
                                    cols_order = ["quantidade", "unidade", "item", "detalhe"]
                                    cols_fin = [c for c in cols_order if c in df.columns]
                                    df = df[cols_fin]

                                    st.dataframe(df, use_container_width=True)
                                    
                                    # Download Excel BR
                                    csv_br = converter_csv_br(df)
                                    st.download_button(
                                        "📥 Baixar Planilha (Excel)",
                                        csv_br,
                                        "levantamento_cad.csv",
                                        "text/csv"
                                    )
                                else:
                                    st.warning("Não foram encontrados materiais quantificáveis no texto.")

                                # ALERTAS
                                if dados.get("alertas"):
                                    with st.expander("⚠️ Alertas de Interpretação"):
                                        for a in dados["alertas"]: st.write(f"- {a}")

    except Exception as e:
        st.error(f"Erro: {e}")
    finally:
        if os.path.exists(path_temp): os.remove(path_temp)
