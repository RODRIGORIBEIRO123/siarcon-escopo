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
st.set_page_config(page_title="Siarcon - Leitor NBR 16401", page_icon="🇧🇷", layout="wide")

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
        help="Se o projeto tem cortes e detalhes repetidos, use a primeira opção."
    )

    classe_pressao = st.selectbox(
        "Classe de Pressão (NBR 16401-1):",
        ["Classe A (Baixa - até 500 Pa)", "Classe B (Média - até 1000 Pa)", "Classe C (Alta - até 2000 Pa)"],
        index=0
    )
    
    perda_corte = st.slider("Perda de Material / Retalhos (%)", 0, 40, 10) / 100

# ==================================================
# 📐 TABELAS TÉCNICAS (NBR 16401 - AÇO GALVANIZADO)
# ==================================================
def definir_bitola_nbr(maior_lado_mm, classe_txt):
    """
    Define a espessura da chapa conforme NBR 16401-1:2008 (Tabela B.2 e B.3).
    Dutos Retangulares de Aço Galvanizado.
    """
    # A NBR 16401 geralmente começa com 0.65mm (#24) para comercial/industrial.
    # O uso de #26 (0.50mm) é restrito a residenciais muito pequenos ou omitido na norma principal.
    
    # CLASSE A (Baixa Pressão - até 500 Pa)
    if "Classe A" in classe_txt:
        if maior_lado_mm <= 300: return 24  # 0.65mm (Norma pede min 0.65 para a maioria)
        if maior_lado_mm <= 750: return 24  # 0.65mm
        if maior_lado_mm <= 1200: return 22 # 0.80mm
        if maior_lado_mm <= 1500: return 20 # 0.95mm
        return 18                           # 1.25mm
    
    # CLASSE B (Média Pressão - até 1000 Pa)
    elif "Classe B" in classe_txt:
        if maior_lado_mm <= 300: return 24
        if maior_lado_mm <= 600: return 24
        if maior_lado_mm <= 1000: return 22
        if maior_lado_mm <= 1300: return 20
        return 18

    # CLASSE C (Alta Pressão)
    else:
        if maior_lado_mm <= 250: return 24
        if maior_lado_mm <= 500: return 22
        if maior_lado_mm <= 900: return 20
        return 18

def calcular_peso_chapa(bitola):
    # Pesos específicos aço galvanizado Z275 (kg/m²)
    # #26=0.50mm | #24=0.65mm | #22=0.80mm | #20=0.95mm | #18=1.25mm
    pesos = {
        26: 4.00, 
        24: 5.60, 
        22: 6.80, 
        20: 8.40, 
        18: 10.50,
        16: 12.90
    }
    return pesos.get(bitola, 6.0)

# ==================================================
# 📝 GERADOR DE EXCEL (NOVO LAYOUT)
# ==================================================
def gerar_excel_completo(df_dutos, df_equip, resumo_meta):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        
        # 1. ABA RESUMO
        wb = writer.book
        ws_res = wb.add_worksheet('Resumo Executivo')
        
        # Formatos
        fmt_title = wb.add_format({'bold': True, 'font_size': 14, 'font_color': '#1F497D'})
        fmt_header = wb.add_format({'bold': True, 'bg_color': '#D9E1F2', 'border': 1})
        fmt_cell = wb.add_format({'border': 1})
        fmt_num = wb.add_format({'border': 1, 'num_format': '#,##0.00'})
        
        ws_res.write(0, 0, "Resumo do Projeto (NBR 16401)", fmt_title)
        ws_res.write(2, 0, "Parâmetro", fmt_header)
        ws_res.write(2, 1, "Valor", fmt_header)
        
        row = 3
        for k, v in resumo_meta.items():
            ws_res.write(row, 0, k, fmt_cell)
            ws_res.write(row, 1, v, fmt_cell)
            row += 1
        ws_res.set_column(0, 0, 30)
        ws_res.set_column(1, 1, 20)

        # 2. ABA DUTOS
        if not df_dutos.empty:
            df_dutos.to_excel(writer, sheet_name='Memorial Dutos', index=False)
            ws_dutos = writer.sheets['Memorial Dutos']
            for idx, col in enumerate(df_dutos.columns):
                ws_dutos.write(0, idx, col, fmt_header)
            ws_dutos.set_column(0, 5, 15)

        # 3. ABA EQUIPAMENTOS
        if not df_equip.empty:
            df_equip.to_excel(writer, sheet_name='Lista Equipamentos', index=False)
            ws_equip = writer.sheets['Lista Equipamentos']
            for idx, col in enumerate(df_equip.columns):
                ws_equip.write(0, idx, col, fmt_header)
            ws_equip.set_column(0, 3, 25)
            
    output.seek(0)
    return output

# ==================================================
# 🔧 PRÉ-PROCESSAMENTO RIGOROSO (FILTRO DE LIXO)
# ==================================================
def limpar_texto_cad(lista_textos, modo_filtrar):
    texto_limpo = []
    
    # Padrões para remover
    proibidos = [
        "LAYER", "VIEWPORT", "STANDARD", "ISO", "BYLAYER", 
        "COTAS", "MODEL", "LAYOUT", "PRANCHA", "FOLHA", 
        "DESENHO", "APROVADO", "DATA", "REVISÃO", "CLIENTE",
        "ESCALA", "SCALE", "1:50", "1:100", "1/50", "1:20", 
        "NOME DO ARQUIVO", "PATH", "USER", "PLOT"
    ]
    
    # Regex para ignorar números que parecem coordenadas ou cotas de nível (ex: 3000, 150)
    # Só aceita números se tiverem 'x', 'm', '-', ou letras juntas.
    padrao_numero_solto = re.compile(r'^\d+$') 

    for item in lista_textos:
        t = str(item).strip()
        t_upper = t.upper()
        
        # 1. Filtro de Tamanho e Palavras Proibidas
        if len(t) < 2: continue
        if any(p in t_upper for p in proibidos): continue
        
        # 2. Filtro de Números Soltos (A CAUSA DO ERRO 33m)
        # Se for só "3" ou "300" sem unidade, ignora (provavelmente é tag ou cota)
        # Só aceita se tiver 'x' (300x200) ou 'm' (3m) ou 'L=' ou texto.
        eh_numero = padrao_numero_solto.match(t)
        tem_indicador = any(c in t_upper for c in ['X', 'M', 'L=', 'C=', 'DUTO', 'REDE', 'TR'])
        
        if eh_numero and not tem_indicador:
            continue # Joga fora números órfãos

        texto_limpo.append(t)
        
    # Remove duplicatas se o modo de filtro estiver ativo
    if "Filtrar" in modo_filtrar:
        lista_final = list(dict.fromkeys(texto_limpo))
    else:
        lista_final = texto_limpo[:4000]

    return " | ".join(lista_final)

# ==================================================
# 🧠 CÉREBRO DA IA (PROMPT NBR 16401)
# ==================================================
def processar_ia(texto, tipo_leitura):
    if not api_key: return None

    instrucao_cortes = ""
    if "Filtrar" in tipo_leitura:
        instrucao_cortes = "ATENÇÃO: O desenho tem Cortes e Vistas. IGNORE medidas repetidas. Use apenas a Planta Baixa."

    prompt = f"""
    Você é um Engenheiro de HVAC Sênior seguindo a NBR 16401.
    Analise o texto cru (separado por ' | ').
    {instrucao_cortes}

    REGRAS DE OURO PARA QUANTITATIVO (PARA EVITAR ERROS):
    1. DIMENSÕES: Procure "Largura x Altura" (ex: 300x200). Converta para mm.
    2. COMPRIMENTO: Procure números acompanhados de "m", "mts", "L=", "C=".
       - NÃO assuma que um número solto é metro. Se ver "Duto 3 | 300x200", o "3" é o nome do duto, não 3 metros.
       - Só considere comprimento se tiver unidade explícita ou contexto claro de medida linear.
    3. IGNORE COTAS DE NÍVEL: Números como "3000", "2800" costumam ser altura do forro, não comprimento. Ignore-os se não tiverem "L=" ou "m".

    TAREFA: Gere JSON com Dutos e Equipamentos.

    SAÍDA JSON:
    {{
        "resumo_analise": "Descreva o que foi considerado.",
        "dutos": [
            {{
                "dimensao": "300x200", 
                "largura_mm": 300, 
                "altura_mm": 200, 
                "comprimento_m": 3.0,
                "nota": "Rede Principal"
            }}
        ],
        "equipamentos": [
            {{ "item": "Split Cassete 36000", "quantidade": 2 }}
        ]
    }}
    """

    try:
        response = openai.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": f"Analise este texto cru:\n\n{texto[:45000]}"} 
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
st.title("🇧🇷 Leitor Técnico NBR 16401")
st.markdown("Cálculo de Dutos (Aço Galvanizado) conforme norma brasileira.")

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
            
            # Leitura e Limpeza
            raw_text = []
            with st.spinner("Processando geometrias..."):
                for entity in msp.query('TEXT MTEXT'):
                    if entity.dxf.text: raw_text.append(entity.dxf.text)
            
            # Aplica Filtro Rigoroso
            texto_proc = limpar_texto_cad(raw_text, tipo_leitura)
            
            st.info(f"Texto extraído e limpo: {len(raw_text)} blocos originais.")
            
            if st.button("🚀 Calcular conforme NBR 16401", type="primary"):
                if not api_key:
                    st.error("Configure a API Key na barra lateral.")
                else:
                    with st.spinner("Aplicando NBR 16401 e corrigindo leitura..."):
                        dados = processar_ia(texto_proc, tipo_leitura)
                        
                        if "erro" in dados:
                            st.error(f"Erro IA: {dados['erro']}")
                        else:
                            # 1. PROCESSAR DUTOS (NBR)
                            lista_dutos = dados.get("dutos", [])
                            tot_kg = 0
                            tot_m2 = 0
                            res_dutos = []
                            
                            for d in lista_dutos:
                                w, h = d.get('largura_mm', 0), d.get('altura_mm', 0)
                                l = d.get('comprimento_m', 0)
                                
                                # Filtro extra: Comprimento absurdo? (ex: > 100m num único trecho é provável erro de leitura de cota)
                                if l > 100: 
                                    d['nota'] += " [ALERTA: Comprimento suspeito]"
                                
                                if w > 0 and h > 0 and l > 0:
                                    maior = max(w, h)
                                    gauge = definir_bitola_nbr(maior, classe_pressao) # USA A NOVA FUNÇÃO NBR
                                    
                                    perim = 2 * (w/1000 + h/1000)
                                    area = (perim * l) * (1 + perda_corte)
                                    peso = area * calcular_peso_chapa(gauge)
                                    
                                    tot_kg += peso
                                    tot_m2 += area
                                    res_dutos.append({
                                        "Dimensão (mm)": f"{int(w)}x{int(h)}",
                                        "Comp. (m)": round(l, 2),
                                        "Bitola (NBR)": f"#{gauge}",
                                        "Área (m²)": round(area, 2),
                                        "Peso (kg)": round(peso, 2),
                                        "Obs": d.get("nota", "")
                                    })

                            # 2. PROCESSAR EQUIPAMENTOS
                            lista_equip = dados.get("equipamentos", [])
                            res_equip = pd.DataFrame(lista_equip) if lista_equip else pd.DataFrame()
                            qtd_equip = sum([e.get('quantidade', 0) for e in lista_equip])

                            # --- DASHBOARD ---
                            st.divider()
                            c1, c2, c3 = st.columns(3)
                            c1.metric("Peso Total (Aço)", f"{tot_kg:,.1f} kg")
                            c2.metric("Área Dutos", f"{tot_m2:,.1f} m²")
                            c3.metric("Equipamentos", f"{qtd_equip} un")
                            
                            st.caption(f"Nota da Engenharia IA: {dados.get('resumo_analise')}")

                            # --- VISUALIZAÇÃO ---
                            tab_d, tab_e = st.tabs(["📝 Memorial Dutos", "⚙️ Equipamentos"])
                            
                            with tab_d:
                                if res_dutos:
                                    df_d = pd.DataFrame(res_dutos)
                                    st.dataframe(df_d, use_container_width=True)
                                else:
                                    st.warning("Nenhum duto validado encontrado.")
                                    df_d = pd.DataFrame()
                            
                            with tab_e:
                                if not res_equip.empty:
                                    st.dataframe(res_equip, use_container_width=True)
                                else:
                                    st.info("Nenhum equipamento listado.")

                            # --- EXCEL DOWNLOAD ---
                            meta = {
                                "Norma Aplicada": "ABNT NBR 16401-1:2008",
                                "Classe": classe_pressao,
                                "Peso Total (kg)": tot_kg,
                                "Área Total (m²)": tot_m2,
                                "Perda Considerada": f"{int(perda_corte*100)}%"
                            }
                            
                            xlsx = gerar_excel_completo(df_d, res_equip, meta)
                            
                            st.download_button(
                                "📥 Baixar Planilha NBR 16401 (.xlsx)",
                                xlsx,
                                "Levantamento_NBR16401.xlsx",
                                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                            )

    except Exception as e:
        st.error(f"Erro: {e}")
    finally:
        if os.path.exists(path_temp): os.remove(path_temp)
