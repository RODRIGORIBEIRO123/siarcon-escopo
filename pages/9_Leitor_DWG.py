import streamlit as st
import ezdxf
from ezdxf import recover
import pandas as pd
import os
import tempfile
import openai
import json
import io
import re

# Configuração da Página
st.set_page_config(page_title="Siarcon - Leitor Pro V13", page_icon="🛡️", layout="wide")

# ==================================================
# 🔧 FUNÇÕES DE SEGURANÇA
# ==================================================
def safe_float(valor):
    try:
        if valor is None: return 0.0
        limpo = str(valor).replace(',', '.').strip()
        nums = re.findall(r"[-+]?\d*\.\d+|\d+", limpo)
        if nums: return float(nums[0])
        return 0.0
    except:
        return 0.0

# ==================================================
# 🔑 CONFIGURAÇÃO (SIDEBAR)
# ==================================================
api_key_sistema = st.secrets.get("OPENAI_API_KEY", None)

with st.sidebar:
    st.title("⚙️ Configuração")
    if api_key_sistema:
        openai.api_key = api_key_sistema
        api_key = api_key_sistema
        st.success("🔑 Chave Segura Ativa")
    else:
        api_key = st.text_input("API Key (OpenAI):", type="password")
        if api_key: openai.api_key = api_key

    st.divider()
    st.subheader("🛡️ Travas de Segurança")
    
    # NOVA TRAVA CRÍTICA
    max_len_segmento = st.number_input(
        "Máx. Comprimento por Trecho (m):", 
        min_value=1.0, max_value=20.0, value=6.0,
        help="Ignora valores maiores que isso. Evita confundir Vazão (34000) com Comprimento (34m)."
    )

    tipo_leitura = st.radio(
        "Estratégia:", ("Filtrar Cortes", "Ler Tudo"), index=0
    )

    st.subheader("📋 Parâmetros NBR 16401")
    classe_pressao = st.selectbox(
        "Classe de Pressão:",
        ["Classe A (Baixa)", "Classe B (Média)", "Classe C (Alta)"], index=0
    )
    perda_corte = st.slider("Perda (%)", 0, 40, 10) / 100

# ==================================================
# 📐 TABELAS TÉCNICAS
# ==================================================
def definir_bitola_nbr(maior_lado_mm, classe_txt):
    maior_lado_mm = safe_float(maior_lado_mm)
    if "Classe A" in classe_txt:
        if maior_lado_mm <= 300: return 24
        if maior_lado_mm <= 750: return 24
        if maior_lado_mm <= 1200: return 22
        if maior_lado_mm <= 1500: return 20
        return 18
    elif "Classe B" in classe_txt:
        if maior_lado_mm <= 300: return 24
        if maior_lado_mm <= 600: return 24
        if maior_lado_mm <= 1000: return 22
        if maior_lado_mm <= 1300: return 20
        return 18
    else:
        if maior_lado_mm <= 250: return 24
        if maior_lado_mm <= 500: return 22
        if maior_lado_mm <= 900: return 20
        return 18

def calcular_peso_chapa(bitola):
    pesos = {26: 4.00, 24: 5.60, 22: 6.80, 20: 8.40, 18: 10.50}
    return pesos.get(int(safe_float(bitola)), 6.0)

# ==================================================
# 📝 GERADOR EXCEL
# ==================================================
def gerar_excel_completo(df_dutos, df_equip, resumo_meta):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        wb = writer.book
        ws_res = wb.add_worksheet('Resumo')
        fmt_head = wb.add_format({'bold': True, 'bg_color': '#D9E1F2', 'border': 1})
        
        ws_res.write(0, 0, "Item", fmt_head)
        ws_res.write(0, 1, "Valor", fmt_head)
        row = 1
        for k, v in resumo_meta.items():
            ws_res.write(row, 0, k)
            ws_res.write(row, 1, v)
            row += 1
            
        if not df_dutos.empty:
            df_dutos.to_excel(writer, sheet_name='Dutos', index=False)
        if not df_equip.empty:
            df_equip.to_excel(writer, sheet_name='Equipamentos', index=False)
            
    output.seek(0)
    return output

# ==================================================
# 🔧 LIMPEZA INTELIGENTE
# ==================================================
def limpar_texto_cad(lista_textos, modo_filtrar):
    texto_limpo = []
    proibidos = ["LAYER", "VIEWPORT", "COTAS", "MODEL", "LAYOUT", "PRANCHA", "FOLHA", "ESCALA", "SCALE", "1:50", "PATH"]
    
    for item in lista_textos:
        t = str(item).strip()
        if len(t) < 2: continue
        if any(p in t.upper() for p in proibidos): continue
        
        # Filtro de pré-processamento: Se for número gigante (>50000), nem manda pra IA
        try:
            val = float(t.replace(',','.'))
            if val > 50000: continue # Ignora coordenadas UTM
        except:
            pass
            
        texto_limpo.append(t)
        
    if "Filtrar" in modo_filtrar:
        lista_final = list(dict.fromkeys(texto_limpo))
    else:
        lista_final = texto_limpo[:5000]

    return " | ".join(lista_final)

# ==================================================
# 🧠 CÉREBRO DA IA (PROMPT ANTI-VAZÃO)
# ==================================================
def processar_ia(texto, tipo_leitura, max_len):
    if not api_key: return None

    prompt = f"""
    Você é um Engenheiro de HVAC. Analise o texto do CAD (separado por ' | ').
    
    PROBLEMA A EVITAR: Confundir VAZÃO ($m^3/h$) com COMPRIMENTO (mm).
    
    REGRAS DE OURO:
    1. DIMENSÕES: Padrão "Largura x Altura" (ex: 1300x700). Assuma mm.
    
    2. FILTRO DE VAZÃO (IMPORTANTE):
       - Números grandes como 34000, 17000, 15000 ao lado de dutos SÃO VAZÃO ($m^3/h$).
       - NUNCA converta esses números para metros. IGNORE-OS.
       - Dutos raramente têm trechos únicos maiores que 6m. Se você achar "34m", está errado.
    
    3. FILTRO DE NÍVEL:
       - Números como 2800, 3000, 2600 soltos são Altura do Forro. IGNORE.
    
    4. COMPRIMENTO VÁLIDO:
       - Procure números pequenos (ex: 1.5, 3, 5.2).
       - Procure prefixos (L=, C=) ou sufixos (m).
       - Se encontrar "1300x700 | 34000", o comprimento é DESCONHECIDO (não use 34!).
    
    SAÍDA JSON:
    {{
        "dutos": [
            {{ "dimensao": "1300x700", "largura_mm": 1300, "altura_mm": 700, "comprimento_m": 0, "nota": "Ignorado 34000 (Vazão)" }}
        ],
        "equipamentos": []
    }}
    """

    try:
        response = openai.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": f"Limite Máximo aceitável p/ trecho: {max_len}m. Texto:\n\n{texto[:50000]}"} 
            ],
            temperature=0.0,
            response_format={"type": "json_object"}
        )
        return json.loads(response.choices[0].message.content)
    except Exception as e:
        return {"erro": str(e)}

# ==================================================
# 🖥️ INTERFACE
# ==================================================
st.title("🛡️ Leitor Pro V13 (Filtro Vazão)")
st.markdown("Algoritmo ajustado para diferenciar **Vazão ($m^3/h$)** de **Comprimento (m)**.")

arquivo = st.file_uploader("Upload DXF", type=["dxf"])

if arquivo:
    st.divider()
    path_temp = tempfile.NamedTemporaryFile(delete=False, suffix=".dxf").name
    arquivo.seek(0)
    with open(path_temp, "wb") as f: f.write(arquivo.getbuffer())

    try:
        try: doc = ezdxf.readfile(path_temp)
        except: doc, auditor = recover.readfile(path_temp)

        if doc:
            msp = doc.modelspace()
            raw_text = []
            with st.spinner("Lendo..."):
                for entity in msp.query('TEXT MTEXT'):
                    if entity.dxf.text: raw_text.append(entity.dxf.text)
            
            texto_proc = limpar_texto_cad(raw_text, tipo_leitura)
            st.info(f"Dados lidos: {len(raw_text)} blocos.")
            
            if st.button("🚀 Calcular (Com Trava de Segurança)", type="primary"):
                if not api_key:
                    st.error("Sem API Key.")
                else:
                    with st.spinner("Filtrando vazões e níveis..."):
                        dados = processar_ia(texto_proc, tipo_leitura, max_len_segmento)
                        
                        if "erro" in dados:
                            st.error(f"Erro IA: {dados['erro']}")
                        else:
                            # PROCESSAMENTO
                            lista_dutos = dados.get("dutos", [])
                            res_dutos = []
                            tot_kg = 0
                            tot_m2 = 0
                            
                            for d in lista_dutos:
                                w = safe_float(d.get('largura_mm'))
                                h = safe_float(d.get('altura_mm'))
                                l = safe_float(d.get('comprimento_m'))
                                
                                # --- TRAVA DE SEGURANÇA FINAL (HARD CODE) ---
                                # Se a IA falhar e mandar um 34m, o Python corta aqui.
                                if l > max_len_segmento:
                                    d['nota'] += f" [CORTE: {l}m > limite {max_len_segmento}m]"
                                    l = 0 # Zera ou assume um valor padrão? Melhor zerar para não dar falso positivo.
                                
                                if w > 0 and h > 0 and l > 0:
                                    maior = max(w, h)
                                    gauge = definir_bitola_nbr(maior, classe_pressao)
                                    perim = 2 * (w/1000 + h/1000)
                                    area = (perim * l) * (1 + perda_corte)
                                    peso = area * calcular_peso_chapa(gauge)
                                    
                                    tot_kg += peso
                                    tot_m2 += area
                                    res_dutos.append({
                                        "Dimensão": f"{int(w)}x{int(h)}",
                                        "Comp. (m)": round(l, 2),
                                        "Bitola": f"#{gauge}",
                                        "Área (m²)": round(area, 2),
                                        "Peso (kg)": round(peso, 2),
                                        "Obs": d.get("nota", "")
                                    })
                            
                            # EXIBIÇÃO
                            c1, c2, c3 = st.columns(3)
                            c1.metric("Peso Total", f"{tot_kg:,.1f} kg")
                            c2.metric("Área Isol.", f"{tot_m2:,.1f} m²")
                            c3.metric("Limite p/ Trecho", f"{max_len_segmento} m")
                            
                            if res_dutos:
                                st.dataframe(pd.DataFrame(res_dutos), use_container_width=True)
                            else:
                                st.warning("Nenhum duto válido encontrado (Talvez todos os números fossem vazão?).")
                                
                            # Download
                            meta = {"Norma": "NBR 16401", "Peso Total": tot_kg, "Trava Máx (m)": max_len_segmento}
                            xlsx = gerar_excel_completo(pd.DataFrame(res_dutos), pd.DataFrame(dados.get("equipamentos",[])), meta)
                            st.download_button("📥 Baixar Excel", xlsx, "Levantamento_V13.xlsx")

    except Exception as e:
        st.error(f"Erro: {e}")
    finally:
        if os.path.exists(path_temp): os.remove(path_temp)
