import streamlit as st
import ezdxf
from ezdxf import recover
import math
import pandas as pd
import tempfile
import os
import re
from openai import OpenAI
from collections import Counter

# --- 🔒 SEGURANÇA ---
if 'logado' not in st.session_state or not st.session_state['logado']:
    st.warning("🔒 Acesso negado. Faça login no Dashboard.")
    st.stop()

st.set_page_config(page_title="Leitor DXF (Geometria Real)", page_icon="📏", layout="wide")

st.title("📏 Leitor Técnico DXF - Medição por Geometria")
st.markdown("""
**Algoritmo Avançado "Wall Matcher":**
O sistema usa a **Largura do Texto (ex: 500)** para encontrar as linhas paralelas do desenho que correspondem a essa medida e calcula o comprimento real do trecho.
""")

# ============================================================================
# 1. CONFIGURAÇÕES
# ============================================================================
with st.sidebar:
    st.header("⚙️ Configurações")
    
    # Fundamental para a lógica funcionar
    unidade_desenho = st.selectbox(
        "Unidade do Desenho CAD:", 
        ["Milímetros (1u=1mm)", "Centímetros (1u=1cm)", "Metros (1u=1m)"],
        index=0,
        help="Se o duto 500x300 mede 500 unidades no CAD, selecione Milímetros."
    )
    
    # Tolerância de desenho (desenhistas nunca são exatos)
    tolerancia_desenho = st.number_input(
        "Tolerância de Desenho (mm):", 
        value=5.0, 
        help="Se a linha tiver 502mm e o texto 500mm, considera igual."
    )

    raio_busca = st.number_input(
        "Raio de Busca (mm):", 
        value=1500, 
        step=500,
        help="Distância máxima do texto até a parede do duto."
    )
    
    st.divider()
    classe_pressao = st.selectbox("Classe de Pressão", ["Classe A (Baixa)", "Classe B (Média)", "Classe C (Alta)"])
    perda_corte = st.number_input("% Perda / Corte", value=10.0)
    tipo_isolamento = st.selectbox("Isolamento", ["Lã de Vidro", "Borracha Elast.", "Isopor", "Sem Isolamento"])

# ============================================================================
# 2. FUNÇÕES GEOMÉTRICAS (MATEMÁTICA VETORIAL)
# ============================================================================

def pt_dist(p1, p2):
    return math.hypot(p2[0]-p1[0], p2[1]-p1[1])

def get_line_props(line):
    """Retorna inicio, fim, angulo (graus) e comprimento"""
    s, e = line.dxf.start, line.dxf.end
    dx, dy = e.x - s.x, e.y - s.y
    ang = math.degrees(math.atan2(dy, dx)) % 180 # Normaliza 0-180
    return s, e, ang, math.hypot(dx, dy)

def distancia_ponto_reta(px, py, x1, y1, x2, y2):
    # Distância mínima de um ponto a um segmento de reta
    # (Simplificado para distância perpendicular infinita para checar afastamento)
    # A*x + B*y + C = 0
    # A = y1-y2, B = x2-x1, C = x1*y2 - x2*y1
    a = y1 - y2
    b = x2 - x1
    c = x1 * y2 - x2 * y1
    return abs(a*px + b*py + c) / math.hypot(a, b)

def medir_duto_pela_largura(msp, texto_obj, largura_alvo, altura_alvo, layers_validos, unid_fator):
    """
    O CÉREBRO: Procura linhas paralelas espaçadas por 'largura_alvo' ou 'altura_alvo'.
    """
    # Converte alvos para unidade do CAD
    # Se CAD é mm: 500 -> 500. Se CAD é cm: 500 -> 50.
    w_cad = largura_alvo * unid_fator
    h_cad = altura_alvo * unid_fator
    tol = tolerancia_desenho * unid_fator
    
    # Coordenadas do texto
    ins = texto_obj.dxf.insert
    tx, ty = ins.x, ins.y
    
    melhor_comprimento = 0.0
    tipo_encontrado = "Não achou"

    # Coleta linhas próximas (Bounding Box simples para otimizar)
    linhas_candidatas = []
    
    # O ideal seria query espacial, mas vamos iterar filtrando por layer
    query = f'LINE LWPOLYLINE'
    
    for e in msp.query(query):
        # Filtro de Layer (Ignora arquitetura se layer for selecionado)
        if layers_validos and e.dxf.layer not in layers_validos: continue
        
        # Pega geometria básica
        if e.dxftype() == 'LINE':
            s, end, ang, comp = get_line_props(e)
            # Filtro de proximidade (Manhattan distance)
            if abs(s.x - tx) > raio_busca and abs(end.x - tx) > raio_busca: continue
            if abs(s.y - ty) > raio_busca and abs(end.y - ty) > raio_busca: continue
            
            linhas_candidatas.append({'obj': e, 'ang': ang, 'comp': comp, 's': s, 'e': end})
            
        elif e.dxftype() == 'LWPOLYLINE':
            # Explode polilinha em segmentos virtuais
            pts = e.get_points()
            for i in range(len(pts)-1):
                p1, p2 = pts[i], pts[i+1]
                dx, dy = p2[0]-p1[0], p2[1]-p1[1]
                ang = math.degrees(math.atan2(dy, dx)) % 180
                comp = math.hypot(dx, dy)
                
                # Check proximidade
                if abs(p1[0] - tx) > raio_busca and abs(p2[0] - tx) > raio_busca: continue
                if abs(p1[1] - ty) > raio_busca and abs(p2[1] - ty) > raio_busca: continue
                
                linhas_candidatas.append({'obj': e, 'ang': ang, 'comp': comp, 's': p1, 'e': p2})

    # Agora a mágica: Busca PARES de linhas paralelas
    # Complexidade O(N^2) local -> aceitável para N < 100 candidatos
    for i in range(len(linhas_candidatas)):
        l1 = linhas_candidatas[i]
        for j in range(i + 1, len(linhas_candidatas)):
            l2 = linhas_candidatas[j]
            
            # 1. São paralelas? (Diferença de ângulo < 5 graus)
            diff_ang = abs(l1['ang'] - l2['ang'])
            if diff_ang > 5 and diff_ang < 175: continue 
            
            # 2. Distância entre elas bate com a Largura ou Altura?
            # Pega o ponto médio de L1 e mede distância até a reta L2
            mid1_x = (l1['s'][0] + l1['e'][0])/2
            mid1_y = (l1['s'][1] + l1['e'][1])/2
            
            try:
                dist_paredes = distancia_ponto_reta(mid1_x, mid1_y, l2['s'][0], l2['s'][1], l2['e'][0], l2['e'][1])
            except: continue # Divisão por zero em pontos iguais
            
            match_w = abs(dist_paredes - w_cad) <= tol
            match_h = abs(dist_paredes - h_cad) <= tol
            
            if match_w or match_h:
                # BINGO! Achamos as paredes.
                # O comprimento do duto é a média do comprimento das paredes
                # (Ou o maximo, para ser conservador)
                comp_medido = max(l1['comp'], l2['comp'])
                
                # Vamos somar ao total (se tivermos sorte de pegar segmentos continuos, somamos)
                # Neste algoritmo simplificado, pegamos o maior par encontrado.
                if comp_medido > melhor_comprimento:
                    melhor_comprimento = comp_medido
                    dim_match = largura_alvo if match_w else altura_alvo
                    tipo_encontrado = f"Paredes dist={int(dim_match)}"

    return melhor_comprimento, tipo_encontrado

# ============================================================================
# 3. PROCESSAMENTO
# ============================================================================
def extrair_dutos_com_logica_largura(file_bytes, layers_duto_sel, unid_cad_sel):
    temp_path = tempfile.NamedTemporaryFile(delete=False, suffix=".dxf").name
    with open(temp_path, "wb") as f: f.write(file_bytes)
    
    try:
        try: doc = ezdxf.readfile(temp_path)
        except: doc, aud = recover.readfile(temp_path)
        msp = doc.modelspace()
        
        # Fator de conversão (Unidade Escolhida -> Unidade do CAD)
        # Se CAD é mm, fator é 1. Se CAD é m, mas texto diz 500(mm), fator é 0.001
        # Assumindo que o TEXTO é sempre mm (padrão HVAC)
        fator_dim_para_cad = 1.0
        if unid_cad_sel == "Metros (m)": fator_dim_para_cad = 0.001
        elif unid_cad_sel == "Centímetros (cm)": fator_dim_para_cad = 0.1
        
        dutos_finais = []
        
        # Regex para pegar dimensão (1.300x700 ou 500x300)
        reg_dim = re.compile(r'(\d{1,3}(?:\.\d{3})*|\d+)\s*[xX]\s*(\d{1,3}(?:\.\d{3})*|\d+)')
        
        count_textos = 0
        for e in msp.query('TEXT MTEXT'):
            txt = e.dxf.text if e.dxftype() == 'TEXT' else e.text
            if not txt: continue
            t_clean = txt.strip().upper()
            
            match = reg_dim.search(t_clean)
            if match:
                l_str = match.group(1).replace('.', '')
                a_str = match.group(2).replace('.', '')
                l_mm = float(l_str)
                a_mm = float(a_str)
                
                if l_mm > 50 and a_mm > 50:
                    # Aplica o "Wall Matcher"
                    comp_cad, tipo_match = medir_duto_pela_largura(msp, e, l_mm, a_mm, layers_duto_sel, fator_dim_para_cad)
                    
                    # Converte comp do CAD para Metros
                    comp_m = 0
                    if unid_cad_sel == "Milímetros (mm)": comp_m = comp_cad / 1000
                    elif unid_cad_sel == "Centímetros (cm)": comp_m = comp_cad / 100
                    else: comp_m = comp_cad
                    
                    dutos_finais.append({
                        "Largura": l_mm,
                        "Altura": a_mm,
                        "Comp. Geo (m)": comp_m,
                        "Tag": t_clean,
                        "Debug": tipo_match
                    })
                    count_textos += 1
                    
        return dutos_finais, f"Analisados {count_textos} textos de bitola."
        
    except Exception as e:
        return [], str(e)
    finally:
        if os.path.exists(temp_path): os.remove(temp_path)

# ============================================================================
# 4. INTERFACE
# ============================================================================
uploaded_dxf = st.file_uploader("📂 Carregar DXF", type=["dxf"])

if uploaded_dxf:
    # 1. Leitura inicial de Layers para o usuário escolher
    # (Reusando função segura de leitura básica)
    try:
        content_str = uploaded_dxf.getvalue().decode("cp1252", errors='ignore')
        doc_pre = ezdxf.read(io.StringIO(content_str))
        layers_all = sorted(list(set([l.dxf.name for l in doc_pre.layers])))
    except:
        layers_all = []

    if layers_all:
        st.info("Para a medição geométrica funcionar, selecione o Layer onde estão as LINHAS dos dutos.")
        sel_layer = st.multiselect("Layer(s) de Dutos:", layers_all)
        
        if st.button("🚀 Calcular (Algoritmo Geométrico)", type="primary"):
            if not sel_layer:
                st.error("Selecione pelo menos um layer.")
            else:
                with st.spinner("Medindo paredes dos dutos..."):
                    lista, log = extrair_dutos_com_logica_largura(uploaded_dxf, sel_layer, unidade_desenho)
                    
                    if lista:
                        df = pd.DataFrame(lista)
                        
                        # --- AGRUPAMENTO E CÁLCULOS FINAIS ---
                        # Agrupa por dimensão, somando o comprimento medido
                        # E contando quantas peças (tags) achou
                        df_g = df.groupby(['Largura', 'Altura']).agg(
                            Qtd_Pecas=('Tag', 'count'),
                            Comp_Medido=('Comp. Geo (m)', 'sum'),
                            Exemplo_Debug=('Debug', 'first')
                        ).reset_index()
                        
                        # Lógica Híbrida:
                        # Se o comp. medido for muito baixo (geo falhou), usa estimativa por peça
                        # Se o comp. medido for bom, usa ele.
                        def definir_comp_final(row):
                            # Se a média por peça for < 0.5m, provavelmente a geometria falhou
                            media = row['Comp_Medido'] / row['Qtd_Pecas']
                            if media < 0.3: 
                                return row['Qtd_Pecas'] * 1.10 # Fallback (Estimado)
                            return row['Comp_Medido'] # Geometria (Real)

                        df_g['Comp. Final (m)'] = df_g.apply(definir_comp_final, axis=1)
                        df_g['Origem'] = df_g.apply(lambda x: "Geometria" if x['Comp_Medido']/x['Qtd_Pecas'] > 0.3 else "Estimado (Tag)", axis=1)
                        
                        # Cálculos de Área e Peso
                        df_g['Perímetro'] = (2*df_g['Largura'] + 2*df_g['Altura'])/1000
                        df_g['Área (m²)'] = df_g['Perímetro'] * df_g['Comp. Final (m)'] * (1 + perda_corte/100)
                        
                        # --- EXIBIÇÃO ---
                        area_tot = df_g['Área (m²)'].sum()
                        peso_tot = area_tot * 5.6
                        
                        c1, c2, c3 = st.columns(3)
                        c1.metric("Peso Total", f"{peso_tot:,.0f} kg")
                        c2.metric("Área Total", f"{area_tot:,.2f} m²")
                        c3.metric("Itens Lidos", int(df_g['Qtd_Pecas'].sum()))
                        
                        tab1, tab2 = st.tabs(["Resumo", "Detalhamento Individual"])
                        with tab1:
                            st.dataframe(df_g, use_container_width=True)
                        with tab2:
                            st.dataframe(df) # Mostra item a item para debug
                            
                    else:
                        st.warning("Nenhuma etiqueta de duto (ex: 500x300) encontrada.")

    else:
        st.error("Erro ao ler layers do arquivo.")
