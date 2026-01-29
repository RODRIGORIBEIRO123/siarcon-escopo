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

st.set_page_config(page_title="Leitor DXF (Profundo)", page_icon="📐", layout="wide")

st.title("📐 Leitor Técnico DXF - Varredura Profunda")
st.markdown("""
**Correção Aplicada:** O sistema agora lê **Blocos e Atributos** (comuns em tags de projeto), além de Textos simples.
A medição geométrica continua testando automaticamente a escala (m/cm/mm).
""")

# ============================================================================
# 1. CONFIGURAÇÕES
# ============================================================================
with st.sidebar:
    st.header("⚙️ Configurações")
    
    st.info("ℹ️ Raio de Busca: Distância máxima do texto até a linha do duto.")
    raio_busca = st.number_input("Raio de Busca (Unidades CAD)", value=2.0, help="Tente 2.0 se estiver em Metros, ou 2000 se estiver em Milímetros.")
    
    comp_padrao = st.number_input("Comp. Padrão (Fallback)", value=1.10, help="Usado se a geometria não for encontrada.")
    
    st.divider()
    classe_pressao = st.selectbox("Classe de Pressão", ["Classe A", "Classe B", "Classe C"])
    perda_corte = st.number_input("% Perda / Corte", value=10.0)
    tipo_isolamento = st.selectbox("Isolamento", ["Lã de Vidro", "Borracha Elast.", "Isopor", "Sem Isolamento"])

# ============================================================================
# 2. FUNÇÕES DE EXTRAÇÃO (VARREDURA PROFUNDA)
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
    """
    Extrai textos de: TEXT, MTEXT e INSERT (Blocos com Atributos).
    Retorna lista de dicionários: {'texto': str, 'obj': entity}
    """
    lista_textos = []
    
    # 1. Textos Normais
    for e in msp.query('TEXT MTEXT'):
        txt = e.dxf.text if e.dxftype() == 'TEXT' else e.text
        if txt:
            lista_textos.append({'texto': txt, 'obj': e})
            
    # 2. Atributos dentro de Blocos (INSERT)
    for e in msp.query('INSERT'):
        if e.attribs:
            for attrib in e.attribs:
                txt = attrib.dxf.text
                if txt:
                    lista_textos.append({'texto': txt, 'obj': attrib})
                    
    return lista_textos

def limpar_e_parsear(texto_raw):
    """
    Limpa formatação CAD e tenta extrair 500x300 ou 1.300x700.
    """
    # Limpa códigos MTEXT
    t = re.sub(r'\\[ACFHQTW].*?;', '', texto_raw).replace('{', '').replace('}', '').strip().upper()
    
    # Regex robusta para 1.300x700 ou 500x300
    # Captura grupos de digitos e pontos
    match = re.search(r'([\d\.]+)\s*[xX*]\s*([\d\.]+)', t)
    
    if match:
        try:
            # Remove ponto de milhar APENAS se fizer sentido
            # Ex: 1.300 -> 1300.  Mas 1.5 (metro) -> 1.5
            l_str = match.group(1)
            a_str = match.group(2)
            
            # Função auxiliar para converter string numérica
            def to_float(s):
                if s.count('.') == 1 and len(s.split('.')[1]) == 3: # Ex: 1.300
                    return float(s.replace('.', ''))
                return float(s)

            # Para HVAC, geralmente medidas são inteiras em mm (500, 1300)
            # Vamos assumir remoção de ponto se resultar em valor > 50
            l_val = float(l_str.replace('.', ''))
            a_val = float(a_str.replace('.', ''))
            
            if l_val > 50 and a_val > 50:
                return l_val, a_val, t # Retorna valores limpos e o texto original limpo
        except: pass
        
    return None, None, t

# ============================================================================
# 3. MOTOR GEOMÉTRICO (AUTO-SCALE)
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
                p1, p2 = pts[i], pts[i+1]
                dx, dy = p2[0]-p1[0], p2[1]-p1[1]
                l = math.hypot(dx, dy)
                if l > 0:
                    ang = math.degrees(math.atan2(dy, dx)) % 180
                    segs.append({'p1':p1, 'p2':p2, 'len':l, 'ang':ang})
    except: pass
    return segs

def dist_paralela(s1, s2):
    mx, my = (s1['p1'][0]+s1['p2'][0])/2, (s1['p1'][1]+s1['p2'][1])/2
    x1, y1 = s2['p1']; x2, y2 = s2['p2']
    A = y1-y2; B = x2-x1; C = x1*y2 - x2*y1
    denom = math.hypot(A, B)
    if denom == 0: return float('inf')
    return abs(A*mx + B*my + C) / denom

def medir_duto(msp, texto_obj, w_target, h_target, layers, raio):
    ins = texto_obj.dxf.insert
    tx, ty = ins.x, ins.y
    
    # Coleta Candidatos
    candidatos = []
    # Itera sobre geometrias LINE e LWPOLYLINE
    for e in msp.query('LINE LWPOLYLINE'):
        if layers and e.dxf.layer not in layers: continue
        
        # Check Bounding Box
        try:
            if e.dxftype()=='LINE': px, py = e.dxf.start.x, e.dxf.start.y
            else: px, py = e.get_points()[0][0], e.get_points()[0][1]
            if abs(px-tx) > raio or abs(py-ty) > raio: continue
            candidatos.extend(get_segmentos(e))
        except: pass
        
    if len(candidatos) < 2: return 0.0, "Sem linhas próximas"

    melhor_comp = 0.0
    match_info = "Não medido"
    escalas = [1.0, 0.1, 0.01, 0.001] # mm, cm, dm, m
    
    # Compara pares
    for i in range(len(candidatos)):
        s1 = candidatos[i]
        for j in range(i+1, len(candidatos)):
            s2 = candidatos[j]
            
            # Paralelismo
            if abs(s1['ang'] - s2['ang']) > 5 and abs(s1['ang'] - s2['ang']) < 175: continue
            
            dist = dist_paralela(s1, s2)
            if dist < 0.001: continue
            
            # Testa Escalas
            for esc in escalas:
                w_t = w_target * esc
                h_t = h_target * esc
                tol_w, tol_h = w_t * 0.05, h_t * 0.05
                
                if (abs(dist - w_t) < tol_w) or (abs(dist - h_t) < tol_h):
                    comp_cad = (s1['len'] + s2['len']) / 2
                    
                    # Converte para metros
                    f_metro = 1.0
                    if esc == 1.0: f_metro = 0.001 # mm
                    elif esc == 0.1: f_metro = 0.01 # cm
                    
                    comp_real = comp_cad * f_metro
                    if comp_real > melhor_comp:
                        melhor_comp = comp_real
                        match_info = f"Medido (Escala {esc})"
                        
    return melhor_comp, match_info

# ============================================================================
# 4. PROCESSAMENTO
# ============================================================================
def processar(doc, layers_duto, raio, padrao):
    msp = doc.modelspace()
    dutos = []
    restos = []
    logs = []
    
    # Usa a nova função de varredura profunda
    todos_textos = extrair_todos_textos(msp)
    
    for item in todos_textos:
        txt_raw = item['texto']
        e = item['obj']
        
        largura, altura, t_limpo = limpar_e_parsear(txt_raw)
        
        if largura:
            # Tenta Medir
            comp_m, status = medir_duto(msp, e, largura, altura, layers_duto, raio)
            
            val_final = comp_m if comp_m > 0 else padrao
            origem = "Medido (Auto)" if comp_m > 0 else "Estimado (Padrão)"
            
            dutos.append({
                "Largura": largura,
                "Altura": altura,
                "Comp. (m)": val_final,
                "Origem": origem,
                "Tag": t_limpo
            })
            logs.append(f"✅ {t_limpo}: {status} -> {val_final:.2f}m")
        else:
            if t_limpo and any(c.isalpha() for c in t_limpo):
                restos.append(t_limpo)
                
    return dutos, restos, logs

# ============================================================================
# 5. IA
# ============================================================================
def ia_class(lista):
    if not lista: return {}
    # Uso seguro da chave
    api_key = st.secrets.get("openai", {}).get("api_key")
    if not api_key: return {}
    
    client = OpenAI(api_key=api_key)
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
# 6. UI
# ============================================================================
uploaded_dxf = st.file_uploader("📂 Carregar DXF", type=["dxf"])

if uploaded_dxf:
    doc, temp_path, erro = carregar_dxf_seguro(uploaded_dxf)
    
    if erro:
        st.error(f"Erro: {erro}")
        limpar_temp(temp_path)
    else:
        layers = sorted([l.dxf.name for l in doc.layers])
        def_idx = [i for i,s in enumerate(layers) if 'DUT' in s.upper() or 'DUCT' in s.upper() or 'REDE' in s.upper()]
        
        st.info("Passo 1: Selecione o Layer das Paredes do Duto.")
        sel_layers = st.multiselect("Layer Paredes:", layers, default=[layers[def_idx[0]]] if def_idx else None)
        
        if st.button("🚀 Processar", type="primary"):
            with st.spinner("Varrendo Blocos, Textos e Geometria..."):
                dutos, restos, logs = processar(doc, sel_layers, raio_busca, comp_padrao)
                
                st.session_state['res_dutos'] = dutos
                st.session_state['res_logs'] = logs
                if restos: st.session_state['res_ia'] = ia_class(restos)
                else: st.session_state['res_ia'] = {}
        
        limpar_temp(temp_path)

# ============================================================================
# 7. EXIBIÇÃO
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
            n_med = df[df['Origem'].str.contains("Medido")].shape[0]
            perc = (n_med/len(df))*100 if len(df)>0 else 0
            
            k1, k2 = st.columns(2)
            k1.metric("Trechos Identificados", len(df))
            k2.metric("Medidos Geometricamente", f"{perc:.1f}%")
            
            # Tabela
            df_view = df.groupby(['Largura', 'Altura', 'Origem']).agg(
                Qtd=('Tag', 'count'),
                Comp_Total=('Comp. (m)', 'sum')
            ).reset_index()
            
            st.markdown("### 📋 Quantitativo")
            df_ed = st.data_editor(
                df_view, use_container_width=True,
                column_config={
                    "Largura": st.column_config.NumberColumn(format="%d mm"),
                    "Altura": st.column_config.NumberColumn(format="%d mm"),
                    "Comp_Total": st.column_config.NumberColumn(format="%.2f m")
                }
            )
            
            # Totais
            df_ed['Perímetro'] = (2*df_ed['Largura'] + 2*df_ed['Altura'])/1000
            df_ed['Área'] = df_ed['Perímetro'] * df_ed['Comp_Total'] * (1+perda_corte/100)
            
            tot_a = df_ed['Área'].sum()
            
            st.divider()
            c1, c2, c3 = st.columns(3)
            c1.metric("Área Total", f"{tot_a:,.2f} m²")
            c2.metric("Peso", f"{tot_a*5.6:,.0f} kg")
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
        st.text_area("Log de Leitura", "\n".join(logs), height=300)
