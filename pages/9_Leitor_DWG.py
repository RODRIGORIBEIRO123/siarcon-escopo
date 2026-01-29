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

st.set_page_config(page_title="Leitor DXF (Auto-Scale)", page_icon="📐", layout="wide")

st.title("📐 Leitor Técnico DXF - Medição Real (Auto-Scale)")
st.markdown("""
**Correção Aplicada:** O sistema agora testa automaticamente se o desenho está em metros, centímetros ou milímetros para cada duto.
Se ele encontrar duas linhas paralelas com a largura correta (ex: 500, 50 ou 0.5), ele mede o **comprimento real** do trecho.
""")

# ============================================================================
# 1. CONFIGURAÇÕES
# ============================================================================
with st.sidebar:
    st.header("⚙️ Configurações")
    
    st.info("ℹ️ O Raio de Busca define quão longe o texto pode estar das linhas do duto.")
    raio_busca = st.number_input("Raio de Busca (Unidades CAD)", value=2.0, help="Aumente se o texto estiver longe do duto. Tente 2.0 (m) ou 2000 (mm).")
    
    comp_padrao = st.number_input("Comp. Padrão (Fallback)", value=1.10, help="Usado APENAS se não encontrarmos as paredes do duto.")
    
    st.divider()
    classe_pressao = st.selectbox("Classe de Pressão", ["Classe A", "Classe B", "Classe C"])
    perda_corte = st.number_input("% Perda / Corte", value=10.0)
    tipo_isolamento = st.selectbox("Isolamento", ["Lã de Vidro", "Borracha Elast.", "Isopor", "Sem Isolamento"])

# ============================================================================
# 2. FUNÇÕES GEOMÉTRICAS (AUTO-SCALE)
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

def limpar_temp(path):
    if path and os.path.exists(path):
        try: os.remove(path)
        except: pass

def get_segmentos(e):
    """Retorna lista de segmentos de linha [(p1, p2, ang, len)]"""
    segs = []
    try:
        if e.dxftype() == 'LINE':
            p1 = (e.dxf.start.x, e.dxf.start.y)
            p2 = (e.dxf.end.x, e.dxf.end.y)
            dx, dy = p2[0]-p1[0], p2[1]-p1[1]
            l = math.hypot(dx, dy)
            if l > 0:
                ang = math.degrees(math.atan2(dy, dx)) % 180
                segs.append({'p1':p1, 'p2':p2, 'len':l, 'ang':ang})
        elif e.dxftype() == 'LWPOLYLINE':
            pts = e.get_points()
            for i in range(len(pts)-1):
                p1, p2 = pts[i], pts[i+1]
                dx, dy = p2[0]-p1[0], p2[1]-p1[1]
                l = math.hypot(dx, dy)
                if l > 0:
                    ang = math.degrees(math.atan2(dy, dx)) % 180
                    segs.append({'p1':p1, 'p2':p2, 'len':l, 'ang':ang})
    except: pass
    return segs

def dist_segmentos_paralelos(s1, s2):
    """Retorna distância entre dois segmentos paralelos"""
    # Ponto médio de s1
    mx, my = (s1['p1'][0]+s1['p2'][0])/2, (s1['p1'][1]+s1['p2'][1])/2
    
    # Reta s2: Ax + By + C = 0
    x1, y1 = s2['p1']
    x2, y2 = s2['p2']
    A = y1 - y2
    B = x2 - x1
    C = x1*y2 - x2*y1
    
    denom = math.hypot(A, B)
    if denom == 0: return float('inf')
    return abs(A*mx + B*my + C) / denom

def medir_duto_auto_scale(msp, texto_obj, largura_alvo, altura_alvo, layers_validos, raio):
    """
    Tenta encontrar paredes paralelas espaçadas por Largura ou Altura.
    Testa escalas: 1.0 (mm), 0.1 (cm), 0.01, 0.001 (m).
    """
    ins = texto_obj.dxf.insert
    tx, ty = ins.x, ins.y
    
    # 1. Coleta linhas próximas (Bounding Box)
    candidatos = []
    
    # Busca Otimizada: Itera apenas primitivas de linha
    for e in msp.query('LINE LWPOLYLINE'):
        if layers_validos and e.dxf.layer not in layers_validos: continue
        
        # Check Bounding Box Rápido
        try:
            if e.dxftype() == 'LINE': px, py = e.dxf.start.x, e.dxf.start.y
            else: px, py = e.get_points()[0][0], e.get_points()[0][1]
            
            if abs(px - tx) > raio or abs(py - ty) > raio: continue
            
            segs = get_segmentos(e)
            candidatos.extend(segs)
        except: pass
        
    if len(candidatos) < 2: return 0.0, "Sem linhas próximas"

    melhor_comp = 0.0
    match_info = "Não medido"
    
    # Escalas possíveis para testar (Texto vs Desenho)
    # Ex: Texto 500. Desenho pode ser 500, 50, 5 ou 0.5
    escalas = [1.0, 0.1, 0.01, 0.001]
    
    # 2. Compara Pares
    found = False
    for i in range(len(candidatos)):
        if found: break
        s1 = candidatos[i]
        for j in range(i+1, len(candidatos)):
            s2 = candidatos[j]
            
            # Check Paralelismo (tolerância 5 graus)
            ang_diff = abs(s1['ang'] - s2['ang'])
            if ang_diff > 5 and ang_diff < 175: continue
            
            # Distância entre paredes
            dist = dist_segmentos_paralelos(s1, s2)
            if dist <= 0.001: continue
            
            # Testa contra Largura e Altura em várias escalas
            for esc in escalas:
                w_test = largura_alvo * esc
                h_test = altura_alvo * esc
                
                # Tolerância de 5% na medida
                tol_w = w_test * 0.05
                tol_h = h_test * 0.05
                
                is_width = abs(dist - w_test) < tol_w
                is_height = abs(dist - h_test) < tol_h
                
                if is_width or is_height:
                    # BINGO! Achamos paredes paralelas na distância certa
                    comp_medio_cad = (s1['len'] + s2['len']) / 2
                    
                    # Converte esse comprimento CAD para METROS Reais
                    # Se esc=1.0 (mm), então CAD=mm -> /1000
                    # Se esc=0.001 (m), então CAD=m -> /1
                    fator_para_metro = 1.0
                    if esc == 1.0: fator_para_metro = 0.001 # mm
                    elif esc == 0.1: fator_para_metro = 0.01 # cm
                    elif esc == 0.01: fator_para_metro = 0.1 # dm
                    elif esc == 0.001: fator_para_metro = 1.0 # m
                    
                    comp_real_m = comp_medio_cad * fator_para_metro
                    
                    # Salva o melhor (mais longo) encontrado
                    if comp_real_m > melhor_comp:
                        melhor_comp = comp_real_m
                        tipo_dim = "L" if is_width else "A"
                        match_info = f"Medido por {tipo_dim} (Escala {esc})"
                        # Não damos break aqui pois pode haver um par melhor (ex: duto mais longo)
                        
    if melhor_comp > 0:
        return melhor_comp, match_info
    
    return 0.0, "Geometria não casou"

# ============================================================================
# 3. PROCESSAMENTO PRINCIPAL
# ============================================================================
def processar_dxf(doc, layers_duto, raio, padrao_estimado):
    msp = doc.modelspace()
    
    dutos = []
    restos = []
    log_debug = []
    
    # Regex flexível: 500x300, 1.300x700
    reg = re.compile(r'(\d{1,4}(?:\.\d{3})*|\d+)\s*[xX*]\s*(\d{1,4}(?:\.\d{3})*|\d+)')
    
    count_txt = 0
    
    for e in msp.query('TEXT MTEXT'):
        txt = e.dxf.text if e.dxftype() == 'TEXT' else e.text
        if not txt: continue
        
        # Limpa
        t_clean = re.sub(r'\\[ACFHQTW].*?;', '', txt).replace('{','').replace('}','').strip().upper()
        if len(t_clean) < 3: continue
        count_txt += 1
        
        match = reg.search(t_clean)
        if match:
            try:
                l_raw = float(match.group(1).replace('.',''))
                a_raw = float(match.group(2).replace('.',''))
                
                if l_raw > 50 and a_raw > 50:
                    # AUTO-SCALE MEASURE
                    comp_m, status = medir_duto_auto_scale(
                        msp, e, l_raw, a_raw, layers_duto, raio
                    )
                    
                    origem = ""
                    final_val = 0.0
                    
                    if comp_m > 0:
                        final_val = comp_m
                        origem = "Medido (Auto)"
                        log_debug.append(f"✅ {t_clean}: {status} -> {final_val:.2f}m")
                    else:
                        final_val = padrao_estimado
                        origem = "Estimado (Padrão)"
                        log_debug.append(f"⚠️ {t_clean}: Falha geo -> Usando {final_val}m")
                        
                    dutos.append({
                        "Largura": l_raw,
                        "Altura": a_raw,
                        "Comp. (m)": final_val,
                        "Origem": origem,
                        "Tag": t_clean
                    })
                    continue
            except: pass
        
        if any(c.isalpha() for c in t_clean):
            restos.append(t_clean)
            
    return dutos, restos, log_debug

# ============================================================================
# 4. IA
# ============================================================================
def classificar_ia(lista):
    if not lista: return {}
    if "openai" not in st.secrets: return {}
    client = OpenAI(api_key=st.secrets["openai"]["api_key"])
    
    c = Counter(lista)
    p = "\n".join([f"{k} (x{v})" for k,v in c.most_common(200)])
    
    sys = """
    Analise HVAC. SAÍDA CSV (;):
    ---TERMINAIS---
    Item;Qtd
    ---EQUIPAMENTOS---
    Tag;Tipo;Detalhe;Qtd
    ---ELETRICA---
    Tag;Desc;Qtd
    """
    try:
        r = client.chat.completions.create(model="gpt-4o", messages=[{"role":"system","content":sys},{"role":"user","content":p}], temperature=0)
        res = {"TERMINAIS":[], "EQUIPAMENTOS":[], "ELETRICA":[]}
        curr = None
        for l in r.choices[0].message.content.split('\n'):
            if "---TERM" in l: curr="TERMINAIS"; continue
            if "---EQUI" in l: curr="EQUIPAMENTOS"; continue
            if "---ELET" in l: curr="ELETRICA"; continue
            if curr and ";" in l and "Tag" not in l: res[curr].append(l.split(';'))
        return res
    except: return {}

# ============================================================================
# 5. UI
# ============================================================================
uploaded_dxf = st.file_uploader("📂 Carregar DXF", type=["dxf"])

if uploaded_dxf:
    doc, temp_path, erro = carregar_dxf_seguro(uploaded_dxf)
    
    if erro:
        st.error(f"Erro: {erro}")
        limpar_temp(temp_path)
    else:
        # Seleção de Layer OBRIGATÓRIA para funcionar bem
        layers = sorted([l.dxf.name for l in doc.layers])
        def_idx = [i for i,s in enumerate(layers) if 'DUT' in s.upper() or 'DUCT' in s.upper()]
        
        st.info("Passo 1: Selecione o Layer onde estão as linhas do duto.")
        sel_layers = st.multiselect("Layer Paredes:", layers, default=[layers[def_idx[0]]] if def_idx else None)
        
        if st.button("🚀 Processar (Auto-Scale)", type="primary"):
            if not sel_layers:
                st.error("Selecione o layer das paredes! Sem isso a medição geométrica não funciona.")
            else:
                with st.spinner("Testando escalas e medindo dutos..."):
                    dutos, restos, logs = processar_dxf(doc, sel_layers, raio_busca, comp_padrao)
                    
                    st.session_state['res_dutos'] = dutos
                    st.session_state['res_logs'] = logs
                    
                    if restos:
                        st.session_state['res_ia'] = classificar_ia(restos)
                    else:
                        st.session_state['res_ia'] = {}
        
        limpar_temp(temp_path)

# ============================================================================
# 6. RESULTADOS
# ============================================================================
if 'res_dutos' in st.session_state:
    dutos = st.session_state['res_dutos']
    ia = st.session_state.get('res_ia', {})
    logs = st.session_state.get('res_logs', [])
    
    t1, t2, t3, t4, t5 = st.tabs(["🌪️ Dutos", "💨 Terminais", "⚙️ Equipamentos", "⚡ Elétrica", "🔍 Diagnóstico"])
    
    with t1:
        if dutos:
            df = pd.DataFrame(dutos)
            
            # KPI
            n_medido = df[df['Origem'].str.contains("Medido")].shape[0]
            n_tot = df.shape[0]
            perc = (n_medido/n_tot)*100
            
            k1, k2 = st.columns(2)
            k1.metric("Trechos Identificados", n_tot)
            k2.metric("Medidos Geometricamente", f"{perc:.1f}%", help="Se estiver baixo, verifique o Raio de Busca ou se selecionou o Layer correto.")
            
            # Tabela
            df_view = df.groupby(['Largura', 'Altura', 'Origem']).agg(
                Qtd=('Tag', 'count'),
                Comp_Total=('Comp. (m)', 'sum')
            ).reset_index()
            
            st.markdown("### 📋 Quantitativo")
            df_ed = st.data_editor(
                df_view,
                use_container_width=True,
                column_config={
                    "Largura": st.column_config.NumberColumn(format="%d mm"),
                    "Altura": st.column_config.NumberColumn(format="%d mm"),
                    "Comp_Total": st.column_config.NumberColumn(format="%.2f m")
                }
            )
            
            # Cálculo Final
            df_ed['Perímetro'] = (2*df_ed['Largura'] + 2*df_ed['Altura'])/1000
            df_ed['Área'] = df_ed['Perímetro'] * df_ed['Comp_Total'] * (1+perda_corte/100)
            
            tot_a = df_ed['Área'].sum()
            tot_p = tot_a * 5.6
            
            st.divider()
            c1, c2, c3 = st.columns(3)
            c1.metric("Área Total", f"{tot_a:,.2f} m²")
            c2.metric("Peso", f"{tot_p:,.0f} kg")
            c3.metric("Isolamento", f"{tot_a:,.2f} m²" if tipo_isolamento!="Sem Isolamento" else "-")
        else:
            st.error("Nenhum duto encontrado.")

    with t2:
        if ia.get("TERMINAIS"): st.data_editor(pd.DataFrame(ia["TERMINAIS"], columns=["Item","Qtd"]), use_container_width=True)
        else: st.info("Vazio")
    with t3:
        if ia.get("EQUIPAMENTOS"): st.data_editor(pd.DataFrame(ia["EQUIPAMENTOS"], columns=["Tag","Tipo","Detalhe","Qtd"]), use_container_width=True)
        else: st.info("Vazio")
    with t4:
        if ia.get("ELETRICA"): st.data_editor(pd.DataFrame(ia["ELETRICA"], columns=["Tag","Desc","Qtd"]), use_container_width=True)
        else: st.info("Vazio")
        
    with t5:
        st.markdown("### Log do Robô")
        st.text_area("Log", "\n".join(logs), height=400)
