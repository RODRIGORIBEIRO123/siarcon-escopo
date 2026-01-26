import streamlit as st
import ezdxf
from ezdxf import recover
import pandas as pd
import os
import tempfile
import openai
import json
import io

# Configuração da Página
st.set_page_config(page_title="Calculadora de Dutos Pro", page_icon="❄️", layout="wide")

# ==================================================
# 🔑 CONFIGURAÇÃO E INPUTS
# ==================================================
api_key_sistema = st.secrets.get("OPENAI_API_KEY", None)

with st.sidebar:
    st.header("⚙️ Configuração de Projeto")
    
    if api_key_sistema:
        openai.api_key = api_key_sistema
        api_key = api_key_sistema
        st.success("🔑 Chave segura ativa.")
    else:
        api_key = st.text_input("API Key (OpenAI):", type="password")
        if api_key: openai.api_key = api_key

    st.divider()

    st.subheader("💨 Classe de Pressão")
    classe_pressao = st.selectbox(
        "Selecione a pressão estática:",
        options=[
            "Muito Baixa (até 250 Pa)", 
            "Baixa (até 500 Pa)", 
            "Média (até 1000 Pa)", 
            "Alta (> 1000 Pa)"
        ],
        index=1,
        help="Define a espessura da chapa (Bitola) conforme SMACNA/NBR."
    )
    
    perda_corte = st.slider("Margem de Perda/Corte (%)", 0, 40, 10) / 100

# ==================================================
# 📐 CÉREBRO DE ENGENHARIA (TABELAS DE BITOLA)
# ==================================================
def definir_bitola(maior_lado_mm, classe):
    """
    Define a bitola (Gauge) baseada na pressão e dimensão.
    Lógica aproximada baseada em normas SMACNA/NBR 16401.
    """
    
    # 1. MUITO BAIXA (250 Pa) - Permite dutos maiores com chapa fina
    if "250 Pa" in classe:
        if maior_lado_mm <= 450: return 26
        if maior_lado_mm <= 900: return 24
        if maior_lado_mm <= 1500: return 22
        return 20

    # 2. BAIXA (500 Pa)
    elif "500 Pa" in classe:
        if maior_lado_mm <= 300: return 26
        if maior_lado_mm <= 750: return 24
        if maior_lado_mm <= 1400: return 22
        return 20
    
    # 3. MÉDIA (1000 Pa)
    elif "Média" in classe:
        if maior_lado_mm <= 250: return 26
        if maior_lado_mm <= 600: return 24
        if maior_lado_mm <= 1200: return 22
        return 20

    # 4. ALTA (>1000 Pa) - Reforçado
    else:
        if maior_lado_mm <= 200: return 24
        if maior_lado_mm <= 500: return 22
        if maior_lado_mm <= 1000: return 20
        return 18

def calcular_peso_chapa(bitola):
    # Pesos médios de aço galvanizado (kg/m²)
    pesos = {26: 4.20, 24: 5.60, 22: 6.80, 20: 8.40, 18: 10.50}
    return pesos.get(bitola, 6.0)

# ==================================================
# 📝 GERADOR DE EXCEL (NOVO)
# ==================================================
def gerar_excel_formatado(df_detalhado, resumo_dados):
    output = io.BytesIO()
    
    # Cria o Excel Writer usando XlsxWriter como engine
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        
        # ABA 1: MEMORIAL ANALÍTICO
        df_detalhado.to_excel(writer, sheet_name='Memorial Analítico', index=False)
        
        workbook = writer.book
        worksheet = writer.sheets['Memorial Analítico']
        
        # Formatações
        formato_header = workbook.add_format({'bold': True, 'bg_color': '#D3D3D3', 'border': 1})
        formato_numero = workbook.add_format({'num_format': '#,##0.00'})
        formato_central = workbook.add_format({'align': 'center'})

        # Aplica formatação no cabeçalho
        for col_num, value in enumerate(df_detalhado.columns.values):
            worksheet.write(0, col_num, value, formato_header)
            worksheet.set_column(col_num, col_num, 15) # Largura padrão

        # ABA 2: RESUMO GERAL
        worksheet_resumo = workbook.add_worksheet('Resumo Executivo')
        worksheet_resumo.write(0, 0, "Item", formato_header)
        worksheet_resumo.write(0, 1, "Valor", formato_header)
        
        linha = 1
        for chave, valor in resumo_dados.items():
            worksheet_resumo.write(linha, 0, chave)
            worksheet_resumo.write(linha, 1, valor)
            linha += 1
            
        worksheet_resumo.set_column(0, 0, 25)
        worksheet_resumo.set_column(1, 1, 15)

    output.seek(0)
    return output

# ==================================================
# 🧠 CÉREBRO DA IA
# ==================================================
def processar_com_inteligencia(texto_sujo):
    if not api_key: return None

    prompt_sistema = """
    Você é um Engenheiro de HVAC Sênior.
    Analise o texto bruto extraído de um projeto CAD e identifique TRECHOS DE DUTOS.

    MISSÃO:
    1. Procure padrões dimensionais (ex: "300x200", "500x300", "40x20").
    2. Identifique o COMPRIMENTO linear associado (m, metros). Se não tiver unidade, assuma metros se for número pequeno (<100).
    3. Agrupe trechos iguais (ex: se tiver 3 notas de "Duto 300x200", some os comprimentos).

    SAÍDA JSON OBRIGATÓRIA:
    {
        "resumo_projeto": "Breve descrição do sistema identificado.",
        "dutos": [
            {
                "largura_mm": 300, 
                "altura_mm": 200, 
                "comprimento_total_m": 15.5,
                "nota_original": "Duto Alim. 300x200"
            }
        ]
    }
    
    OBS: Converta tudo para milímetros (largura/altura) e metros (comprimento).
    """

    try:
        response = openai.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": prompt_sistema},
                {"role": "user", "content": f"Extraia o levantamento de dutos deste texto:\n\n{texto_sujo[:35000]}"} 
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
    ignorar = ["LAYER", "VIEWPORT", "STANDARD", "ISO", "BYLAYER", "COTAS", "MODEL"]
    for item in lista_textos:
        t = str(item).strip()
        if len(t) < 3 or any(x in t.upper() for x in ignorar): continue
        texto_limpo.append(t)
    return "\n".join(texto_limpo[:3000])

def salvar_temp(arquivo):
    with tempfile.NamedTemporaryFile(delete=False, suffix=".dxf") as tmp:
        tmp.write(arquivo.getbuffer())
        return tmp.name

# ==================================================
# 🖥️ INTERFACE
# ==================================================
st.title("❄️ Calculadora de Dutos & Memorial (CAD)")
st.markdown("Extração automática de quantitativos com geração de **Memorial de Cálculo em Excel**.")

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
            with st.spinner("Lendo projeto CAD..."):
                for entity in msp.query('TEXT MTEXT'):
                    if entity.dxf.text: textos_crus.append(entity.dxf.text)
            
            texto_pronto = limpar_texto_cad(textos_crus)
            
            c1, c2 = st.columns([1, 2])
            with c1:
                st.info(f"Texto lido: {len(textos_crus)} elementos")
                with st.expander("Ver Texto Bruto"):
                    st.text_area("", texto_pronto, height=350)

            with c2:
                st.subheader("🤖 Processamento")
                if not api_key:
                    st.error("⚠️ Configure a API Key.")
                else:
                    if st.button("🚀 Gerar Memorial de Cálculo", type="primary"):
                        with st.spinner("Calculando bitolas, áreas e pesos..."):
                            dados = processar_com_inteligencia(texto_pronto)
                            
                            if "erro" in dados:
                                st.error(f"Erro IA: {dados['erro']}")
                            else:
                                lista_dutos = dados.get("dutos", [])
                                
                                if lista_dutos:
                                    # --- CÁLCULOS ---
                                    resultados = []
                                    total_kg = 0
                                    total_m2 = 0
                                    
                                    for d in lista_dutos:
                                        L = d.get('largura_mm', 0)
                                        H = d.get('altura_mm', 0)
                                        comp = d.get('comprimento_total_m', 0)
                                        
                                        if L > 0 and H > 0:
                                            # 1. Bitola
                                            maior_lado = max(L, H)
                                            gauge = definir_bitola(maior_lado, classe_pressao)
                                            
                                            # 2. Área
                                            perimetro = 2 * ((L/1000) + (H/1000))
                                            area_liquida = perimetro * comp
                                            area_final = area_liquida * (1 + perda_corte)
                                            
                                            # 3. Peso
                                            kg_m2 = calcular_peso_chapa(gauge)
                                            peso = area_final * kg_m2
                                            
                                            resultados.append({
                                                "Dimensão": f"{int(L)}x{int(H)}",
                                                "Comp. (m)": round(comp, 2),
                                                "Bitola": f"#{gauge}",
                                                "Área (m²)": round(area_final, 2),
                                                "Peso (kg)": round(peso, 2),
                                                "Obs": d.get("nota_original", "")
                                            })
                                            
                                            total_kg += peso
                                            total_m2 += area_final

                                    # --- VISUALIZAÇÃO ---
                                    st.success("✅ Memorial Gerado com Sucesso!")
                                    
                                    # Cards Resumo
                                    k1, k2, k3 = st.columns(3)
                                    k1.metric("Peso Total", f"{total_kg:,.1f} kg")
                                    k2.metric("Área Total", f"{total_m2:,.1f} m²")
                                    k3.metric("Classe Pressão", classe_pressao.split('(')[0])

                                    # Tabela na Tela
                                    df = pd.DataFrame(resultados)
                                    st.dataframe(df, use_container_width=True)
                                    
                                    # --- PREPARAR EXCEL ---
                                    resumo_dict = {
                                        "Obra/Projeto": "Extraído via Leitor CAD",
                                        "Classe de Pressão": classe_pressao,
                                        "Perda Considerada": f"{int(perda_corte*100)}%",
                                        "Peso Total (kg)": total_kg,
                                        "Área Total (m²)": total_m2
                                    }
                                    
                                    excel_file = gerar_excel_formatado(df, resumo_dict)
                                    
                                    st.download_button(
                                        label="📥 Baixar Memorial Formatado (.xlsx)",
                                        data=excel_file,
                                        file_name="Memorial_Dutos.xlsx",
                                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                                    )
                                    
                                else:
                                    st.warning("Não encontrei dutos. Verifique se o desenho tem textos legíveis (ex: 300x200).")

    except Exception as e:
        st.error(f"Erro: {e}")
    finally:
        if os.path.exists(path_temp): os.remove(path_temp)
