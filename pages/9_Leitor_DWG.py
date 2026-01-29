import streamlit as st
import ezdxf
from ezdxf import recover
import pandas as pd
import tempfile
import os
import re
import math
import io
from openai import OpenAI
from collections import Counter

# --- 🔒 SEGURANÇA ---
if 'logado' not in st.session_state or not st.session_state['logado']:
    st.warning("🔒 Acesso negado. Faça login no Dashboard.")
    st.stop()

st.set_page_config(page_title="Leitor DXF (Memorial)", page_icon="📐", layout="wide")

st.title("📐 Leitor Técnico DXF - Memorial de Cálculo")
st.markdown("""
**Status:** Motor Geométrico Ativo.
1. **Dutos:** O sistema procura as paredes do duto baseadas na largura escrita (ex: 500) e mede o comprimento real.
2. **Grelhas:** Medidas terminadas em '25' (ex: 425x125) são automaticamente separadas como terminais.
3. **Memorial:** Gera planilha com bitola de chapa e peso por trecho.
""")

# ============================================================================
# 1. CONFIGURAÇÕES
# ============================================================================
with st.sidebar:
    st.header("⚙️ Configurações")
    
    # Tolerância geométrica
    st.info("ℹ️ Raio de Busca: Distância máx do texto até a linha.")
    raio_busca = st.number_input("Raio de Busca (Unidades CAD)", value=2.0, help="2.0 para Metros, 2000 para Milímetros.")
    
    # Fallback
    comp_padrao = st.number_input("Comp. Padrão (Se falhar geometria)", value=1.10)
    
    st.divider()
    classe_pressao = st.selectbox("Classe de Pressão", ["Classe A", "Classe B", "Classe C"])
    perda_corte = st.number_input("% Perda / Corte", value=10.0)
    tipo_isolamento = st.selectbox("Isolamento", ["Lã de Vidro", "Borracha Elast.", "Isopor", "Sem Isolamento"])

# ============================================================================
# 2. CARREGAMENTO E TEXTO
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

def extrair_todos_textos(msp):
    lista = []
    # Textos
    for e in msp.query('TEXT MTEXT'):
        txt = e.dxf.text if e.dxftype() == 'TEXT' else e.text
        if txt: lista.append({'texto': txt, 'obj': e})
    # Blocos (Atributos)
    for e in msp.query('INSERT'):
        if e.attribs:
            for a in e.attribs:
                t = a.dxf.text
                if t: lista.append({'texto': t, 'obj': a})
    return lista

def limpar_parsear(txt_raw):
    # Limpa MTEXT
    t = re.sub(r'\\[ACFHQTW].*?;', '', txt_raw).replace('{','').replace('}','').strip().upper()
    # Regex 1.300x700
    m = re.search(r'([\d\.]+)\s*[xX*]\s*([\d\.]+)', t)
    if m:
        try:
            l_str = m.group(1)
            a_str = m.group(2)
            # Remove ponto milhar se > 50
            l_val = float(l_str.replace('.','')) if '.' in l_str and len(l_str)>4 else float(l_str)
            a_val = float(a_str.replace('.','')) if '.' in a_str and len(a_str)>4 else float(a_str)
            if l_val > 50 and a_val > 50:
                return l_val, a_val, t
        except: pass
    return None, None, t

# ============================================================================
# 3. MOTOR GEOMÉTRICO
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
                # Correção LWPOLYLINE (Pega só X,Y)
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
        x1, y1 = s2['p1']; x2, y2 = s2['p2']
        A = y1-y2; B = x2-x1; C = x1*y2 - x2*y1
        denom = math.hypot(A, B)
        if denom == 0: return float('inf')
        return abs(A*mx + B*my + C) / denom
    except: return float('inf')

def medir_duto_geom(msp, texto_obj, w_target, h_target, layers, raio):
    """Procura paredes paralelas com afastamento = largura ou altura."""
    ins = texto_obj.dxf.insert
    tx, ty = ins.x, ins.y
    
    candidatos = []
    # Coleta linhas próximas
    for e in msp.query('LINE LWPOLYLINE'):
        if layers and e.dxf.layer not in layers: continue
        try:
            if e.dxftype()=='LINE': px, py = e.dxf.start.x, e.dxf.start.y
            else: 
                pts = e.get_points()
                px, py = pts[0][0], pts[0][1]
            if abs(px-tx) > raio or abs(py-ty) > raio: continue
            candidatos.extend(get_segmentos(e))
        except: pass
        
    if len(candidatos) < 2: return 0.0, "Sem linhas"

    melhor_comp = 0.0
    match_info = "Não medido"
    # Escalas comuns (mm, cm, m)
    escalas = [1.0, 0.1, 0.01, 0.001]
    
    for i in range(len(candidatos)):
        s1 = candidatos[i]
        for j in range(i+1, len(candidatos)):
            s2 = candidatos[j]
            
            # Checa paralelismo (5 graus)
            if abs(s1['ang'] - s2['ang']) > 5 and abs(s1['ang'] - s2['ang']) < 175: continue
            
            # Distancia entre as linhas
            dist = dist_paralela(s1, s2)
            if dist < 0.001: continue
            
            # Testa contra Largura e Altura em várias escalas
            for esc in escalas:
                w_t = w_target * esc
                h_t = h_target * esc
                tol_w, tol_h = w_t * 0.05, h_t * 0.05
                
                match_w = abs(dist - w_t) < tol_w
                match_h = abs(dist - h_t) < tol_h
                
                if match_w or match_h:
                    # BINGO: Paredes encontradas
                    comp_cad = (s1['len'] + s2['len']) / 2
                    
                    # Converte comp_cad para Metros Reais
                    f_metro = 1.0
                    if esc == 1.0: f_metro = 0.001 # mm
                    elif esc == 0.1: f_metro = 0.01 # cm
                    
                    comp_real = comp_cad * f_metro
                    
                    # Guarda o maior trecho encontrado
                    if comp_real > melhor_comp:
                        melhor_comp = comp_real
                        tipo = "Largura" if match_w else "Altura"
                        match_info = f"Medido p/ {tipo} (Escala {esc})"
                        
    return melhor_comp, match_info

# ============================================================================
# 4. PROCESSAMENTO
# ============================================================================
def processar(doc, layers_duto, raio, padrao):
    msp = doc.modelspace()
    dutos = []
    restos = []
    logs = []
    
    lista = extrair_todos_textos(msp)
    
    for item in lista:
        l, a, t = limpar_parsear(item['texto'])
        obj = item['obj']
        
        if l:
            # --- FILTRO GRELHA (Termina em 25) ---
            eh_grelha = str(int(l)).endswith('25') or str(int(a)).endswith('25')
            
            if eh_grelha:
                restos.append(t)
                logs.append(f"💨 Grelha detectada: {t}")
            else:
                # É Duto -> Medir Geometria
                comp_m, status = medir_duto_geom(msp, obj, l, a, layers_duto, raio)
                
                val_final = comp_m if comp_m > 0 else padrao
                orig = "Medido (Auto)" if comp_m > 0 else "Estimado (Padrão)"
                
                dutos.append({
                    "Largura": l, "Altura": a, "Comp. (m)": val_final,
                    "Origem": orig, "Tag": t
                })
                logs.append(f"✅ Duto: {t} -> {val_final:.2f}m ({status})")
        else:
            # Texto sem medida clara -> IA
            if t and any(c.isalpha() for c in t):
                restos.append(t)
                
    return dutos, restos, logs

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
            with st.spinner("Medindo geometria..."):
                dutos, restos, logs = processar(doc, sel, raio_busca, comp_padrao)
                st.session_state['res_dutos'] = dutos
                st.session_state['res_logs'] = logs
                st.session_state['res_ia'] = ia_class(restos) if restos else {}
        
        limpar_temp(tmp)

# ============================================================================
# 6. RESULTADOS E MEMORIAL
# ============================================================================
if 'res_dutos' in st.session_state:
    dutos = st.session_state['res_dutos']
    ia = st.session_state.get('res_ia', {})
    logs = st.session_state.get('res_logs', [])
    
    t1, t2, t3, t4, t5 = st.tabs(["🌪️ Dutos", "💨 Terminais", "⚙️ Equipamentos", "⚡ Elétrica", "🔍 Diagnóstico"])
    
    with t1:
        if dutos:
            # --- PROCESSAMENTO DO MEMORIAL DE CÁLCULO ---
            lista_memorial = []
            
            for item in dutos:
                larg = item['Largura']
                alt = item['Altura']
                comp = item['Comp. (m)']
                
                # Regra de Bitola (Padrão Baixa Pressão SMACNA/ABNT)
                maior_lado = max(larg, alt)
                bitola = 26
                peso_m2 = 4.2 # Peso aprox aço galv #26
                
                if maior_lado <= 300: 
                    bitola = 26; peso_m2 = 4.20
                elif maior_lado <= 750: 
                    bitola = 24; peso_m2 = 5.40
                elif maior_lado <= 1500: 
                    bitola = 22; peso_m2 = 6.80
                elif maior_lado <= 2000: 
                    bitola = 20; peso_m2 = 8.60
                else: 
                    bitola = 18; peso_m2 = 11.00
                
                # Cálculo de Área e Peso do Trecho
                perimetro = (2*larg + 2*alt) / 1000
                area_trecho = perimetro * comp * (1 + perda_corte/100)
                peso_trecho = area_trecho * peso_m2
                
                lista_memorial.append({
                    "Tag Original": item['Tag'],
                    "Largura (mm)": larg,
                    "Altura (mm)": alt,
                    "Comprimento (m)": comp,
                    "Área (m²)": area_trecho,
                    "Bitola (MSG)": f"#{bitola}",
                    "Peso Unit (kg)": peso_trecho
                })

            df_mem = pd.DataFrame(lista_memorial)
            
            # Tabela Resumo (Agrupado por Bitola)
            df_resumo = df_mem.groupby("Bitola (MSG)")["Peso Unit (kg)"].sum().reset_index()
            df_resumo.rename(columns={"Peso Unit (kg)": "Peso Total (kg)"}, inplace=True)
            
            # --- EXIBIÇÃO NA TELA ---
            # KPI
            n_med = pd.DataFrame(dutos)[pd.DataFrame(dutos)['Origem'].str.contains("Medido")].shape[0]
            perc = (n_med/len(dutos))*100 if len(dutos)>0 else 0
            
            c1, c2 = st.columns(2)
            c1.metric("Trechos Duto", len(dutos))
            c2.metric("Sucesso Geometria", f"{perc:.1f}%")
            
            st.markdown("### 📊 Resumo de Pesos por Bitola")
            st.dataframe(df_resumo.style.format({"Peso Total (kg)": "{:.1f}"}), use_container_width=True)
            
            st.markdown("### 📋 Memorial Detalhado (Preview)")
            st.dataframe(df_mem.head(50).style.format({
                "Largura (mm)": "{:.0f}", "Altura (mm)": "{:.0f}", 
                "Comprimento (m)": "{:.2f}", "Área (m²)": "{:.2f}", "Peso Unit (kg)": "{:.2f}"
            }))
            
            # --- GERAR EXCEL ---
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                df_mem.to_excel(writer, sheet_name='Memorial Detalhado', index=False)
                df_resumo.to_excel(writer, sheet_name='Resumo de Cargas', index=False)
                
            st.download_button(
                label="📥 Baixar Planilha Memorial (.xlsx)",
                data=output.getvalue(),
                file_name="Memorial_Dutos_SiArCon.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

        else:
            st.warning("Nenhum duto encontrado.")

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
        st.text_area("Log", "\n".join(logs), height=300)
