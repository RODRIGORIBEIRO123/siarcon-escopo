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
import networkx as nx

# Configuração da Página
st.set_page_config(page_title="Siarcon - Leitor V20 (Rastreamento)", page_icon="🔗", layout="wide")

# ==================================================
# 🔧 MATEMÁTICA E GEOMETRIA AVANÇADA
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

def dist_sq(p1, p2):
    return (p1[0] - p2[0])**2 + (p1[1] - p2[1])**2

def pontos_iguais(p1, p2, tol=1.0):
    # Tolerância para considerar que duas linhas se tocam (1.0 = 1mm ou 1unidade)
    return dist_sq(p1, p2) < (tol * tol)

def normalizar_texto(texto):
    return str(texto).replace('.', '').replace(' ', '').lower().strip()

# ==================================================
# 🧠 ALGORITMO DE RASTREAMENTO (CHAIN-LINK)
# ==================================================
def construir_grafo_linhas(msp, layers_duto):
    """
    Cria um grafo onde cada 'nó' é uma coordenada (x,y) e cada 'aresta' é uma linha do CAD.
    Isso permite navegar pela rede de dutos.
    """
    G = nx.Graph()
    
    # Adiciona LINHAS
    for line in msp.query('LINE'):
        if line.dxf.layer in layers_duto:
            p1 = (round(line.dxf.start.x, 1), round(line.dxf.start.y, 1))
            p2 = (round(line.dxf.end.x, 1), round(line.dxf.end.y, 1))
            comprimento = math.sqrt(dist_sq(p1, p2))
            G.add_edge(p1, p2, weight=comprimento, id=str(line))

    # Adiciona POLILINHAS (Explode em segmentos)
    for poly in msp.query('LWPOLYLINE'):
        if poly.dxf.layer in layers_duto:
            pts = poly.get_points()
            for i in range(len(pts) - 1):
                p1 = (round(pts[i][0], 1), round(pts[i][1], 1))
                p2 = (round(pts[i+1][0], 1), round(pts[i+1][1], 1))
                comprimento = math.sqrt(dist_sq(p1, p2))
                G.add_edge(p1, p2, weight=comprimento, id=str(poly))
                
    return G

def medir_rede_conectada(grafo, ponto_inicial_aprox, raio_busca):
    """
    Dado um ponto (texto), encontra a linha mais próxima e soma 
    todas as linhas conectadas a ela (componente conexo).
    """
    # 1. Achar o nó do grafo mais próximo do texto
    nos = list(grafo.nodes)
    if not nos: return 0.0, 0
    
    # KDTree seria ideal, mas força bruta resolve para <10k linhas
    melhor_no = None
    menor_dist = float('inf')
    
    px, py = ponto_inicial_aprox
    
    for no in nos:
        d = (no[0]-px)**2 + (no[1]-py)**2
        if d < menor_dist:
            menor_dist = d
            melhor_no = no
            
    # Se o nó mais próximo estiver muito longe, aborta (não pertence a esse texto)
    if menor_dist > (raio_busca**2):
        return 0.0, int(math.sqrt(menor_dist))

    # 2. Descobrir a componente conectada (todas as linhas que se tocam a partir daqui)
    # BFS para encontrar tudo conectado
    componente = nx.node_connected_component(grafo, melhor_no)
    
    # 3. Somar pesos (comprimentos) da sub-rede
    subgrafo = grafo.subgraph(componente)
    comprimento_total = subgrafo.size(weight='weight')
    
    # IMPORTANTE: Remover as arestas do grafo principal para não somar duas vezes
    # se tiver outro texto perto?
    # R: NÃO. Em dutos, é comum ter texto repetido. Melhor medir tudo e o usuário ver se duplicou,
    # ou assumimos que textos distantes medem redes distintas.
    # Neste algoritmo V20, vamos medir a ilha isolada.
    
    return comprimento_total, int(math.sqrt(menor_dist))

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
    st.subheader("📐 Geometria & Rastreio")
    
    unidade_cad = st.selectbox("Unidade CAD:", ["Milímetros (1u=1mm)", "Metros (1u=1m)"], index=0)
    
    raio_busca = st.number_input(
        "Raio de Captura (mm):", 
        value=1500, 
        step=500,
        help="Distância para 'agarrar' a primeira linha do duto perto do texto."
    )
    
    st.info("ℹ️ O algoritmo agora soma todas as linhas conectadas!")
    
    st.subheader("🛡️ Filtros")
    fator_ajuste = st.number_input("Multiplicador Manual:", value=1.0, step=0.1)
    
    st.subheader("📋 NBR 16401")
    classe_pressao = st.selectbox("Pressão:", ["Classe A (Baixa)", "Classe B (Média)", "Classe C (Alta)"], index=0)
    perda_corte = st.slider("Perda (%)", 0, 40, 10) / 100

# ==================================================
# 🧠 LÓGICA PRINCIPAL
# ==================================================
def calcular_peso_chapa(bitola):
    pesos = {26: 4.00, 24: 5.60, 22: 6.80, 20: 8.40, 18: 10.50}
    return pesos.get(int(safe_float(bitola)), 6.0)

def definir_bitola_nbr(maior_lado_mm, classe_txt):
    maior_lado_mm = safe_float(maior_lado_mm)
    if "Classe A" in classe_txt:
        return 24 if maior_lado_mm <= 750 else 22 if maior_lado_mm <= 1200 else 20 if maior_lado_mm <= 1500 else 18
    elif "Classe B" in classe_txt:
        return 24 if maior_lado_mm <= 600 else 22 if maior_lado_mm <= 1000 else 20
    else:
        return 24 if maior_lado_mm <= 250 else 22 if maior_lado_mm <= 500 else 20

def processar_ia(texto_limpo, dicionario_geo, grafo, raio, unid_cad, fator_manual):
    if not api_key: return None

    escala = 0.001 if "Milímetros" in unid_cad else 1.0

    prompt = f"""
    Engenheiro HVAC. Analise texto DXF (separado por ' | ').
    IGNORAR VAZÃO ENTRE PARÊNTESES "(34.000)".
    EXTRAIR APENAS DIMENSÕES "LARGURA x ALTURA" (Ex: 1.300x700).
    IDENTIFICAR EQUIPAMENTOS.

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
        
        # Para evitar somar a mesma rede várias vezes se tiver vários textos nela,
        # poderíamos marcar os nós visitados. Mas para simplificar V20, vamos medir tudo.
        
        for d in lista_dutos:
            dim_ia = d.get("dimensao_original", "")
            key_ia = normalizar_texto(dim_ia)
            
            # 1. Achar coordenadas do texto
            coords = None
            for item_geo in dicionario_geo:
                if key_ia in normalizar_texto(item_geo['txt']):
                    coords = item_geo['pos']
                    break
            
            if coords:
                # 2. ALGORITMO CHAIN-LINK (Rastreamento)
                comp_rede_raw, dist_aprox = medir_rede_conectada(grafo, coords, raio)
                
                if comp_rede_raw > 0:
                    # Aplica escala e fator manual
                    comp_final = (comp_rede_raw * escala) * fator_manual
                    d['comprimento_m'] = comp_final
                    d['nota'] = f"Rede Rasteada (Dist inicial: {dist_aprox})"
                else:
                    d['comprimento_m'] = 0
                    d['nota'] = "Nenhuma linha conectada encontrada no raio."
            else:
                d['comprimento_m'] = 0
                d['nota'] = "Texto não localizado."

        return ai_data

    except Exception as e:
        return {"erro": str(e)}

def gerar_excel_final(df_dutos, df_equip, resumo):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        wb = writer.book
        fmt_head = wb.add_format({'bold': True, 'bg_color': '#104E8B', 'font_color': 'white'})
        
        ws1 = wb.add_worksheet('Resumo')
        ws1.write(0, 0, "Item", fmt_head)
        ws1.write(0, 1, "Valor", fmt_head)
        r = 1
        for k,v in resumo.items():
            ws1.write(r, 0, k)
            ws1.write(r, 1, v)
            r+=1
            
        if not df_dutos.empty:
            df_dutos.to_excel(writer, sheet_name='Dutos', index=False)
        if not df_equip.empty:
            df_equip.to_excel(writer, sheet_name='Equipamentos', index=False)
                
    output.seek(0)
    return output

# ==================================================
# 🖥️ INTERFACE
# ==================================================
st.title("🔗 Leitor V20 (Algoritmo de Conectividade)")
st.markdown("Rastreia todas as linhas conectadas ao texto (Chain-Link) para evitar medir apenas segmentos soltos.")

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
            
            # Seleção de Layers
            all_layers = sorted(list(set([e.dxf.layer for e in msp])))
            c1, c2 = st.columns(2)
            sel_layers_duto = c1.multiselect("Layers DUTOS (Linhas):", all_layers)
            sel_layers_equip = c2.multiselect("Layers EQUIPAMENTOS:", all_layers)
            
            # Extração de Texto
            raw_text = []
            geo_list = []
            for e in msp.query('TEXT MTEXT'):
                t = str(e.dxf.text).strip()
                if len(t) > 2:
                    raw_text.append(t)
                    geo_list.append({'txt': t, 'pos': (e.dxf.insert.x, e.dxf.insert.y)})
            
            # Extração de Blocos (Equipamentos)
            if sel_layers_equip:
                for ins in msp.query('INSERT'):
                    if ins.dxf.layer in sel_layers_equip:
                        t = ins.dxf.name
                        raw_text.append(t)
                        geo_list.append({'txt': t, 'pos': (ins.dxf.insert.x, ins.dxf.insert.y)})

            st.caption(f"Textos lidos: {len(raw_text)}")

            if st.button("🚀 Calcular (Rastreamento de Rede)", type="primary"):
                if not sel_layers_duto or not api_key:
                    st.error("Selecione Layers de Duto e insira a API Key.")
                else:
                    with st.spinner("Construindo grafo de conectividade da rede... (Isso pode levar alguns segundos)"):
                        # 1. Constrói o Grafo da Rede (Pesado, mas necessário)
                        grafo_dutos = construir_grafo_linhas(msp, sel_layers_duto)
                        st.caption(f"Rede Mapeada: {grafo_dutos.number_of_nodes()} conexões encontradas.")
                        
                        # 2. Processa IA e Medição
                        txt_join = " | ".join(raw_text)
                        dados = processar_ia(txt_join, geo_list, grafo_dutos, raio_busca, unidade_cad, fator_ajuste)
                        
                        if "erro" in dados:
                            st.error(dados['erro'])
                        else:
                            # 3. Resultados
                            lista = dados.get("dutos", [])
                            res_final = []
                            kg_total = 0
                            m2_total = 0
                            
                            for d in lista:
                                w, h = safe_float(d.get('largura_mm')), safe_float(d.get('altura_mm'))
                                l = d.get('comprimento_m', 0)
                                
                                if w > 0 and h > 0:
                                    maior = max(w, h)
                                    bitola = definir_bitola_nbr(maior, classe_pressao)
                                    kg_m2 = calcular_peso_chapa(bitola)
                                    
                                    perimetro = 2 * (w + h) / 1000
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
                            
                            # Exibição
                            k1, k2, k3 = st.columns(3)
                            k1.metric("Peso Total (Aço)", f"{kg_total:,.1f} kg")
                            k2.metric("Área Isolamento", f"{m2_total:,.1f} m²")
                            k3.metric("Equipamentos", f"{len(dados.get('equipamentos', []))} un")
                            
                            st.dataframe(pd.DataFrame(res_final), use_container_width=True)
                            
                            meta = {"Peso Total (kg)": kg_total, "Área Total (m2)": m2_total}
                            xlsx = gerar_excel_final(pd.DataFrame(res_final), pd.DataFrame(dados.get("equipamentos", [])), meta)
                            st.download_button("📥 Baixar Excel", xlsx, "Levantamento_V20.xlsx")

    except Exception as e:
        st.error(f"Erro: {e}")
    finally:
        if os.path.exists(path_temp): os.remove(path_temp)
