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
st.set_page_config(page_title="Siarcon - Leitor Master", page_icon="🏗️", layout="wide")

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

    st.subheader("📋 Parâmetros de Leitura")
    
    tipo_leitura = st.radio(
        "Estratégia de Desenho:",
        ("Contém Planta e Cortes (Filtrar)", "Apenas Planta Baixa (Somar Tudo)"),
        index=0,
        help="Use 'Filtrar' para ignorar as repetições dos cortes e detalhes."
    )

    classe_pressao = st.selectbox(
        "Classe de Pressão:",
        ["Muito Baixa (até 250 Pa)", "Baixa (até 500 Pa)", "Média (até 1000 Pa)", "Alta (> 1000 Pa)"],
        index=1
    )
    
    perda_corte = st.slider("Perda de Material / Retalhos (%)", 0, 40, 10) / 100

# ==================================================
# 📐 TABELAS TÉCNICAS (SMACNA/NBR)
# ==================================================
def definir_bitola(maior_lado_mm, classe):
    if "250 Pa" in classe:
        if maior_lado_mm <= 450: return 26
        if maior_lado_mm <= 900: return 24
        if maior_lado_mm <= 1500: return 22
        return 20
    elif "500 Pa" in classe:
        if maior_lado_mm <= 300: return 26
        if maior_lado_mm <= 750: return 24
        if maior_lado_mm <= 1400: return 22
        return 20
    elif "Média" in classe:
        if maior_lado_mm <= 250: return 26
        if maior_lado_mm <= 600: return 24
        if maior_lado_mm <= 1200: return 22
        return 20
    else:
        if maior_lado_mm <= 200: return 24
        if maior_lado_mm <= 500: return 22
        if maior_lado_mm <= 1000: return 20
        return 18

def calcular_peso_chapa(bitola):
    # kg/m² aproximado para aço galvanizado
    pesos = {26: 4.20, 24: 5.60, 22: 6.80, 20: 8.40, 18: 10.50}
    return pesos.get(bitola, 6.0)

# ==================================================
# 📝 GERADOR DE EXCEL MULTI-ABA
# ==================================================
def gerar_excel_completo(df_dutos, df_equip, resumo_meta):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        
        # 1. ABA RESUMO
        wb = writer.book
        ws_res = wb.add_worksheet('Resumo Executivo')
        fmt_header = wb.add_format({'bold': True, 'bg_color': '#4F81BD', 'font_color': 'white', 'border': 1})
        fmt_dado = wb.add_format({'border': 1})
        
        ws_res.write(0, 0, "Item", fmt_header)
        ws_res.write(0, 1, "Valor", fmt_header)
        
        row = 1
        for k, v in resumo_meta.items():
            ws_res.write(row, 0, k, fmt_dado)
            ws_res.write(row, 1, v, fmt_dado)
            row += 1
        ws_res.set_column(0, 0, 25)
        ws_res.set_column(1, 1, 15)

        # 2. ABA DUTOS
        if not df_dutos.empty:
            df_dutos.to_excel(writer, sheet_name='Memorial Dutos', index=False)
            ws_dutos = writer.sheets['Memorial Dutos']
            for idx, col in enumerate(df_dutos.columns):
                ws_dutos.write(0, idx, col, fmt_header)
                ws_dutos.set_column(idx, idx, 15)

        # 3. ABA EQUIPAMENTOS
        if not df_equip.empty:
            df_equip.to_excel(writer, sheet_name='Lista Equipamentos', index=False)
            ws_equip = writer.sheets['Lista Equipamentos']
            for idx, col in enumerate(df_equip.columns):
                ws_equip.write(0, idx, col, fmt_header)
                ws_equip.set_column(idx, idx, 25)
            
    output.seek(0)
    return output

# ==================================================
# 🔧 LIMPEZA DE TEXTO (CORREÇÃO DE CONCATENAÇÃO)
# ==================================================
def limpar_texto_cad(lista_textos, modo_rigoroso):
    texto_limpo = []
    
    # Lista negra de palavras para evitar leitura de margem/carimbo
    proibidos = [
        "LAYER", "VIEWPORT", "STANDARD", "ISO", "BYLAYER", 
        "COTAS", "MODEL", "LAYOUT", "PRANCHA", "FOLHA", 
        "DESENHO", "APROVADO", "DATA", "REVISÃO", "CLIENTE",
        "ESCALA", "SCALE", "1:50", "1:100", "1/50", "1:20", "NOME DO ARQUIVO"
    ]
    
    # Regex para identificar números isolados que parecem tags (ex: "1", "02")
    # Se o texto for só um número pequeno, a gente descarta se não tiver unidade perto na IA
    
    for item in lista_textos:
        t = str(item).strip()
        t_upper = t.upper()
        
        if len(t) < 2: continue # Ignora letras soltas
        if any(p in t_upper for p in proibidos): continue
        
        texto_limpo.append(t)
        
    # Se modo cortes ativo, remove duplicatas exatas
    if "Cortes" in modo_rigoroso:
        lista_final = list(dict.fromkeys(texto_limpo))
    else:
        lista_final = texto_limpo[:4000]

    # TRUQUE: Usar " | " como separador visual para a IA não juntar "Duto 3" com "3m" virando "33m"
    return " | ".join(lista_final)

# ==================================================
# 🧠 CÉREBRO DA IA (PROMPT REFINADO)
# ==================================================
def processar_ia(texto, tipo_leitura):
    if not api_key: return None

    instrucao_cortes = ""
    if "Cortes" in tipo_leitura:
        instrucao_cortes = "ATENÇÃO: O desenho tem Cortes e Vistas. IGNORE medidas repetidas nestas áreas. Use apenas a Planta Baixa."

    prompt = f"""
    Você é um Engenheiro Sênior de Orçamentos (MEP). Analise os textos extraídos de um CAD.
    Os textos estão separados por " | ".
    {instrucao_cortes}

    TAREFA 1: DUTOS E QUANTITATIVOS
    - Encontre padrões "Largura x Altura" (ex: 300x200). Converta para mm.
    - Encontre COMPRIMENTO (m). 
    - CRÍTICO: Cuidado com concatenação. Se ver "Duto 3 | 3.00", o comprimento é 3, NÃO 33.
    - Ignore números inteiros pequenos (1, 2, 3) isolados, pois geralmente são TAGS ou números de peças, não metros. Só aceite como metro se tiver unidade (m) ou for dimensional lógico.

    TAREFA 2: LISTA DE EQUIPAMENTOS
    - Identifique itens como: Fancoil, Split, Cassete, VRF, Chiller, Bomba, Ventilador, Exaustor, Quadro Elétrico (QDL/QD).
    - Conte as quantidades.

    SAÍDA JSON OBRIGATÓRIA:
    {{
        "resumo_analise": "Comentário sobre a qualidade da leitura.",
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
            {{
                "item": "Fancoil 5TR",
                "quantidade": 2,
                "detalhe": "Modelo Teto"
            }}
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
            temperature=0.0, # Zero criatividade para máxima precisão matemática
            response_format={"type": "json_object"}
        )
        return json.loads(response.choices[0].message.content)
    except Exception as e:
        return {"erro": str(e)}

# ==================================================
# 🖥️ INTERFACE PRINCIPAL
# ==================================================
st.title("📏 Leitor Técnico Master (Dutos + Equipamentos)")
st.markdown("Extração precisa com separação de **Planta vs Cortes** e listagem de equipamentos.")

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
            
            # Leitura
            raw_text = []
            with st.spinner("Lendo geometrias e separando textos..."):
                for entity in msp.query('TEXT MTEXT'):
                    if entity.dxf.text: raw_text.append(entity.dxf.text)
            
            # Limpeza com separador visual
            texto_proc = limpar_texto_cad(raw_text, tipo_leitura)
            
            st.info(f"Leitura: {len(raw_text)} blocos de texto processados.")
            
            if st.button("🚀 Processar Leitura Fina", type="primary"):
                if not api_key:
                    st.error("Configure a API Key na barra lateral.")
                else:
                    with st.spinner("IA analisando dimensões, corrigindo erros de leitura e listando equipamentos..."):
                        dados = processar_ia(texto_proc, tipo_leitura)
                        
                        if "erro" in dados:
                            st.error(f"Erro Crítico: {dados['erro']}")
                        else:
                            # --- PROCESSAMENTO DOS DADOS ---
                            
                            # 1. DUTOS
                            lista_dutos = dados.get("dutos", [])
                            tot_kg = 0
                            tot_m2 = 0
                            res_dutos = []
                            
                            for d in lista_dutos:
                                w, h = d.get('largura_mm', 0), d.get('altura_mm', 0)
                                l = d.get('comprimento_m', 0)
                                if w > 0 and h > 0 and l > 0:
                                    gauge = definir_bitola(max(w, h), classe_pressao)
                                    perim = 2 * (w/1000 + h/1000)
                                    area = (perim * l) * (1 + perda_corte)
                                    peso = area * calcular_peso_chapa(gauge)
                                    
                                    tot_kg += peso
                                    tot_m2 += area
                                    res_dutos.append({
                                        "Dimensão": f"{int(w)}x{int(h)}",
                                        "Comp. (m)": round(l, 2),
                                        "Bitola": f"#{gauge}",
                                        "Área Isol. (m²)": round(area, 2),
                                        "Peso (kg)": round(peso, 2),
                                        "Nota": d.get("nota", "")
                                    })

                            # 2. EQUIPAMENTOS
                            lista_equip = dados.get("equipamentos", [])
                            tot_equip = sum([e.get('quantidade', 0) for e in lista_equip])
                            res_equip = []
                            if lista_equip:
                                res_equip = pd.DataFrame(lista_equip)

                            # --- LAYOUT DE MÉTRICAS (VOLTOU!) ---
                            st.divider()
                            c1, c2, c3 = st.columns(3)
                            
                            c1.metric("📦 Peso Total Dutos", f"{tot_kg:,.1f} kg", help="Considerando perda configurada")
                            c2.metric("🧣 Área Isolamento", f"{tot_m2:,.1f} m²", help="Equivalente à área de chapa + perda")
                            c3.metric("⚙️ Equipamentos", f"{tot_equip} un", help="Total de itens identificados")
                            
                            st.caption(f"Análise da IA: {dados.get('resumo_analise')}")

                            # --- ABAS DE DETALHE ---
                            tab1, tab2 = st.tabs(["📝 Memorial de Dutos", "🏗️ Lista de Equipamentos"])
                            
                            with tab1:
                                if res_dutos:
                                    df_dutos = pd.DataFrame(res_dutos)
                                    st.dataframe(df_dutos, use_container_width=True)
                                else:
                                    st.warning("Nenhum duto identificado.")
                                    df_dutos = pd.DataFrame()

                            with tab2:
                                if not res_equip.empty:
                                    st.dataframe(res_equip, use_container_width=True)
                                else:
                                    st.info("Nenhum equipamento de grande porte identificado (Fancoil, Split, etc).")
                                    df_equip = pd.DataFrame()

                            # --- EXPORTAÇÃO EXCEL COMPLETO ---
                            meta_dados = {
                                "Peso Total (kg)": tot_kg,
                                "Área Isolamento (m²)": tot_m2,
                                "Qtd Equipamentos": tot_equip,
                                "Pressão": classe_pressao,
                                "Perda": f"{int(perda_corte*100)}%"
                            }
                            
                            excel_file = gerar_excel_completo(df_dutos, res_equip if isinstance(res_equip, pd.DataFrame) else pd.DataFrame(), meta_dados)
                            
                            st.download_button(
                                label="📥 Baixar Relatório Completo (.xlsx)",
                                data=excel_file,
                                file_name="Relatorio_Obra_Completo.xlsx",
                                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                            )

    except Exception as e:
        st.error(f"Erro ao ler arquivo: {e}")
    finally:
        if os.path.exists(path_temp): os.remove(path_temp)
