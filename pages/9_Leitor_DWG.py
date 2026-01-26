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
st.set_page_config(page_title="Siarcon - Leitor Técnico CAD", page_icon="📐", layout="wide")

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

    st.subheader("📋 Parâmetros de Obra")
    
    # ESTRATÉGIA DE LEITURA (NOVO)
    tipo_leitura = st.radio(
        "Tipo de Desenho:",
        ("Contém Planta e Cortes (Filtrar)", "Apenas Planta Baixa (Somar Tudo)"),
        index=0,
        help="Se o desenho tiver muitos cortes/detalhes repetidos, use a primeira opção para não duplicar valores."
    )

    classe_pressao = st.selectbox(
        "Classe de Pressão:",
        ["Muito Baixa (até 250 Pa)", "Baixa (até 500 Pa)", "Média (até 1000 Pa)", "Alta (> 1000 Pa)"],
        index=1
    )
    
    perda_corte = st.slider("Perda de Material (%)", 0, 40, 10) / 100

# ==================================================
# 📐 TABELAS TÉCNICAS (SMACNA/NBR)
# ==================================================
def definir_bitola(maior_lado_mm, classe):
    # Lógica ajustada para economia e segurança
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
# 📝 GERADOR DE EXCEL
# ==================================================
def gerar_excel(df_dados, resumo_meta):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        # Aba Analítica
        df_dados.to_excel(writer, sheet_name='Memorial Analítico', index=False)
        wb = writer.book
        ws = writer.sheets['Memorial Analítico']
        
        # Estilos
        fmt_header = wb.add_format({'bold': True, 'bg_color': '#E0E0E0', 'border': 1})
        fmt_center = wb.add_format({'align': 'center'})
        
        for idx, col in enumerate(df_dados.columns):
            ws.write(0, idx, col, fmt_header)
            ws.set_column(idx, idx, 18, fmt_center)

        # Aba Resumo
        ws_res = wb.add_worksheet('Resumo Executivo')
        ws_res.write(0, 0, "Parâmetro", fmt_header)
        ws_res.write(0, 1, "Valor", fmt_header)
        
        row = 1
        for k, v in resumo_meta.items():
            ws_res.write(row, 0, k)
            ws_res.write(row, 1, v)
            row += 1
            
    output.seek(0)
    return output

# ==================================================
# 🔧 LIMPEZA INTELIGENTE DE CAD
# ==================================================
def limpar_texto_cad(lista_textos, modo_rigoroso):
    texto_limpo = []
    
    # 1. Palavras Proibidas (Carimbos, Legendas, Escalas)
    # Isso resolve o problema de ler a margem
    proibidos = [
        "LAYER", "VIEWPORT", "STANDARD", "ISO", "BYLAYER", 
        "COTAS", "MODEL", "LAYOUT", "PRANCHA", "FOLHA", 
        "DESENHO", "APROVADO", "DATA", "REVISÃO", "CLIENTE",
        "ESCALA", "SCALE", "1:50", "1:100", "1/50", "1/100", "1:25"
    ]
    
    padrao_cota_isolada = re.compile(r'^\d{1,3}$') # Números soltos como "100", "50" (geralmente cotas de parede)

    for item in lista_textos:
        t = str(item).strip()
        t_upper = t.upper()
        
        # Filtros iniciais
        if len(t) < 3: continue
        if any(p in t_upper for p in proibidos): continue
        if padrao_cota_isolada.match(t): continue # Ignora números isolados que confundem a IA
        
        texto_limpo.append(t)
        
    # Se modo rigoroso (tem cortes), remove duplicatas exatas para diminuir ruído
    if "Cortes" in modo_rigoroso:
        return "\n".join(list(dict.fromkeys(texto_limpo)))
    else:
        # Se for só planta, mantém tudo para contar peças
        return "\n".join(texto_limpo[:3500])

# ==================================================
# 🧠 CÉREBRO DA IA (PROMPT CORRIGIDO)
# ==================================================
def processar_ia(texto, tipo_leitura):
    if not api_key: return None

    # Define o comportamento com base na escolha do usuário
    comportamento = ""
    if "Cortes" in tipo_leitura:
        comportamento = """
        MODO DE FILTRAGEM DE CORTES ATIVO:
        Este texto contém redundâncias (Planta Baixa + Cortes A/B/C).
        1. PRIORIDADE: Identifique as dimensões apenas na PLANTA BAIXA.
        2. IGNORAR: Se uma medida aparecer repetida perto de palavras como "CORTE", "VISTA", "DETALHE", ignore-a.
        3. ESCALA: Ignore textos de escala (ex: 1:50) que possam parecer quantidades.
        """
    else:
        comportamento = """
        MODO DE SOMA TOTAL:
        O texto refere-se apenas à planta. Pode somar itens repetidos como quantidades adicionais.
        """

    prompt = f"""
    Você é um Engenheiro Orçamentista Sênior.
    {comportamento}

    Tarefa: Identificar TRECHOS DE DUTOS DE AR CONDICIONADO no texto bruto.
    
    Regras de Ouro:
    1. Identifique o padrão "Largura x Altura" (ex: 300x200, 50x30). Converta tudo para MM.
    2. Identifique o COMPRIMENTO linear (m). Se não houver unidade explícita e o número for pequeno (<100), assuma metros.
    3. Se encontrar o mesmo duto (ex: 300x200) várias vezes e estiver no 'Modo Cortes', conte apenas UMA VEZ o comprimento do trecho, a menos que fique claro que são trechos distintos.

    SAÍDA JSON OBRIGATÓRIA:
    {{
        "resumo_analise": "Explique brevemente o que foi considerado e o que foi descartado (ex: 'Ignorei as repetições dos cortes').",
        "dutos": [
            {{
                "dimensao": "300x200", 
                "largura_mm": 300, 
                "altura_mm": 200, 
                "comprimento_total_m": 10.5,
                "nota": "Rede Principal"
            }}
        ]
    }}
    """

    try:
        response = openai.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": f"Analise este levantamento:\n\n{texto[:35000]}"} 
            ],
            temperature=0.1, # Criatividade quase zero para ser exato
            response_format={"type": "json_object"}
        )
        return json.loads(response.choices[0].message.content)
    except Exception as e:
        return {"erro": str(e)}

# ==================================================
# 🖥️ INTERFACE PRINCIPAL
# ==================================================
st.title("📏 Leitor e Calculador de Dutos")
st.markdown("Extração de quantitativos CAD com algoritmo anti-duplicidade.")

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
            
            # 1. Extração
            raw_text = []
            with st.spinner("Lendo geometrias e textos..."):
                for entity in msp.query('TEXT MTEXT'):
                    if entity.dxf.text: raw_text.append(entity.dxf.text)
            
            # 2. Limpeza (Aplica Filtro de Margem/Escala)
            texto_proc = limpar_texto_cad(raw_text, tipo_leitura)
            
            # Layout Coluna Dividida (Anterior)
            col1, col2 = st.columns([1, 2])
            
            with col1:
                st.info(f"Leitura: {len(raw_text)} linhas brutas.")
                st.caption(f"Modo: {tipo_leitura}")
                with st.expander("Ver Texto Filtrado"):
                    st.text_area("", texto_proc, height=400)
            
            with col2:
                st.subheader("📊 Resultado do Cálculo")
                
                if not api_key:
                    st.error("Chave API ausente.")
                else:
                    if st.button("🚀 Processar Quantitativo", type="primary"):
                        with st.spinner("IA analisando dimensões e eliminando redundâncias..."):
                            dados = processar_ia(texto_proc, tipo_leitura)
                            
                            if "erro" in dados:
                                st.error(f"Erro: {dados['erro']}")
                            else:
                                lista = dados.get("dutos", [])
                                if lista:
                                    # Cálculos Matemáticos
                                    res_final = []
                                    tot_kg = 0
                                    tot_m2 = 0
                                    
                                    for item in lista:
                                        w = item.get('largura_mm', 0)
                                        h = item.get('altura_mm', 0)
                                        l = item.get('comprimento_total_m', 0)
                                        
                                        if w > 0 and h > 0:
                                            # Bitola
                                            maior = max(w, h)
                                            gauge = definir_bitola(maior, classe_pressao)
                                            
                                            # Área
                                            perim = 2 * (w/1000 + h/1000)
                                            area_tot = (perim * l) * (1 + perda_corte)
                                            
                                            # Peso
                                            peso = area_tot * calcular_peso_chapa(gauge)
                                            
                                            res_final.append({
                                                "Dimensão": f"{int(w)}x{int(h)}",
                                                "Comp. (m)": round(l, 2),
                                                "Bitola": f"#{gauge}",
                                                "Área (m²)": round(area_tot, 2),
                                                "Peso (kg)": round(peso, 2),
                                                "Nota": item.get("nota", "-")
                                            })
                                            tot_kg += peso
                                            tot_m2 += area_tot
                                    
                                    # Exibição
                                    st.success(f"✅ Análise Completa: {tot_kg:,.1f} kg")
                                    st.info(f"IA: {dados.get('resumo_analise')}")
                                    
                                    df = pd.DataFrame(res_final)
                                    st.dataframe(df, use_container_width=True)
                                    
                                    # Excel
                                    meta = {
                                        "Peso Total (kg)": tot_kg,
                                        "Área Total (m²)": tot_m2,
                                        "Classe": classe_pressao,
                                        "Estratégia": tipo_leitura
                                    }
                                    xlsx = gerar_excel(df, meta)
                                    st.download_button("📥 Baixar Planilha (.xlsx)", xlsx, "Memorial_Dutos.xlsx")
                                    
                                else:
                                    st.warning("Nenhum duto detectado com segurança.")

    except Exception as e:
        st.error(f"Erro ao ler arquivo: {e}")
    finally:
        if os.path.exists(path_temp): os.remove(path_temp)
