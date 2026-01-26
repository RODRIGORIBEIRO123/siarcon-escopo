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
st.set_page_config(page_title="Siarcon - Leitor V19 (Final)", page_icon="🏗️", layout="wide")

# ==================================================
# 🔧 FUNÇÕES MATEMÁTICAS
# ==================================================
def safe_float(valor):
    try:
        if valor is None: return 0.0
        val_str = str(valor).upper().replace('MM', '').strip().replace(',', '.')
        nums = re.findall(r"[-+]?\d*\.\d+|\d+", val_str)
        if nums: return float(nums[0])
        return 0.0
    except:
        return 0.0

def calcular_distancia(p1, p2):
    return math.sqrt((p1[0] - p2[0])**2 + (p1[1] - p2[1])**2)

def normalizar_texto(texto):
    return str(texto).replace('.', '').replace(' ', '').lower().strip()

# ==================================================
# 🔑 CONFIGURAÇÃO
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
    st.subheader("📐 Geometria")
    
    unidade_cad = st.selectbox(
        "Unidade do CAD:", 
        ["Milímetros (1u=1mm)", "Metros (1u=1m)"], 
        index=0
    )
    
    raio_busca = st.number_input(
        "Raio de Busca (mm):", 
        value=2000, 
        step=500,
        help="Aumente se o texto estiver longe da linha do duto."
    )
    
    st.subheader("🛡️ Filtros")
    max_len = st.number_input("Trava Máx. (m):", value=50.0)
    
    # FATOR DE CORREÇÃO MANUAL
    st.caption("Calibração Fina:")
    fator_ajuste = st.number_input("Multiplicador de Comprimento:", value=1.0, step=0.1, help="Use 1.0 para normal. Se precisar ajustar, mude aqui.")
    
    st.subheader("📋 NBR 16401")
    classe_pressao = st.selectbox("Pressão:", ["Classe A (Baixa)", "Classe B (Média)", "Classe C (Alta)"], index=0)
    perda_corte = st.slider("Perda (%)", 0, 40, 10) / 100

# ==================================================
# 🧠 TABELAS E LÓGICA
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
    # kg/m2 Z275
    pesos = {26: 4.00, 24: 5.60, 22: 6.80, 20: 8.40, 18: 10.50}
    return pesos.get(int(safe_float(bitola)), 6.0)

def encontrar_comprimento_proximo(msp, coords_texto, raio, layers_duto):
    """Busca a entidade MAIS PRÓXIMA nas layers indicadas."""
    melhor_comp = 0.0
    menor_dist = float('inf')

    # Busca em LINHAS
    for line in msp.query('LINE'):
        if line.dxf.layer in layers_duto:
            mid = ((line.dxf.start.x + line.dxf.end.x)/2, (line.dxf.start.y + line.dxf.end.y)/2)
            dist = calcular_distancia(mid, coords_texto)
            
            if dist < raio and dist < menor_dist:
                menor_dist = dist
                melhor_comp = calcular_distancia(line.dxf.start, line.dxf.end)

    # Busca em POLILINHAS
    for poly in msp.query('LWPOLYLINE'):
        if poly.dxf.layer in layers_duto:
            if len(poly) > 0:
                p0 = poly[0]
                dist = calcular_distancia((p0[0], p0[1]), coords_texto)
                
                if dist < raio and dist < menor_dist:
                    menor_dist = dist
                    # Perímetro
                    pts = poly.get_points()
                    comp_poly = 0
                    for i in range(len(pts)-1):
                        comp_poly += calcular_distancia(pts[i], pts[i+1])
                    
                    # Se for polilinha fechada (retângulo), o perímetro é 2L+2A. 
                    # Aproximação: Se perímetro > raio, assumimos que é comprimento linear desenhado
                    melhor_comp = comp_poly

    return melhor_comp, menor_dist

def processar_ia(texto_limpo, dicionario_geo, msp, raio, layers_duto, layers_equip, unid_cad, fator_manual):
    if not api_key: return None

    escala = 0.001 if "Milímetros" in unid_cad else 1.0

    prompt = f"""
    Engenheiro HVAC. Analise texto DXF (separado por ' | ').
    
    1. VAZÃO: Ignore números entre parênteses ex: "(34.000)".
    2. DIMENSÕES: Extraia "LARGURA x ALTURA" (ex: 1.300x700).
    3. EQUIPAMENTOS: Identifique Fancoils, Cassetes, etc.

    SAÍDA JSON:
    {{
        "dutos": [{{ "dimensao_original": "1.300x700", "largura_mm": 1300, "altura_mm": 700 }}],
        "equipamentos": [{{ "item": "Nome", "quantidade": 1 }}]
    }}
    """

    try:
        response = openai.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": f"Texto:\n{texto_limpo[:60000]}"} 
            ],
            temperature=0.0,
            response_format={"type": "json_object"}
        )
        ai_data = json.loads(response.choices[0].message.content)
        
        lista_dutos = ai_data.get("dutos", [])
        
        for d in lista_dutos:
            dim_ia = d.get("dimensao_original", "")
            key_ia = normalizar_texto(dim_ia)
            
            # Match Texto <-> Geometria
            coords = None
            for item_geo in dicionario_geo:
                if key_ia in normalizar_texto(item_geo['txt']):
                    coords = item_geo['pos']
                    break
            
            if coords:
                comp_raw, dist = encontrar_comprimento_proximo(msp, coords, raio, layers_duto)
                
                if comp_raw > 0:
                    # CORREÇÃO DO 50%: NÃO DIVIDE MAIS POR 2.
                    # Multiplica pelo fator manual se o usuário quiser ajustar.
                    comp_final = (comp_raw * escala) * fator_manual
                    d['comprimento_m'] = comp_final
                    d['nota'] = f"Medido (Dist: {int(dist)})"
                else:
                    d['comprimento_m'] = 0
                    d['nota'] = "Linha não encontrada (Aumentar Raio?)"
            else:
                d['comprimento_m'] = 0
                d['nota'] = "Texto não localizado no espaço"

        return ai_data

    except Exception as e:
        return {"erro": str(e)}

def gerar_excel_final(df_dutos, df_equip, resumo):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        wb = writer.book
        # Formatos
        fmt_head = wb.add_format({'bold': True, 'bg_color': '#104E8B', 'font_color': 'white'})
        fmt_num = wb.add_format({'num_format': '#,##0.00'})
        
        # Aba Resumo
        ws1 = wb.add_worksheet('Resumo')
        ws1.write(0, 0, "Item", fmt_head)
        ws1.write(0, 1, "Valor", fmt_head)
        r = 1
        for k,v in resumo.items():
            ws1.write(r, 0, k)
            ws1.write(r, 1, v)
            r+=1
            
        # Aba Dutos
        if not df_dutos.empty:
            df_dutos.to_excel(writer, sheet_name='Dutos', index=False)
            ws2 = writer.sheets['Dutos']
            for i, col in enumerate(df_dutos.columns):
                ws2.write(0, i, col, fmt_head)
                
        # Aba Equip
        if not df_equip.empty:
            df_equip.to_excel(writer, sheet_name='Equipamentos', index=False)
            ws3 = writer.sheets['Equipamentos']
            for i, col in enumerate(df_equip.columns):
                ws3.write(0, i, col, fmt_head)
                
    output.seek(0)
    return output

# ==================================================
# 🖥️ INTERFACE
# ==================================================
st.title("🏗️ Leitor V19: Correção de Quantitativos")
st.markdown("Cálculo corrigido (sem divisão por 2), com **Bitola** e **Área** visíveis.")

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
            
            # Seletor de Layers
            all_layers = sorted(list(set([e.dxf.layer for e in msp])))
            c1, c2 = st.columns(2)
            sel_layers_duto = c1.multiselect("Layers de DUTOS:", all_layers)
            sel_layers_equip = c2.multiselect("Layers de EQUIPAMENTOS:", all_layers)
            
            # Leitura
            raw_text = []
            geo_list = []
            for e in msp.query('TEXT MTEXT'):
                t = str(e.dxf.text).strip()
                if len(t) > 2:
                    raw_text.append(t)
                    geo_list.append({'txt': t, 'pos': (e.dxf.insert.x, e.dxf.insert.y)})
            
            # Blocos
            if sel_layers_equip:
                for ins in msp.query('INSERT'):
                    if ins.dxf.layer in sel_layers_equip:
                        t = ins.dxf.name
                        raw_text.append(t)
                        geo_list.append({'txt': t, 'pos': (ins.dxf.insert.x, ins.dxf.insert.y)})

            if st.button("🚀 Calcular (Corrigido)", type="primary"):
                if not sel_layers_duto or not api_key:
                    st.error("Selecione Layers e verifique API Key.")
                else:
                    with st.spinner("Calculando Geometria..."):
                        txt_join = " | ".join(raw_text)
                        dados = processar_ia(txt_join, geo_list, msp, raio_busca, sel_layers_duto, sel_layers_equip, unidade_cad, fator_ajuste)
                        
                        if "erro" in dados:
                            st.error(dados['erro'])
                        else:
                            # --- CÁLCULOS FINAIS ---
                            lista = dados.get("dutos", [])
                            res_final = []
                            kg_total = 0
                            m2_total = 0
                            
                            for d in lista:
                                w, h = safe_float(d.get('largura_mm')), safe_float(d.get('altura_mm'))
                                l = d.get('comprimento_m', 0)
                                if l > max_len: l = 0
                                
                                if w > 0 and h > 0:
                                    maior = max(w, h)
                                    bitola = definir_bitola_nbr(maior, classe_pressao)
                                    kg_m2 = calcular_peso_chapa(bitola)
                                    
                                    perimetro = 2 * (w + h) / 1000 # metros
                                    area = (perimetro * l) * (1 + perda_corte)
                                    peso = area * kg_m2
                                    
                                    kg_total += peso
                                    m2_total += area
                                    
                                    res_final.append({
                                        "Dimensão": d.get("dimensao_original"),
                                        "Comp. (m)": round(l, 2),
                                        "Bitola": f"#{bitola}",
                                        "Área (m²)": round(area, 2),
                                        "Peso (kg)": round(peso, 1),
                                        "Obs": d.get("nota")
                                    })
                            
                            # --- EXIBIÇÃO ---
                            # 1. CARDS DE MÉTRICAS (Resgatados)
                            k1, k2, k3 = st.columns(3)
                            k1.metric("Peso Total (Aço)", f"{kg_total:,.1f} kg")
                            k2.metric("Área Isolamento", f"{m2_total:,.1f} m²")
                            k3.metric("Equipamentos", f"{len(dados.get('equipamentos', []))} un")
                            
                            st.divider()
                            
                            # 2. TABELAS
                            t1, t2 = st.tabs(["📋 Memorial de Dutos", "❄️ Equipamentos"])
                            
                            with t1:
                                df_dutos = pd.DataFrame(res_final)
                                st.dataframe(df_dutos, use_container_width=True)
                            
                            with t2:
                                df_equip = pd.DataFrame(dados.get("equipamentos", []))
                                st.dataframe(df_equip, use_container_width=True)
                                
                            # 3. EXCEL
                            meta = {
                                "Peso Total (kg)": kg_total, 
                                "Área Total (m2)": m2_total,
                                "Norma": "NBR 16401"
                            }
                            xlsx = gerar_excel_final(df_dutos, df_equip, meta)
                            st.download_button("📥 Baixar Planilha Completa", xlsx, "Levantamento_V19.xlsx")

    except Exception as e:
        st.error(f"Erro: {e}")
    finally:
        if os.path.exists(path_temp): os.remove(path_temp)
