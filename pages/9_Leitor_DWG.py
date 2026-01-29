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

st.set_page_config(page_title="Leitor DXF (Restaurado)", page_icon="📐", layout="wide")

st.title("📐 Leitor Técnico DXF - Alta Precisão")
st.markdown("""
**Versão Restaurada:** Motor geométrico de alta precisão (Wall Matcher).
**Filtros Ativos:** Dutos (Medição Real), Grelhas (Final 25), Cortes (Texto).
""")

# ============================================================================
# 1. CONFIGURAÇÕES
# ============================================================================
with st.sidebar:
    st.header("⚙️ Configurações")
    
    st.info("ℹ️ Raio de Busca: Aumente se o texto estiver longe das linhas.")
    raio_busca = st.number_input("Raio de Busca (Unidades CAD)", value=2.0, help="Ex: 2.0 (m) ou 2000 (mm).")
    
    comp_padrao = st.number_input("Comp. Padrão (Se falhar geometria)", value=1.10)
    
    st.divider()
    classe_pressao = st.selectbox("Classe de Pressão", ["Classe A", "Classe B", "Classe C"])
    perda_corte = st.number_input("% Perda / Corte", value=10.0)
    tipo_isolamento = st.selectbox("Isolamento", ["Lã de Vidro", "Borracha Elast.", "Isopor", "Sem Isolamento"])

# ============================================================================
# 2. CARREGAMENTO
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

def limpar_e_parsear(texto_raw):
    # Remove formatação MTEXT
    t = re.sub(r'\\[ACFHQTW].*?;', '', texto_raw).replace('{', '').replace('}', '').strip().upper()
    
    # Radar de Cortes
    if "CORTE" in t or "SECTION" in t or "VISTA" in t:
        return None, None, t
    
    # Regex Medidas
    match = re.search(r'([\d\.]+)\s*[xX*]\s*([\d\.]+)', t)
    if match:
        try:
            l_str = match.group(1)
            a_str = match.group(2)
            # Remove ponto milhar se > 50
            l_val = float(l_str.replace('.', '')) if '.' in l_str and len(l_str) > 4 else float(l_str)
            a_val = float(a_str.replace('.', '')) if '.' in a_str and len(a_str) > 4 else float(a_str)
            
            if l_val > 50 and a_val > 50:
                return l_val, a_val, t
        except: pass
    return None, None, t

# ============================================================================
# 3. MOTOR GEOMÉTRICO (COM A CORREÇÃO DE POLILINHA)
# ============================================================================
def get_segmentos(e):
    segs = []
    try:
        if e.dxftype() == 'LINE':
            p1 = (e.dxf.start.x, e.dxf.start.y)
            p2 = (e.dxf.end.x, e.dxf.end.y)
            l = math.hypot(p2[0]-p1[0], p2[1]-p1[1])
            if l > 0:
                ang = math.degrees(math.atan2(p2[1]-p1[1], p2[0]-p1[0])) % 180
                segs.append({'p1':p1, 'p2':p2, 'len':l, 'ang':ang})
                
        elif e.dxftype() == 'LWPOLYLINE':
            pts = e.get_points()
            for i in range(len(pts)-1):
                # --- CORREÇÃO CRÍTICA AQUI ---
                # Garante que pegamos apenas (x,y), evitando o ValueError
                p1 = pts[i][:2]
                p2 = pts[i+1][:2]
                
                dx, dy = p2[0]-p1[0], p2[1]-p1[1]
                l = math.hypot(dx, dy)
                if l > 0:
                    ang = math.degrees(math.atan2(dy, dx)) % 180
                    segs.append({'p1':p1, 'p2':p2, 'len':l, 'ang':ang})
    except: pass
    return segs

def dist_paralela(s1, s2):
    try:
        mx, my = (s1['p1'][0]+s1['p2'][0])/2, (s1['p1'][1]+s1['p2'][1])/2
        x1, y1 = s2['p1'][0], s2['p1'][1]
        x2, y2 = s2['p2'][0], s2['p2'][1]
        A = y1 - y2
        B = x2 - x1
        C = x1*y2 - x2*y1
        denom = math.hypot(A, B)
        if denom == 0: return float('inf')
        return abs(A*mx + B*my + C) / denom
    except: return float('inf')

def medir_duto_geom(msp, texto_obj, w_target, h_target, layers, raio):
    ins = texto_obj.dxf.insert
    tx, ty = ins.x, ins.y
    
    candidatos = []
    # Busca Otimizada em ModelSpace (Sem entrar em blocos para não poluir)
    for e in msp.query('LINE LWPOLYLINE'):
        if layers and e.dxf.layer not in layers: continue
        try:
            if e.dxftype()=='LINE': 
                px, py = e.dxf.start.x, e.dxf.start.y
            else: 
                # Pega primeiro ponto com segurança
                raw_pts = e.get_points()
                px, py = raw_pts[0][0], raw_pts[0][1]
                
            if abs(px-tx) > raio or abs(py-ty) > raio: continue
            candidatos.extend(get_segmentos(e))
        except: pass
        
    if len(candidatos) < 2: return 0.0, "Sem linhas"

    melhor_comp = 0.0
    match_info = "Não medido"
    escalas = [1.0, 0.1, 0.01, 0.001]
    
    for i in range(len(candidatos)):
        s1 = candidatos[i]
        for j in range(i+1, len(candidatos)):
            s2 = candidatos[j]
            
            if abs(s1['ang'] - s2['ang']) > 5 and abs(s1['ang'] - s2['ang']) < 175: continue
            
            dist = dist_paralela(s1, s2)
            if dist < 0.001: continue
            
            for esc in escalas:
                w_t = w_target * esc
                h_t = h_target * esc
                tol_w, tol_h = w_t * 0.05, h_t * 0.05
                
                match_w = abs(dist - w_t) < tol_w
                match_h = abs(dist - h_t) < tol_h
                
                if match_w or match_h:
                    comp_cad = (s1['len'] + s2['len']) / 2
                    
                    f_metro = 1.0
                    if esc == 1.0: f_metro = 0.001
                    elif esc == 0.1: f_metro = 0.01
                    
                    comp_real = comp_cad * f_metro
                    if comp_real > melhor_comp:
                        melhor_comp = comp_real
                        match_info = f"Medido (Esc {esc})"
                        
    return melhor_comp, match_info

# ============================================================================
# 4. PROCESSAMENTO
# ============================================================================
def processar(doc, layers_duto, raio, padrao):
    msp = doc.modelspace()
    dutos = []
    restos = []
    cortes = []
    logs = []
    
    # Varredura Clássica (TEXT/MTEXT no ModelSpace) - Mais confiável para geometria
    total_txt = 0
    for e in msp.query('TEXT MTEXT'):
        txt_raw = e.dxf.text if e.dxftype() == 'TEXT' else e.text
        if not txt_raw: continue
        total_txt += 1
        
        l, a, t = limpar_e_parsear(txt_raw)
        
        if l:
            # Filtro Grelha (Final 25)
            eh_grelha = str(int(l)).endswith('25') or str(int(a)).endswith('25')
            
            if eh_grelha:
                restos.append(t)
                logs.append(f"💨 Grelha: {t}")
            else:
                # Duto -> Geometria
                comp_m, status = medir_duto_geom(msp, e, l, a, layers_duto, raio)
                
                val_final = comp_m if comp_m > 0 else padrao
                orig = "Medido (Auto)" if comp_m > 0 else "Estimado (Padrão)"
                
                dutos.append({
                    "Largura": l, "Altura": a, "Comp. (m)": val_final,
                    "Origem": orig, "Tag": t
                })
                logs.append(f"✅ Duto: {t} -> {val_final:.2f}m ({status})")
                
        else:
            if t and "CORTE" in t or "SECTION" in t:
                cortes.append(t)
            elif t and any(c.isalpha() for c in t):
                restos.append(t)
                
    return dutos, restos, cortes, logs

def ia_class(lista):
    if not lista: return {}
    key = st.secrets.get("openai", {}).get("api_key")
    if not key: return {}
    
    client = OpenAI(api_key=key)
    c = Counter(lista)
    p = "\n".join([f"{k} (x{v})" for k,v in c.most_common(200)])
    
    sys = """
    Analise HVAC. SAÍDA CSV (;):
    ---TERMINAIS---
    Item;Qtd
    Grelha 425x125;10
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
    doc, tmp, err = carregar_dxf_seguro(uploaded_dxf)
    if err:
        st.error(f"Erro: {err}")
        limpar_temp(tmp)
    else:
        layers = sorted([l.dxf.name for l in doc.layers])
        idx = [i for i,s in enumerate(layers) if 'DUT' in s.upper() or 'DUCT' in s.upper()]
        
        st.info("Passo 1: Selecione o Layer das Paredes.")
        sel = st.multiselect("Layer Paredes:", layers, default=[layers[idx[0]]] if idx else None)
        
        if st.button("🚀 Processar", type="primary"):
            with st.spinner("Analisando Geometria..."):
                dutos, restos, cortes, logs = processar(doc, sel, raio_busca, comp_padrao)
                st.session_state['res_dutos'] = dutos
                st.session_state['res_cortes'] = cortes
                st.session_state['res_logs'] = logs
                st.session_state['res_ia'] = ia_class(restos) if restos else {}
        
        limpar_temp(tmp)

# ============================================================================
# 6. RESULTADOS
# ============================================================================
if 'res_dutos' in st.session_state:
    dutos = st.session_state['res_dutos']
    ia = st.session_state.get('res_ia', {})
    cortes = st.session_state.get('res_cortes', [])
    logs = st.session_state.get('res_logs', [])
    
    t1, t2, t3, t4, t5, t6 = st.tabs(["🌪️ Dutos", "💨 Terminais", "⚙️ Equipamentos", "⚡ Elétrica", "✂️ Cortes", "🔍 Log"])
    
    with t1:
        if dutos:
            df = pd.DataFrame(dutos)
            
            # KPI
            n_med = df[df['Origem'].str.contains("Medido")].shape[0]
            perc = (n_med/len(df))*100 if len(df)>0 else 0
            
            k1, k2 = st.columns(2)
            k1.metric("Trechos", len(df))
            k2.metric("Sucesso Geometria", f"{perc:.1f}%")
            
            df_view = df.groupby(['Largura', 'Altura', 'Origem']).agg(
                Qtd=('Tag', 'count'), Comp_Total=('Comp. (m)', 'sum')
            ).reset_index()
            
            st.markdown("### 📋 Quantitativo Dutos")
            df_ed = st.data_editor(
                df_view, use_container_width=True,
                column_config={"Comp_Total": st.column_config.NumberColumn(format="%.2f m")}
            )
            
            df_ed['Perímetro'] = (2*df_ed['Largura'] + 2*df_ed['Altura'])/1000
            df_ed['Área'] = df_ed['Perímetro'] * df_ed['Comp_Total'] * (1+perda_corte/100)
            tot_a = df_ed['Área'].sum()
            
            st.divider()
            c1, c2, c3 = st.columns(3)
            c1.metric("Área Total", f"{tot_a:,.2f} m²")
            c2.metric("Peso", f"{tot_a*5.6:,.0f} kg")
            c3.metric("Isolamento", f"{tot_a:,.2f} m²" if tipo_isolamento!="Sem Isolamento" else "-")
        else: st.warning("Nenhum duto encontrado.")

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
        if cortes: st.table(pd.DataFrame(cortes, columns=["Cortes Identificados"]))
        else: st.info("Nenhum corte identificado.")
    with t6:
        st.text_area("Log", "\n".join(logs), height=300)
