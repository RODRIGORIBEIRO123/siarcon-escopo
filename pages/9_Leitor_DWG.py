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
st.set_page_config(page_title="Siarcon - Leitor V15", page_icon="🎯", layout="wide")

# ==================================================
# 🔧 FUNÇÕES DE SEGURANÇA
# ==================================================
def safe_float(valor):
    try:
        if valor is None: return 0.0
        # Remove pontos de milhar se existirem (ex: 1.300 -> 1300)
        # Mas cuidado com 1.5 (metro). A IA já deve mandar limpo, aqui é o backup.
        val_str = str(valor).replace('mm', '').strip()
        
        # Se tiver vírgula, troca por ponto
        val_str = val_str.replace(',', '.')
        
        # Extrai número
        nums = re.findall(r"[-+]?\d*\.\d+|\d+", val_str)
        if nums: 
            return float(nums[0])
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
    
    max_len_segmento = st.number_input(
        "Máx. Comprimento por Trecho (m):", 
        min_value=1.0, max_value=50.0, value=10.0,
        help="Qualquer medida lida acima disso será zerada (evita confundir vazão com metro)."
    )

    tipo_leitura = st.radio(
        "Estratégia:", ("Filtrar Cortes (Recomendado)", "Ler Tudo"), index=0
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
        
        # MANTÉM OS NÚMEROS COM PONTO (Ex: 1.300) PARA A IA INTERPRETAR
        # NÃO FILTRA NÚMEROS GRANDES AQUI, DEIXA A IA DECIDIR PELO PARÊNTESES
        
        texto_limpo.append(t)
        
    if "Filtrar" in modo_filtrar:
        lista_final = list(dict.fromkeys(texto_limpo))
    else:
        lista_final = texto_limpo[:6000]

    return " | ".join(lista_final)

# ==================================================
# 🧠 CÉREBRO DA IA (RECONHECIMENTO DE FORMATAÇÃO BR)
# ==================================================
def processar_ia(texto, tipo_leitura, max_len):
    if not api_key: return None

    instrucao_cortes = ""
    if "Filtrar" in tipo_leitura:
        instrucao_cortes = "O desenho tem Cortes. IGNORE textos de medidas repetidos. Use apenas a Planta Baixa."

    prompt = f"""
    Você é um Engenheiro de HVAC Sênior.
    Analise o texto cru do CAD (separado por ' | ').
    {instrucao_cortes}

    PADRÃO DE FORMATAÇÃO DO ARQUIVO (IMPORTANTE):
    1. OS NÚMEROS USAM PONTO PARA MILHAR: "1.300" = 1300mm. "34.000" = 34000.
    2. VAZÃO ESTÁ ENTRE PARÊNTESES: "(34.000)" = Vazão. "(4.250)" = Vazão.

    REGRAS DE EXTRAÇÃO:
    
    1. DIMENSÕES DE DUTO:
       - Procure padrão "LARGURA x ALTURA" onde os números podem ter pontos.
       - Exemplo: "1.300x700" -> LEIA COMO: Largura 1300mm, Altura 700mm.
       - Exemplo: "500x450" -> Largura 500mm, Altura 450mm.
       - REMOVA OS PONTOS DAS DIMENSÕES.

    2. VAZÃO (O INIMIGO):
       - Qualquer número dentro de parênteses `(...)` é VAZÃO.
       - Exemplo: "(34.000)" -> IGNORE COMPLETAMENTE PARA COMPRIMENTO.
       - Exemplo: "(4.250)" -> IGNORE.
    
    3. COMPRIMENTO (A MISSÃO):
       - Procure números que NÃO estão entre parênteses.
       - Procure números próximos às dimensões.
       - Se encontrar "1.300x700 | (34.000)", e não houver outro número, o comprimento é 0.
       - Se encontrar "1.300x700 | (34.000) | 2000", o comprimento é 2000mm (2m).
       - Se encontrar "1.300x700 | (34.000) | 2", o comprimento é 2m.

    4. EQUIPAMENTOS:
       - Liste Fancoil, Split, Cassete, VRF, Exaustor.

    SAÍDA JSON:
    {{
        "dutos": [
            {{ 
                "dimensao_original": "1.300x700",
                "largura_mm": 1300, 
                "altura_mm": 700, 
                "comprimento_m": 0, 
                "nota": "Ignorado (34.000) pois é vazão. Sem comprimento explícito." 
            }}
        ],
        "equipamentos": []
    }}
    """

    try:
        response = openai.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": f"Limite Máx Trecho: {max_len}m. Texto:\n\n{texto[:60000]}"} 
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
st.title("🎯 Leitor V15 (Ponto de Milhar e Parênteses)")
st.markdown("Algoritmo ajustado para formatação: `1.300` = 1300 e `(34.000)` = Vazão.")

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
            with st.spinner("Lendo textos..."):
                for entity in msp.query('TEXT MTEXT'):
                    if entity.dxf.text: raw_text.append(entity.dxf.text)
            
            texto_proc = limpar_texto_cad(raw_text, tipo_leitura)
            st.info(f"Dados lidos: {len(raw_text)} blocos.")
            
            if st.button("🚀 Calcular (Corrigido)", type="primary"):
                if not api_key:
                    st.error("Sem API Key.")
                else:
                    with st.spinner("Interpretando 1.300x700 e ignorando (Vazão)..."):
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
                                
                                # TRAVA DE SEGURANÇA
                                if l > max_len_segmento:
                                    d['nota'] += f" [CORTE: {l}m > limite]"
                                    l = 0 
                                
                                if w > 0 and h > 0:
                                    maior = max(w, h)
                                    gauge = definir_bitola_nbr(maior, classe_pressao)
                                    perim = 2 * (w/1000 + h/1000)
                                    # Se L=0, Área=0, Peso=0 (Correto para orçamento não inventado)
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
                                st.warning("Dutos encontrados, mas nenhum texto de comprimento válido foi identificado.")
                                
                            meta = {"Norma": "NBR 16401", "Peso Total": tot_kg, "Trava Máx (m)": max_len_segmento}
                            xlsx = gerar_excel_completo(pd.DataFrame(res_dutos), pd.DataFrame(dados.get("equipamentos",[])), meta)
                            st.download_button("📥 Baixar Excel", xlsx, "Levantamento_V15.xlsx")

    except Exception as e:
        st.error(f"Erro: {e}")
    finally:
        if os.path.exists(path_temp): os.remove(path_temp)
