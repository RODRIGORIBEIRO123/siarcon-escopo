import streamlit as st
import ezdxf
from ezdxf import recover
import pandas as pd
import tempfile
import os
import re
import math
from openai import OpenAI
from collections import Counter

# --- 🔒 SEGURANÇA ---
if 'logado' not in st.session_state or not st.session_state['logado']:
    st.warning("🔒 Acesso negado. Faça login no Dashboard.")
    st.stop()

st.set_page_config(page_title="Leitor DXF (Scanline)", page_icon="📏", layout="wide")

st.title("📏 Leitor Técnico DXF - Medição por Referência de Largura")
st.markdown("""
**Novo Algoritmo (Scanline):** O sistema lê a bitola (ex: **500**x300), procura no desenho duas linhas que estejam afastadas exatamente **500mm** e mede o comprimento delas.
""")

# ============================================================================
# 1. CONFIGURAÇÕES
# ============================================================================
with st.sidebar:
    st.header("⚙️ Calibração Geométrica")
    
    st.info("Para este método funcionar, a unidade deve estar EXATA.")
    unidade_desenho = st.selectbox(
        "Unidade do Desenho:", 
        ["Milímetros (1u=1mm)", "Centímetros (1u=1cm)", "Metros (1u=1m)"],
        index=0
    )
    
    tolerancia = st.number_input(
        "Tolerância de Desenho (+/-)", 
        value=2.0, 
        help="Se o duto tem 500mm mas o desenhista fez com 501mm, isso aceita. (Use valores baixos: 1.0 a 5.0)"
    )

    raio_busca = st.number_input(
        "Raio de Busca do Texto", 
        value=1000.0, 
        help="Distância máxima que o texto pode estar das linhas do duto."
    )
    
    st.divider()
    comp_fallback = st.number_input("Comp. Padrão (Se falhar a geometria)", value=1.10)
    
    st.divider()
    classe_pressao = st.selectbox("Classe de Pressão", ["Classe A", "Classe B", "Classe C"])
    perda_corte = st.number_input("% Perda / Corte", value=10.0)
    tipo_isolamento = st.selectbox("Isolamento", ["Lã de Vidro", "Borracha Elast.", "Isopor", "Sem Isolamento"])

# ============================================================================
# 2. MOTOR GEOMÉTRICO AVANÇADO (SCANLINE)
# ============================================================================

def ponto_medio(p1, p2):
    return ((p1[0]+p2[0])/2, (p1[1]+p2[1])/2)

def dist_pt(p1, p2):
    return math.hypot(p2[0]-p1[0], p2[1]-p1[1])

def get_segmentos(entity):
    """Explode linhas e polilinhas em segmentos simples [(p1, p2, angulo, comprimento)]"""
    segs = []
    try:
        if entity.dxftype() == 'LINE':
            s, e = entity.dxf.start, entity.dxf.end
            dx, dy = e.x - s.x, e.y - s.y
            ang = math.degrees(math.atan2(dy, dx)) % 180
            comp = math.hypot(dx, dy)
            segs.append({'p1': (s.x, s.y), 'p2': (e.x, e.y), 'ang': ang, 'comp': comp, 'obj': entity})
            
        elif entity.dxftype() == 'LWPOLYLINE':
            pts = entity.get_points()
            for i in range(len(pts)-1):
                p1, p2 = pts[i], pts[i+1]
                dx, dy = p2[0]-p1[0], p2[1]-p1[1]
                ang = math.degrees(math.atan2(dy, dx)) % 180
                comp = math.hypot(dx, dy)
                segs.append({'p1': p1, 'p2': p2, 'ang': ang, 'comp': comp, 'obj': entity})
    except: pass
    return segs

def distancia_entre_segmentos_paralelos(seg1, seg2):
    """Calcula a distância perpendicular entre dois segmentos paralelos"""
    # Pega o ponto médio do seg1
    mid1 = ponto_medio(seg1['p1'], seg1['p2'])
    
    # Projeta na reta do seg2 (Ax + By + C = 0)
    x1, y1 = seg2['p1']
    x2, y2 = seg2['p2']
    
    # Coeficientes da reta geral passando por seg2
    A = y1 - y2
    B = x2 - x1
    C = x1*y2 - x2*y1
    
    denom = math.hypot(A, B)
    if denom == 0: return float('inf')
    
    dist = abs(A*mid1[0] + B*mid1[1] + C) / denom
    return dist

def verificar_sobreposicao_projecao(seg1, seg2, texto_pos):
    """Verifica se o texto está 'entre' o início e fim dos segmentos (grosseiramente)"""
    # Simplificação: Verifica se o texto está dentro do bounding box combinado
    min_x = min(seg1['p1'][0], seg1['p2'][0], seg2['p1'][0], seg2['p2'][0])
    max_x = max(seg1['p1'][0], seg1['p2'][0], seg2['p1'][0], seg2['p2'][0])
    min_y = min(seg1['p1'][1], seg1['p2'][1], seg2['p1'][1], seg2['p2'][1])
    max_y = max(seg1['p1'][1], seg1['p2'][1], seg2['p1'][1], seg2['p2'][1])
    
    tx, ty = texto_pos
    # Margem de segurança
    margin = 50
    if (min_x - margin <= tx <= max_x + margin) and (min_y - margin <= ty <= max_y + margin):
        return True
    return False

def medir_duto_scanline(msp, texto_obj, largura_alvo, altura_alvo, layers_validos, fator_conv, raio_max, tol):
    """
    Algoritmo Scanline:
    1. Acha linhas próximas.
    2. Busca PARES de linhas paralelas cuja distância seja igual a Largura ou Altura.
    3. Retorna o comprimento dessas linhas.
    """
    # Ajusta alvos para unidade do CAD
    targets = [largura_alvo * fator_conv, altura_alvo * fator_conv]
    
    ins = texto_obj.dxf.insert
    t_pos = (ins.x, ins.y)
    
    # 1. Coleta Candidatos (Bounding Box)
    segmentos_proximos = []
    
    # Itera todas as linhas (filtrando layer)
    # Infelizmente ezdxf não tem index espacial nativo rápido, então fazemos brute force filtrado
    for e in msp.query('LINE LWPOLYLINE'):
        if layers_validos and e.dxf.layer not in layers_validos: continue
        
        # Check rápido de distância
        try:
            if e.dxftype() == 'LINE': ref = (e.dxf.start.x, e.dxf.start.y)
            else: ref = (e.get_points()[0][0], e.get_points()[0][1])
            
            if abs(ref[0] - t_pos[0]) > raio_max or abs(ref[1] - t_pos[1]) > raio_max: continue
            
            # Explode e guarda
            sub_segs = get_segmentos(e)
            segmentos_proximos.extend(sub_segs)
        except: pass
        
    if not segmentos_proximos: return 0.0, "Sem linhas"

    melhor_comp = 0.0
    match_type = "Estimado"

    # 2. Compara Pares (O(N^2) local)
    # Como filtramos pelo raio, N deve ser pequeno (<50)
    for i in range(len(segmentos_proximos)):
        s1 = segmentos_proximos[i]
        for j in range(i + 1, len(segmentos_proximos)):
            s2 = segmentos_proximos[j]
            
            # Check Angulo (Paralelismo)
            # Aceita linhas invertidas (0 vs 180)
            diff = abs(s1['ang'] - s2['ang'])
            if diff > 5 and diff < 175: continue # Não são paralelas
            
            # Check Distância
            dist = distancia_entre_segmentos_paralelos(s1, s2)
            
            # Verifica se bate com Largura ou Altura
            bateu_medida = False
            for tgt in targets:
                if abs(dist - tgt) <= (tol * fator_conv):
                    bateu_medida = True
                    break
            
            if bateu_medida:
                # Check se o texto está "no meio" (opcional mas bom)
                if verificar_sobreposicao_projecao(s1, s2, t_pos):
                    # BINGO: Achamos as paredes
                    comp_medio = (s1['comp'] + s2['comp']) / 2
                    if comp_medio > melhor_comp:
                        melhor_comp = comp_medio
                        match_type = f"Paredes (Dist={int(dist)})"

    return melhor_comp, match_type

# ============================================================================
# 3. PROCESSAMENTO ESTRUTURADO
# ============================================================================
def carregar_dxf_seguro(uploaded_file):
    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".dxf") as tmp_file:
            tmp_file.write(uploaded_file.getvalue())
            temp_path = tmp_file.name
        doc, auditor = recover.readfile(temp_path)
        return doc, temp_path, None
    except Exception as e:
        return None, temp_path, str(e)

def processar_projeto(doc, layers_duto, unid_str, raio, tol):
    msp = doc.modelspace()
    
    # Fatores (Texto é sempre mm) -> (CAD) -> (Metros finais)
    if unid_str == "Metros (1u=1m)":
        fator_txt_cad = 0.001
        fator_cad_metro = 1.0
    elif unid_str == "Centímetros (1u=1cm)":
        fator_txt_cad = 0.1
        fator_cad_metro = 0.01
    else: # mm
        fator_txt_cad = 1.0
        fator_cad_metro = 0.001
        
    dutos = []
    ia_buffer = []
    
    # Regex 500x300 ou 1.300x700
    regex_ret = re.compile(r'(\d{1,4}(?:\.\d{3})*|\d+)\s*[xX*]\s*(\d{1,4}(?:\.\d{3})*|\d+)')
    
    count = 0
    progress = st.progress(0, "Escaneando textos...")
    total_txt = sum(1 for _ in msp.query('TEXT MTEXT'))
    
    for idx, e in enumerate(msp.query('TEXT MTEXT')):
        if idx % 50 == 0: progress.progress(min(idx/total_txt, 1.0))
        
        txt = e.dxf.text if e.dxftype() == 'TEXT' else e.text
        if not txt: continue
        t_clean = re.sub(r'\\[ACFHQTW].*?;', '', txt).replace('{','').replace('}','').strip().upper()
        
        # Check Duto
        match = regex_ret.search(t_clean)
        if match:
            try:
                l_raw = float(match.group(1).replace('.',''))
                a_raw = float(match.group(2).replace('.',''))
                
                if l_raw > 50 and a_raw > 50:
                    # ALGORITMO SCANLINE
                    comp_cad, status = medir_duto_scanline(
                        msp, e, l_raw, a_raw, layers_duto, fator_txt_cad, raio, tol
                    )
                    
                    comp_final = 0.0
                    origem = "Estimado"
                    
                    if status.startswith("Paredes"):
                        comp_final = comp_cad * fator_cad_metro
                        origem = "Medido (Geometria)"
                    else:
                        comp_final = comp_fallback # Fallback configurado
                        origem = "Não achou paredes"
                        
                    dutos.append({
                        "Largura": l_raw,
                        "Altura": a_raw,
                        "Comp. (m)": comp_final,
                        "Origem": origem,
                        "Tag": t_clean,
                        "Detalhe": status
                    })
                    continue
            except: pass
            
        # Buffer IA
        if any(c.isalpha() for c in t_clean) and len(t_clean) > 2:
            ia_buffer.append(t_clean)
            
    progress.empty()
    return dutos, ia_buffer

# ============================================================================
# 4. IA (EQUIPAMENTOS)
# ============================================================================
def classificar_ia(lista):
    if not lista: return {}
    # Proteção de chave
    api_key = st.secrets.get("openai", {}).get("api_key")
    if not api_key: return {}
    
    client = OpenAI(api_key=api_key)
    counts = Counter(lista)
    p_txt = "\n".join([f"{k} ({v})" for k,v in counts.most_common(250)])
    
    sys = """
    Analise HVAC. Ignore arquitetura.
    SAÍDA CSV (;):
    ---TERMINAIS---
    Item;Qtd
    ---EQUIPAMENTOS---
    Tag;Tipo;Detalhe;Qtd
    ---ELETRICA---
    Tag;Desc;Qtd
    """
    try:
        r = client.chat.completions.create(model="gpt-4o", messages=[{"role":"system","content":sys},{"role":"user","content":p_txt}], temperature=0)
        return parse_ia(r.choices[0].message.content)
    except: return {}

def parse_ia(txt):
    res = {"TERMINAIS":[], "EQUIPAMENTOS":[], "ELETRICA":[]}
    curr = None
    if not txt: return res
    for l in txt.split('\n'):
        if "---TERM" in l: curr="TERMINAIS"; continue
        if "---EQUI" in l: curr="EQUIPAMENTOS"; continue
        if "---ELET" in l: curr="ELETRICA"; continue
        if curr and ";" in l and "Tag" not in l: res[curr].append(l.split(';'))
    return res

# ============================================================================
# 5. UI PRINCIPAL
# ============================================================================
uploaded_dxf = st.file_uploader("📂 Carregar Projeto DXF", type=["dxf"])

if uploaded_dxf:
    doc, path, err = carregar_dxf_seguro(uploaded_dxf)
    if err:
        st.error(f"Erro: {err}")
        if path: os.remove(path)
    else:
        layers = sorted([l.dxf.name for l in doc.layers])
        def_idx = [i for i,s in enumerate(layers) if 'DUT' in s.upper() or 'DUCT' in s.upper()]
        
        st.info("Passo 1: Selecione o Layer onde estão as linhas do duto (paredes).")
        sel_layers = st.multiselect("Layer Paredes:", layers, default=[layers[def_idx[0]]] if def_idx else None)
        
        if st.button("🚀 Iniciar Medição Scanline", type="primary"):
            if not sel_layers: st.error("Selecione um layer!")
            else:
                dutos, restos = processar_projeto(doc, sel_layers, unidade_desenho, raio_busca, tolerancia)
                st.session_state['res_dutos'] = dutos
                if restos:
                    st.session_state['res_ia'] = classificar_ia(restos)
                
        if path: os.remove(path)

# ============================================================================
# 6. RESULTADOS
# ============================================================================
if 'res_dutos' in st.session_state:
    dutos = st.session_state['res_dutos']
    ia = st.session_state.get('res_ia', {})
    
    t1, t2, t3, t4 = st.tabs(["🌪️ Dutos (Medição)", "💨 Terminais", "⚙️ Equipamentos", "⚡ Elétrica"])
    
    with t1:
        if dutos:
            df = pd.DataFrame(dutos)
            
            # KPI
            st.markdown(f"### 🔍 Diagnóstico da Medição")
            medidos = df[df['Origem'].str.contains("Medido")].shape[0]
            total = df.shape[0]
            perc = (medidos/total)*100
            
            k1, k2 = st.columns(2)
            k1.metric("Itens Identificados", total)
            k2.metric("Sucesso na Geometria", f"{perc:.1f}%", help="Porcentagem de dutos onde achamos as paredes e medimos o comprimento real.")
            
            if perc < 20:
                st.warning("⚠️ Baixa taxa de medição geométrica. Verifique se selecionou o Layer correto ou ajuste a Tolerância/Unidade no menu.")
            
            # Tabela Agrupada
            df_view = df.groupby(['Largura', 'Altura', 'Origem']).agg(
                Qtd=('Tag', 'count'),
                Comp_Total=('Comp. (m)', 'sum')
            ).reset_index()
            
            st.markdown("#### 📋 Quantitativo Consolidado")
            df_ed = st.data_editor(
                df_view,
                use_container_width=True,
                column_config={
                    "Largura": st.column_config.NumberColumn(format="%d mm"),
                    "Altura": st.column_config.NumberColumn(format="%d mm"),
                    "Comp_Total": st.column_config.NumberColumn(format="%.2f m")
                }
            )
            
            # Totais
            df_ed['Perímetro'] = (2*df_ed['Largura'] + 2*df_ed['Altura'])/1000
            df_ed['Área'] = df_ed['Perímetro'] * df_ed['Comp_Total'] * (1+perda_corte/100)
            
            tot_area = df_ed['Área'].sum()
            tot_peso = tot_area * 5.6
            
            st.divider()
            c1, c2, c3 = st.columns(3)
            c1.metric("Área Total", f"{tot_area:,.2f} m²")
            c2.metric("Peso Total", f"{tot_peso:,.0f} kg")
            c3.metric("Isolamento", f"{tot_area:,.2f} m²" if tipo_isolamento != "Sem Isolamento" else "-")
            
            with st.expander("Ver Detalhe (Linha a Linha) para Auditoria"):
                st.dataframe(df)
        else:
            st.error("Nenhum duto encontrado. Verifique se o texto está no formato '500x300'.")

    with t2:
        if ia.get("TERMINAIS"): st.data_editor(pd.DataFrame(ia["TERMINAIS"], columns=["Item","Qtd"]), use_container_width=True)
        else: st.info("Vazio")
    with t3:
        if ia.get("EQUIPAMENTOS"): st.data_editor(pd.DataFrame(ia["EQUIPAMENTOS"], columns=["Tag","Tipo","Detalhe","Qtd"]), use_container_width=True)
        else: st.info("Vazio")
    with t4:
        if ia.get("ELETRICA"): st.data_editor(pd.DataFrame(ia["ELETRICA"], columns=["Tag","Desc","Qtd"]), use_container_width=True)
        else: st.info("Vazio")
