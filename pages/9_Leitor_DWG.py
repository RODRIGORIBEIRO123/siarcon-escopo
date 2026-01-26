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
import math

# Configuração da Página
st.set_page_config(page_title="Siarcon - Leitor Geométrico V16", page_icon="📐", layout="wide")

# ==================================================
# 🔧 FUNÇÕES MATEMÁTICAS E GEOMÉTRICAS
# ==================================================
def safe_float(valor):
    try:
        if valor is None: return 0.0
        val_str = str(valor).replace('mm', '').strip().replace(',', '.')
        nums = re.findall(r"[-+]?\d*\.\d+|\d+", val_str)
        if nums: return float(nums[0])
        return 0.0
    except:
        return 0.0

def calcular_distancia(p1, p2):
    return math.sqrt((p1[0] - p2[0])**2 + (p1[1] - p2[1])**2)

def ler_geometria_proxima(msp, coordenadas_texto, limite_busca=500):
    """
    Procura a linha ou polilinha mais próxima do texto e retorna seu comprimento.
    limite_busca: Raio máximo para procurar uma linha (em unidades do CAD).
    """
    menor_distancia = float('inf')
    comprimento_encontrado = 0.0
    
    # Varre linhas simples (LINE)
    for line in msp.query('LINE'):
        start = line.dxf.start
        end = line.dxf.end
        # Ponto médio da linha
        mid_x = (start.x + end.x) / 2
        mid_y = (start.y + end.y) / 2
        
        dist = calcular_distancia((mid_x, mid_y), coordenadas_texto)
        
        if dist < menor_distancia and dist < limite_busca:
            menor_distancia = dist
            # Comprimento da linha
            comprimento_encontrado = calcular_distancia(start, end)

    # Varre polilinhas (LWPOLYLINE) - Comuns em dutos
    for poly in msp.query('LWPOLYLINE'):
        if len(poly) > 0:
            # Pega o primeiro ponto como referência aproximada (ou calcular centróide seria melhor, mas mais lento)
            p_ref = poly[0]
            dist = calcular_distancia((p_ref[0], p_ref[1]), coordenadas_texto)
            
            # Se o texto estiver perto do início da polilinha
            if dist < menor_distancia and dist < limite_busca:
                menor_distancia = dist
                # Calcula perímetro total da polilinha
                length = 0
                points = poly.get_points()
                for i in range(len(points) - 1):
                    length += calcular_distancia(points[i], points[i+1])
                comprimento_encontrado = length

    return comprimento_encontrado

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
    
    st.subheader("📐 Escala e Geometria")
    unidade_cad = st.selectbox(
        "Unidade do Desenho CAD:",
        [
            "Milímetros (1u = 1mm)", 
            "Centímetros (1u = 1cm)", 
            "Metros (1u = 1m)"
        ],
        index=0,
        help="Se o duto tem 2m e no CAD a linha mede 2000, escolha Milímetros."
    )
    
    raio_busca = st.number_input(
        "Raio de Busca Geométrica:", 
        value=500, 
        help="Distância máxima entre o TEXTO e a LINHA do duto para considerar que são o mesmo conjunto."
    )

    st.subheader("🛡️ Travas")
    max_len_segmento = st.number_input("Máx. Comprimento (m):", value=20.0)
    
    st.subheader("📋 NBR 16401")
    classe_pressao = st.selectbox("Classe de Pressão:", ["Classe A (Baixa)", "Classe B (Média)", "Classe C (Alta)"], index=0)
    perda_corte = st.slider("Perda (%)", 0, 40, 10) / 100

# ==================================================
# 🔧 PROCESSAMENTO
# ==================================================
def calcular_peso_chapa(bitola):
    pesos = {26: 4.00, 24: 5.60, 22: 6.80, 20: 8.40, 18: 10.50}
    return pesos.get(int(safe_float(bitola)), 6.0)

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

def limpar_texto_cad(lista_entidades):
    """Extrai texto e suas coordenadas para associação geométrica"""
    texto_limpo = []
    dados_geo = []
    
    proibidos = ["LAYER", "VIEWPORT", "COTAS", "MODEL", "LAYOUT", "ESCALA", "SCALE"]
    
    for item in lista_entidades:
        t = str(item.dxf.text).strip()
        
        if len(t) < 2: continue
        if any(p in t.upper() for p in proibidos): continue
        
        # Ignora coordenadas UTM gigantes que não sejam texto de duto
        try:
            val = float(t.replace(',','.'))
            if val > 50000: continue 
        except:
            pass
            
        # Guarda o texto e sua posição (insert point)
        texto_limpo.append(t)
        dados_geo.append({
            "texto": t,
            "coords": (item.dxf.insert.x, item.dxf.insert.y)
        })

    return " | ".join(texto_limpo), dados_geo

def processar_ia(texto, dados_geo, msp, raio_busca, unidade_cad):
    if not api_key: return None

    # Fator de conversão da geometria (CAD -> Metros)
    fator_escala = 0.001 if "Milímetros" in unidade_cad else (0.01 if "Centímetros" in unidade_cad else 1.0)

    prompt = f"""
    Você é um Engenheiro HVAC. Analise o texto do CAD (separado por ' | ').
    
    1. VAZÃO: Números entre parênteses "(34.000)" são VAZÃO. IGNORE-OS como medida.
    2. DIMENSÕES: Padrão "1.300x700" ou "500x400".
    3. COMPRIMENTO: 
       - Se houver texto explícito (ex: "L=2"), use-o.
       - Se NÃO houver texto, retorne 0 (o sistema vai medir a geometria depois).

    SAÍDA JSON:
    {{
        "dutos": [
            {{ "dimensao_original": "1.300x700", "largura_mm": 1300, "altura_mm": 700, "comprimento_texto": 0 }}
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
                {"role": "user", "content": f"Texto:\n\n{texto[:50000]}"} 
            ],
            temperature=0.0,
            response_format={"type": "json_object"}
        )
        dados_ia = json.loads(response.choices[0].message.content)
        
        # --- PÓS-PROCESSAMENTO GEOMÉTRICO (A MÁGICA) ---
        lista_dutos = dados_ia.get("dutos", [])
        
        for duto in lista_dutos:
            dim_orig = duto.get("dimensao_original", "")
            comp_txt = safe_float(duto.get("comprimento_texto", 0))
            
            # Se a IA não achou texto de comprimento (comum), vamos medir o desenho!
            if comp_txt == 0:
                # 1. Achar onde está esse texto no desenho
                coords_texto = None
                for g in dados_geo:
                    if g["texto"] in dim_orig: # Match aproximado
                        coords_texto = g["coords"]
                        break
                
                # 2. Se achamos o texto, procuramos a linha mais próxima
                if coords_texto:
                    comp_geo_raw = ler_geometria_proxima(msp, coords_texto, raio_busca)
                    # Aplica escala (Ex: leu 3000mm -> vira 3m)
                    duto["comprimento_m"] = comp_geo_raw * fator_escala
                    duto["nota"] = "Medido via Geometria (Escala)"
                else:
                    duto["comprimento_m"] = 0
                    duto["nota"] = "Não medido (Texto não localizado)"
            else:
                duto["comprimento_m"] = comp_txt
                duto["nota"] = "Lido do Texto"

        return dados_ia

    except Exception as e:
        return {"erro": str(e)}

# ==================================================
# 🖥️ INTERFACE
# ==================================================
st.title("📐 Leitor Geométrico V16 (Texto + Linhas)")
st.markdown("Combina **Inteligência Artificial** (para ler o que é o duto) com **Matemática** (para medir o comprimento das linhas próximas).")

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
            entidades_texto = []
            with st.spinner("Lendo Texto e Geometria..."):
                for entity in msp.query('TEXT MTEXT'):
                    if entity.dxf.text: entidades_texto.append(entity)
            
            # Extrai texto e coordenadas
            texto_full, geo_data = limpar_texto_cad(entidades_texto)
            
            st.info(f"Dados encontrados: {len(entidades_texto)} anotações de texto.")
            
            if st.button("🚀 Calcular (Medir Desenho)", type="primary"):
                if not api_key:
                    st.error("Sem API Key.")
                else:
                    with st.spinner("IA identificando dutos e Algoritmo medindo linhas próximas..."):
                        # Passamos o MSP (Model Space) para a função medir as linhas
                        dados = processar_ia(texto_full, geo_data, msp, raio_busca, unidade_cad)
                        
                        if "erro" in dados:
                            st.error(f"Erro: {dados['erro']}")
                        else:
                            # RESULTADOS
                            lista_dutos = dados.get("dutos", [])
                            res_dutos = []
                            tot_kg = 0
                            tot_m2 = 0
                            
                            for d in lista_dutos:
                                w = safe_float(d.get('largura_mm'))
                                h = safe_float(d.get('altura_mm'))
                                l = safe_float(d.get('comprimento_m'))
                                
                                # Trava Máxima
                                if l > max_len_segmento:
                                    d['nota'] += f" [CORTE > {max_len_segmento}m]"
                                    l = 0

                                if w > 0 and h > 0:
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
                            
                            # EQUIPAMENTOS (RESTAURADO)
                            lista_equip = dados.get("equipamentos", [])
                            res_equip = pd.DataFrame(lista_equip) if lista_equip else pd.DataFrame()
                            qtd_equip = sum([safe_float(e.get('quantidade', 0)) for e in lista_equip])

                            # EXIBIÇÃO
                            c1, c2, c3 = st.columns(3)
                            c1.metric("Peso Total", f"{tot_kg:,.1f} kg")
                            c2.metric("Área Isol.", f"{tot_m2:,.1f} m²")
                            c3.metric("Equipamentos", f"{int(qtd_equip)} un")
                            
                            tab1, tab2 = st.tabs(["Dutos", "Equipamentos"])
                            with tab1:
                                if res_dutos: st.dataframe(pd.DataFrame(res_dutos), use_container_width=True)
                                else: st.warning("Nenhum duto medido.")
                            with tab2:
                                if not res_equip.empty: st.dataframe(res_equip, use_container_width=True)
                                else: st.info("Sem equipamentos.")
                                
                            meta = {"Peso Total": tot_kg, "Escala": unidade_cad}
                            xlsx = gerar_excel_completo(pd.DataFrame(res_dutos), res_equip, meta)
                            st.download_button("📥 Baixar Excel", xlsx, "Levantamento_V16.xlsx")

    except Exception as e:
        st.error(f"Erro: {e}")
    finally:
        if os.path.exists(path_temp): os.remove(path_temp)
