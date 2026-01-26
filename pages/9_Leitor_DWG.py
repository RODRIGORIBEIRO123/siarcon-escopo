import streamlit as st
import ezdxf
from ezdxf import recover
import pandas as pd
import os
import tempfile
import openai
import json

# Configuração da Página
st.set_page_config(page_title="Calculadora de Dutos CAD", page_icon="❄️", layout="wide")

# ==================================================
# 🔑 CONFIGURAÇÃO E INPUTS DE ENGENHARIA
# ==================================================
api_key_sistema = st.secrets.get("OPENAI_API_KEY", None)

with st.sidebar:
    st.header("⚙️ Configuração de Projeto")
    
    # 1. API KEY
    if api_key_sistema:
        openai.api_key = api_key_sistema
        api_key = api_key_sistema
        st.success("🔑 Chave segura ativa.")
    else:
        api_key = st.text_input("API Key (OpenAI):", type="password")
        if api_key: openai.api_key = api_key

    st.divider()

    # 2. PARÂMETROS DE CÁLCULO (O PULO DO GATO)
    st.subheader("💨 Classe de Pressão")
    classe_pressao = st.selectbox(
        "Selecione a pressão do sistema:",
        options=["Baixa (até 500 Pa)", "Média (até 1000 Pa)", "Alta (> 1000 Pa)"],
        index=0,
        help="Isso define a bitola (espessura) da chapa segundo norma SMACNA/NBR."
    )
    
    perda_corte = st.slider("Margem de Perda/Corte (%)", 0, 20, 10) / 100

# ==================================================
# 📐 CÉREBRO DE ENGENHARIA (TABELA SMACNA SIMPLIFICADA)
# ==================================================
def definir_bitola(maior_lado_mm, classe):
    """
    Define a bitola (Gauge) e a espessura (mm) com base no maior lado do duto e na pressão.
    Baseado em aproximação da SMACNA para Dutos Retangulares.
    """
    # Lógica simplificada para fins práticos (Pode ser refinada com tabelas exatas da NBR)
    
    # TABELA DE BAIXA PRESSÃO
    if "Baixa" in classe:
        if maior_lado_mm <= 300: return 26, 0.50
        if maior_lado_mm <= 750: return 24, 0.65
        if maior_lado_mm <= 1500: return 22, 0.80
        return 20, 0.95 # Acima de 1500
    
    # TABELA DE MÉDIA PRESSÃO
    elif "Média" in classe:
        if maior_lado_mm <= 250: return 26, 0.50
        if maior_lado_mm <= 600: return 24, 0.65
        if maior_lado_mm <= 1200: return 22, 0.80
        return 20, 0.95

    # TABELA DE ALTA PRESSÃO
    else:
        if maior_lado_mm <= 200: return 24, 0.65
        if maior_lado_mm <= 500: return 22, 0.80
        if maior_lado_mm <= 1000: return 20, 0.95
        return 18, 1.25

def calcular_peso_chapa(bitola):
    # Pesos aproximados de chapa galvanizada (kg/m²)
    pesos = {
        26: 4.0,
        24: 5.2,
        22: 6.4,
        20: 7.6,
        18: 10.0
    }
    return pesos.get(bitola, 5.0)

# ==================================================
# 🧠 CÉREBRO DA IA (EXTRATOR DE DIMENSÕES)
# ==================================================
def processar_com_inteligencia(texto_sujo):
    if not api_key: return None

    prompt_sistema = """
    Você é um Engenheiro de HVAC. Analise o texto do CAD e extraia dimensões de DUTOS.

    SUA MISSÃO:
    1. Identifique textos que descrevem dutos (ex: "300x200", "40x30", "Duto 500x400").
    2. Identifique o COMPRIMENTO linear associado a esses dutos (em metros).
    3. Ignore cotas soltas que não sejam dimensões de duto.

    SAÍDA JSON OBRIGATÓRIA:
    {
        "resumo": "Resumo do que foi encontrado.",
        "dutos": [
            {
                "largura_mm": 300, 
                "altura_mm": 200, 
                "comprimento_m": 15.0, 
                "descricao_original": "Duto 300x200"
            }
        ],
        "outros_materiais": ["Lista de outros itens que não são dutos (ex: difusores)"]
    }
    
    OBS: Se a medida estiver em cm (ex: 30x20), CONVERTA para mm (300x200).
    Se houver vários trechos do mesmo duto, SOMAR os comprimentos.
    """

    try:
        response = openai.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": prompt_sistema},
                {"role": "user", "content": f"Extraia a lista de dutos deste texto:\n\n{texto_sujo[:30000]}"} 
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
    # Mantemos duplicatas pois a IA precisa contar repetições
    ignorar = ["LAYER", "VIEWPORT", "STANDARD", "ISO", "BYLAYER", "COTAS"]
    for item in lista_textos:
        t = str(item).strip()
        if len(t) < 3 or any(x in t.upper() for x in ignorar): continue
        texto_limpo.append(t)
    return "\n".join(texto_limpo[:2500])

def salvar_temp(arquivo):
    with tempfile.NamedTemporaryFile(delete=False, suffix=".dxf") as tmp:
        tmp.write(arquivo.getbuffer())
        return tmp.name

# ==================================================
# 🖥️ INTERFACE
# ==================================================
st.title("❄️ Calculadora de Dutos & Chapas (CAD)")
st.markdown("Extrai dimensões do DXF e calcula **Peso (kg)** e **Área ($m^2$)** conforme a **Classe de Pressão**.")

arquivo_cad = st.file_uploader("Arraste o DXF aqui", type=["dxf"])

if arquivo_cad:
    st.divider()
    path_temp = salvar_temp(arquivo_cad)

    try:
        try: doc = ezdxf.readfile(path_temp)
        except: doc, auditor = recover.readfile(path_temp)

        if doc:
            msp = doc.modelspace()
            textos_crus = []
            with st.spinner("Lendo projeto..."):
                for entity in msp.query('TEXT MTEXT'):
                    if entity.dxf.text: textos_crus.append(entity.dxf.text)
            
            texto_pronto = limpar_texto_cad(textos_crus)
            
            # Divide a tela
            c1, c2 = st.columns([1, 2])
            with c1:
                st.info(f"Elementos lidos: {len(textos_crus)}")
                st.caption("A IA vai procurar padrões como '300x200', '50x40', etc.")
                with st.expander("Ver Texto Bruto"):
                    st.text_area("", texto_pronto, height=300)

            with c2:
                st.subheader("🤖 Cálculo de Engenharia")
                if not api_key:
                    st.error("Configure a API Key.")
                else:
                    if st.button("🚀 Calcular Chapas e Bitolas", type="primary"):
                        with st.spinner("Identificando dutos, aplicando norma SMACNA e calculando pesos..."):
                            dados = processar_com_inteligencia(texto_pronto)
                            
                            if "erro" in dados:
                                st.error(f"Erro IA: {dados['erro']}")
                            else:
                                lista_dutos = dados.get("dutos", [])
                                
                                if lista_dutos:
                                    # --- PROCESSAMENTO MATEMÁTICO ---
                                    resultados = []
                                    total_kg = 0
                                    total_m2 = 0
                                    
                                    for d in lista_dutos:
                                        # Pega dados da IA
                                        L = d.get('largura_mm', 0)
                                        H = d.get('altura_mm', 0)
                                        comp = d.get('comprimento_m', 0)
                                        
                                        if L > 0 and H > 0 and comp > 0:
                                            # 1. Define Bitola (Norma)
                                            maior_lado = max(L, H)
                                            gauge, espessura = definir_bitola(maior_lado, classe_pressao)
                                            
                                            # 2. Calcula Área (Perímetro * Comprimento)
                                            # Perimetro em metros = 2 * (L/1000 + H/1000)
                                            perimetro = 2 * ((L/1000) + (H/1000))
                                            area_item = perimetro * comp
                                            area_com_perda = area_item * (1 + perda_corte)
                                            
                                            # 3. Calcula Peso
                                            kg_m2 = calcular_peso_chapa(gauge)
                                            peso_total = area_com_perda * kg_m2
                                            
                                            resultados.append({
                                                "Dimensão": f"{int(L)}x{int(H)}",
                                                "Comp. (m)": comp,
                                                "Maior Lado": int(maior_lado),
                                                "Bitola Rec.": f"#{gauge}",
                                                "Área ($m^2$)": round(area_com_perda, 2),
                                                "Peso Est. (kg)": round(peso_total, 2)
                                            })
                                            
                                            total_kg += peso_total
                                            total_m2 += area_com_perda

                                    # --- EXIBIÇÃO ---
                                    st.success("Cálculo Realizado!")
                                    st.markdown(f"**Resumo da IA:** {dados.get('resumo')}")
                                    
                                    # Cards de Totais
                                    k1, k2, k3 = st.columns(3)
                                    k1.metric("Peso Total (Aço)", f"{total_kg:,.1f} kg")
                                    k2.metric("Área Total", f"{total_m2:,.1f} m²")
                                    k3.metric("Perda Considerada", f"{int(perda_corte*100)}%")
                                    
                                    # Tabela Detalhada
                                    df = pd.DataFrame(resultados)
                                    st.dataframe(df, use_container_width=True)
                                    
                                    # Download
                                    csv = df.to_csv(sep=';', decimal=',', index=False).encode('utf-8-sig')
                                    st.download_button("📥 Baixar Quantitativo de Chapas", csv, "dutos_calculado.csv", "text/csv")
                                    
                                else:
                                    st.warning("A IA não encontrou padrões de dutos (ex: 300x200) no texto.")
                                    st.write("Outros itens encontrados:", dados.get("outros_materiais"))

    except Exception as e:
        st.error(f"Erro: {e}")
    finally:
        if os.path.exists(path_temp): os.remove(path_temp)
