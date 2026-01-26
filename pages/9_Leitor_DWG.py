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
st.set_page_config(page_title="Siarcon - Leitor NBR 16401 (V11)", page_icon="🛡️", layout="wide")

# ==================================================
# 🔧 FUNÇÕES DE SEGURANÇA (CORREÇÃO DE BUGS)
# ==================================================
def safe_float(valor):
    """Converte qualquer coisa para float. Se falhar ou for None, retorna 0.0"""
    try:
        if valor is None:
            return 0.0
        # Remove caracteres não numéricos comuns (ex: 'm', 'kg') exceto ponto
        limpo = str(valor).replace(',', '.').lower().strip()
        # Extrai apenas números e ponto
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
        help="Use 'Filtrar' para ignorar textos que parecem estar em cortes/detalhes."
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
# 🔧 LIMPEZA DE TEXTO (FILTRO DE ALUCINAÇÃO)
# ==================================================
def limpar_texto_cad(lista_textos, modo_filtrar):
    texto_limpo = []
    
    proibidos = [
        "LAYER", "VIEWPORT", "STANDARD", "ISO", "BYLAYER", 
        "COTAS", "MODEL", "LAYOUT", "PRANCHA", "FOLHA", 
        "DESENHO", "APROVADO", "DATA", "REVISÃO", "CLIENTE",
        "ESCALA", "SCALE", "1:50", "1:100", "1/50", "1:20", 
        "NOME DO ARQUIVO", "PATH", "USER", "PLOT"
    ]
    
    padrao_numero_solto = re.compile(r'^\d+$') 

    for item in lista_textos:
        t = str(item).strip()
        t_upper = t.upper()
        
        if len(t) < 2: continue
        if any(p in t_upper for p in proibidos): continue
        
        # Filtro Rigoroso: Números Soltos
        # Se for um número solto (ex: "300") SEM contexto de unidade ou dimensão, IGNORAR.
        # Só aceita se tiver 'x', 'm', 'cm', 'L=', 'C=' ou for texto.
        eh_numero = padrao_numero_solto.match(t)
        tem_indicador = any(c in t_upper for c in ['X', 'M', 'L=', 'C=', 'DUTO', 'REDE', 'TR', 'CAP', 'BOLSA'])
        
        if eh_numero and not tem_indicador:
            continue 

        texto_limpo.append(t)
        
    if "Filtrar" in modo_filtrar:
        lista_final = list(dict.fromkeys(texto_limpo))
    else:
        lista_final = texto_limpo[:5000]

    return " | ".join(lista_final)

# ==================================================
# 🧠 CÉREBRO DA IA (PROMPT BLINDADO)
# ==================================================
def processar_ia(texto, tipo_leitura):
    if not api_key: return None

    instrucao_cortes = ""
    if "Filtrar" in tipo_leitura:
        instrucao_cortes = "ATENÇÃO: O desenho tem Cortes e Vistas. IGNORE medidas repetidas nestas áreas. Use apenas a Planta Baixa."

    prompt = f"""
    Você é um Engenheiro de HVAC Sênior. Siga a NBR 16401.
    Analise o texto cru (separado por ' | ').
    {instrucao_cortes}

    REGRAS CRÍTICAS DE LEITURA (ZERO ALUCINAÇÃO):
    
    1. DIMENSÕES: Identifique "Largura x Altura" (ex: 300x200).
    
    2. COMPRIMENTO (O MAIS IMPORTANTE):
       - Você SÓ PODE extrair o comprimento se encontrar um número com UNIDADE EXPLÍCITA ("m", "mts", "cm") ou prefixo ("L=", "C=").
       - EXEMPLO CORRETO: "300x200 | L=3.5" -> Comprimento = 3.5m.
       - EXEMPLO CORRETO: "Duto 30x20 | 5m" -> Comprimento = 5.0m.
       - EXEMPLO ERRADO: "Duto 3 | 300x200". O "3" é TAG. Comprimento = 0 (Não invente!).
       - Se houver números soltos (ex: "3000") sem "L=" ou "m", assuma que é cota de nível ou tag e IGNORE.
    
    3. EQUIPAMENTOS:
       - Liste Fancoil, Split, Cassete, VRF, Exaustor, Caixas de Ventilação.

    SAÍDA JSON:
    {{
        "dutos": [
            {{
                "largura_mm": 300, 
                "altura_mm": 200, 
                "comprimento_m": 3.5,
                "nota": "L=3.5 identificado"
            }}
        ],
        "equipamentos": [
            {{ "item": "Split Cassete 36k", "quantidade": 2 }}
        ],
        "log_erro": "Liste aqui se ignorou números confusos."
    }}
    """

    try:
        response = openai.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": f"Analise este texto cru:\n\n{texto[:50000]}"} 
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
st.title("🛡️ Leitor Técnico NBR 16401 (V11)")
st.markdown("Extração blindada contra erros de leitura de texto solto.")

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
            with st.spinner("Processando geometrias..."):
                for entity in msp.query('TEXT MTEXT'):
                    if entity.dxf.text: raw_text.append(entity.dxf.text)
            
            texto_proc = limpar_texto_cad(raw_text, tipo_leitura)
            
            st.info(f"Elementos de texto analisados: {len(raw_text)}")
            
            if st.button("🚀 Calcular (Modo Seguro)", type="primary"):
                if not api_key:
                    st.error("Configure a API Key.")
                else:
                    with st.spinner("Analisando com filtro de coerência..."):
                        dados = processar_ia(texto_proc, tipo_leitura)
                        
                        if "erro" in dados:
                            st.error(f"Erro IA: {dados['erro']}")
                        else:
                            # 1. PROCESSAMENTO DUTOS
                            lista_dutos = dados.get("dutos", [])
                            tot_kg = 0
                            tot_m2 = 0
                            res_dutos = []
                            
                            for d in lista_dutos:
                                # AQUI ESTAVA O ERRO DE COMPARACAO - AGORA USAMOS SAFE_FLOAT
                                w = safe_float(d.get('largura_mm'))
                                h = safe_float(d.get('altura_mm'))
                                l = safe_float(d.get('comprimento_m'))
                                
                                # Correção automática: Se comprimento vier em mm (ex: 3000), vira 3m
                                if l > 50: # Dificilmente um trecho único tem mais de 50m
                                    l = l / 1000
                                    d['nota'] += " (Conv. mm->m)"
                                
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

                            # 2. PROCESSAMENTO EQUIPAMENTOS
                            lista_equip = dados.get("equipamentos", [])
                            res_equip = pd.DataFrame(lista_equip) if lista_equip else pd.DataFrame()
                            qtd_equip = sum([safe_float(e.get('quantidade')) for e in lista_equip])

                            # --- LAYOUT CARDS (RESTAURADO) ---
                            st.divider()
                            c1, c2, c3 = st.columns(3)
                            c1.metric("📦 Peso Total (Aço)", f"{tot_kg:,.1f} kg")
                            c2.metric("🧣 Área Isolamento", f"{tot_m2:,.1f} m²")
                            c3.metric("⚙️ Equipamentos", f"{int(qtd_equip)} un")
                            
                            if dados.get("log_erro"):
                                st.warning(f"Log de Filtragem: {dados.get('log_erro')}")

                            # --- VISUALIZAÇÃO ---
                            tab_d, tab_e = st.tabs(["📝 Memorial de Cálculo", "🏗️ Equipamentos"])
                            
                            with tab_d:
                                if res_dutos:
                                    st.dataframe(pd.DataFrame(res_dutos), use_container_width=True)
                                else:
                                    st.warning("Nenhum duto com comprimento explícito ('L=' ou 'm') foi encontrado.")
                            
                            with tab_e:
                                if not res_equip.empty:
                                    st.dataframe(res_equip, use_container_width=True)

                            # --- DOWNLOAD ---
                            meta = {
                                "Norma": "NBR 16401",
                                "Peso Total (kg)": tot_kg,
                                "Área (m²)": tot_m2,
                                "Perda": f"{int(perda_corte*100)}%"
                            }
                            xlsx = gerar_excel_completo(pd.DataFrame(res_dutos), res_equip, meta)
                            st.download_button("📥 Baixar Excel", xlsx, "Levantamento_V11.xlsx")

    except Exception as e:
        st.error(f"Erro Crítico: {e}")
    finally:
        if os.path.exists(path_temp): os.remove(path_temp)
