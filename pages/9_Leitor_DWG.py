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
st.set_page_config(page_title="Siarcon - Leitor Pro (Sem Unidades)", page_icon="🏗️", layout="wide")

# ==================================================
# 🔧 FUNÇÕES DE SEGURANÇA
# ==================================================
def safe_float(valor):
    """Converte texto para float, assumindo 0.0 se der erro."""
    try:
        if valor is None: return 0.0
        # Troca vírgula por ponto e remove letras
        limpo = str(valor).replace(',', '.').strip()
        nums = re.findall(r"[-+]?\d*\.\d+|\d+", limpo)
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

    st.subheader("📋 Parâmetros (NBR 16401)")
    
    tipo_leitura = st.radio(
        "Estratégia de Leitura:",
        ("Filtrar Cortes (Evitar Duplicatas)", "Ler Tudo (Planta Única)"),
        index=0,
        help="Use 'Filtrar' para evitar que a IA some o mesmo duto mostrado em cortes."
    )

    classe_pressao = st.selectbox(
        "Classe de Pressão (NBR 16401-1):",
        ["Classe A (Baixa - até 500 Pa)", "Classe B (Média - até 1000 Pa)", "Classe C (Alta - até 2000 Pa)"],
        index=0
    )
    
    perda_corte = st.slider("Perda de Material / Retalhos (%)", 0, 40, 10) / 100

# ==================================================
# 📐 TABELAS TÉCNICAS (NBR 16401)
# ==================================================
def definir_bitola_nbr(maior_lado_mm, classe_txt):
    maior_lado_mm = safe_float(maior_lado_mm)
    
    # CLASSE A (Baixa)
    if "Classe A" in classe_txt:
        if maior_lado_mm <= 300: return 24
        if maior_lado_mm <= 750: return 24
        if maior_lado_mm <= 1200: return 22
        if maior_lado_mm <= 1500: return 20
        return 18
    
    # CLASSE B (Média)
    elif "Classe B" in classe_txt:
        if maior_lado_mm <= 300: return 24
        if maior_lado_mm <= 600: return 24
        if maior_lado_mm <= 1000: return 22
        if maior_lado_mm <= 1300: return 20
        return 18

    # CLASSE C (Alta)
    else:
        if maior_lado_mm <= 250: return 24
        if maior_lado_mm <= 500: return 22
        if maior_lado_mm <= 900: return 20
        return 18

def calcular_peso_chapa(bitola):
    # kg/m² aproximado para aço galvanizado Z275
    pesos = {26: 4.00, 24: 5.60, 22: 6.80, 20: 8.40, 18: 10.50, 16: 12.90}
    return pesos.get(int(safe_float(bitola)), 6.0)

# ==================================================
# 📝 GERADOR DE EXCEL
# ==================================================
def gerar_excel_completo(df_dutos, df_equip, resumo_meta):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        
        # ABA RESUMO
        wb = writer.book
        ws_res = wb.add_worksheet('Resumo Executivo')
        fmt_title = wb.add_format({'bold': True, 'font_size': 14, 'font_color': '#1F497D'})
        fmt_header = wb.add_format({'bold': True, 'bg_color': '#D9E1F2', 'border': 1})
        fmt_cell = wb.add_format({'border': 1})
        
        ws_res.write(0, 0, "Resumo do Projeto (NBR 16401)", fmt_title)
        ws_res.write(2, 0, "Parâmetro", fmt_header)
        ws_res.write(2, 1, "Valor", fmt_header)
        
        row = 3
        for k, v in resumo_meta.items():
            ws_res.write(row, 0, k, fmt_cell)
            ws_res.write(row, 1, v, fmt_cell)
            row += 1
        ws_res.set_column(0, 0, 30)

        # ABA DUTOS
        if not df_dutos.empty:
            df_dutos.to_excel(writer, sheet_name='Memorial Dutos', index=False)
            ws_dutos = writer.sheets['Memorial Dutos']
            for idx, col in enumerate(df_dutos.columns):
                ws_dutos.write(0, idx, col, fmt_header)
            ws_dutos.set_column(0, 6, 15)

        # ABA EQUIPAMENTOS
        if not df_equip.empty:
            df_equip.to_excel(writer, sheet_name='Lista Equipamentos', index=False)
            ws_equip = writer.sheets['Lista Equipamentos']
            for idx, col in enumerate(df_equip.columns):
                ws_equip.write(0, idx, col, fmt_header)
            ws_equip.set_column(0, 3, 25)
            
    output.seek(0)
    return output

# ==================================================
# 🔧 LIMPEZA (SEM FILTRAR NÚMEROS SOLTOS)
# ==================================================
def limpar_texto_cad(lista_textos, modo_filtrar):
    texto_limpo = []
    
    # Lista de coisas que NÃO SÃO números de projeto (Lixo de CAD)
    proibidos = [
        "LAYER", "VIEWPORT", "STANDARD", "ISO", "BYLAYER", 
        "COTAS", "MODEL", "LAYOUT", "PRANCHA", "FOLHA", 
        "DESENHO", "APROVADO", "DATA", "REVISÃO", "CLIENTE",
        "ESCALA", "SCALE", "1:50", "1:100", "1/50", "1:20", 
        "NOME DO ARQUIVO", "PATH", "USER", "PLOT"
    ]
    
    for item in lista_textos:
        t = str(item).strip()
        t_upper = t.upper()
        
        # Filtros Básicos
        if len(t) < 1: continue
        if any(p in t_upper for p in proibidos): continue
        
        # AQUI MUDOU: Não deletamos mais números soltos.
        # Aceitamos tudo que não seja "proibido", a IA que se vire para interpretar.
        
        texto_limpo.append(t)
        
    # Remove duplicatas se o modo de filtro estiver ativo
    if "Filtrar" in modo_filtrar:
        lista_final = list(dict.fromkeys(texto_limpo))
    else:
        lista_final = texto_limpo[:5000] # Limite de segurança

    return " | ".join(lista_final)

# ==================================================
# 🧠 CÉREBRO DA IA (INFERÊNCIA POR GRANDEZA)
# ==================================================
def processar_ia(texto, tipo_leitura):
    if not api_key: return None

    instrucao_cortes = ""
    if "Filtrar" in tipo_leitura:
        instrucao_cortes = "O desenho tem Cortes. IGNORE textos de medidas repetidos. Use apenas a Planta Baixa."

    prompt = f"""
    Você é um Engenheiro de HVAC Sênior (NBR 16401).
    Analise o texto cru (separado por ' | ').
    {instrucao_cortes}

    CONTEXTO: O PROJETO NÃO INDICA UNIDADES DE MEDIDA. VOCÊ DEVE INFERIR PELO VALOR.

    REGRAS DE OURO (INFERÊNCIA POR GRANDEZA):
    
    1. DIMENSÕES DE DUTO (Largura x Altura):
       - Padrão: "300x200", "50x30".
       - Assuma Milímetros (mm).

    2. COMPRIMENTO DO TRECHO (O Número Solto):
       - Você vai encontrar números soltos perto das dimensões (ex: "300x200 | 3000" ou "300x200 | 3").
       - REGRA DO MILÍMETRO (Se valor > 50): Ex: "3000", "1500", "540". Assuma que é MM e CONVERTA PARA METROS (3000mm = 3m).
       - REGRA DO METRO (Se valor <= 50 e > 0): Ex: "1.5", "3", "5". Assuma que é METROS.
       - CUIDADO COM TAGS: Inteiros muito pequenos (1, 2, 3) podem ser "Número do Duto".
         - Se ver "Duto 1 | 300x200", o comprimento é desconhecido (não use 1).
         - Se ver "300x200 | 3.0", o comprimento é 3m.
         - Na dúvida entre Tag e Comprimento, prefira números com casas decimais ou valores grandes (mm).

    3. IGNORE COTAS DE NÍVEL:
       - Valores como "2600", "2800" (Pé direito padrão) soltos, sem relação direta com o duto, devem ser ignorados.

    SAÍDA JSON:
    {{
        "dutos": [
            {{
                "dimensao": "300x200", 
                "largura_mm": 300, 
                "altura_mm": 200, 
                "comprimento_m": 3.0,
                "nota": "Lido como 3000mm ou 3m"
            }}
        ],
        "equipamentos": [
            {{ "item": "Fancoil", "quantidade": 2 }}
        ]
    }}
    """

    try:
        response = openai.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": f"Levantamento Bruto:\n\n{texto[:50000]}"} 
            ],
            temperature=0.0,
            response_format={"type": "json_object"}
        )
        return json.loads(response.choices[0].message.content)
    except Exception as e:
        return {"erro": str(e)}

# ==================================================
# 🖥️ INTERFACE PRINCIPAL
# ==================================================
st.title("🏗️ Leitor Pro V12 (Sem Unidades)")
st.markdown("Interpretação automática de **Metros vs Milímetros** baseada na grandeza do número.")

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
            with st.spinner("Extraindo textos..."):
                for entity in msp.query('TEXT MTEXT'):
                    if entity.dxf.text: raw_text.append(entity.dxf.text)
            
            # Limpeza mais permissiva (deixa passar números soltos)
            texto_proc = limpar_texto_cad(raw_text, tipo_leitura)
            
            st.info(f"Dados extraídos: {len(raw_text)} blocos.")
            
            if st.button("🚀 Calcular (Inferência de Unidades)", type="primary"):
                if not api_key:
                    st.error("Configure a API Key.")
                else:
                    with st.spinner("Analisando grandezas (mm vs m)..."):
                        dados = processar_ia(texto_proc, tipo_leitura)
                        
                        if "erro" in dados:
                            st.error(f"Erro IA: {dados['erro']}")
                        else:
                            # 1. PROCESSAMENTO
                            lista_dutos = dados.get("dutos", [])
                            tot_kg = 0
                            tot_m2 = 0
                            res_dutos = []
                            
                            for d in lista_dutos:
                                w = safe_float(d.get('largura_mm'))
                                h = safe_float(d.get('altura_mm'))
                                l = safe_float(d.get('comprimento_m'))
                                
                                # Trava de Segurança Final
                                if l > 150: # Se depois de tudo a IA achou que tem um duto de 200m, provavelmente leu cota de nível errado
                                    l = 0
                                    d['nota'] += " [IGNORADO: Valor Absurdo]"

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

                            # 2. EQUIPAMENTOS
                            lista_equip = dados.get("equipamentos", [])
                            res_equip = pd.DataFrame(lista_equip) if lista_equip else pd.DataFrame()
                            qtd_equip = sum([safe_float(e.get('quantidade')) for e in lista_equip])

                            # --- RESULTADOS ---
                            st.divider()
                            c1, c2, c3 = st.columns(3)
                            c1.metric("📦 Peso Total (Aço)", f"{tot_kg:,.1f} kg")
                            c2.metric("🧣 Área Isolamento", f"{tot_m2:,.1f} m²")
                            c3.metric("⚙️ Equipamentos", f"{int(qtd_equip)} un")
                            
                            # Abas
                            tab_d, tab_e = st.tabs(["📝 Memorial Dutos", "🏗️ Equipamentos"])
                            
                            with tab_d:
                                if res_dutos:
                                    st.dataframe(pd.DataFrame(res_dutos), use_container_width=True)
                                else:
                                    st.warning("Nenhum duto identificado.")
                            
                            with tab_e:
                                if not res_equip.empty:
                                    st.dataframe(res_equip, use_container_width=True)

                            # Download
                            meta = {
                                "Norma": "NBR 16401",
                                "Peso Total (kg)": tot_kg,
                                "Perda": f"{int(perda_corte*100)}%"
                            }
                            xlsx = gerar_excel_completo(pd.DataFrame(res_dutos), res_equip, meta)
                            st.download_button("📥 Baixar Excel", xlsx, "Levantamento_V12.xlsx")

    except Exception as e:
        st.error(f"Erro Crítico: {e}")
    finally:
        if os.path.exists(path_temp): os.remove(path_temp)
