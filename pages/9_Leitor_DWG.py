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

st.set_page_config(page_title="Leitor DXF (Híbrido)", page_icon="📐", layout="wide")

st.title("📐 Leitor Técnico DXF - Modo Híbrido")
st.markdown("""
**Correção Aplicada:** 1. **Regex Flexível:** Lê formatos como `1.300x700`, `500 x 300` e `500X300`.
2. **Fallback Automático:** Se não conseguir medir as linhas do desenho (geometria), o sistema usa o **Comprimento Padrão** para não zerar o orçamento.
""")

# ============================================================================
# 1. CONFIGURAÇÕES
# ============================================================================
with st.sidebar:
    st.header("⚙️ Configurações")
    
    unidade_desenho = st.selectbox(
        "Unidade do CAD:", 
        ["Milímetros (1u=1mm)", "Centímetros (1u=1cm)", "Metros (1u=1m)"],
        index=0
    )
    
    # Tolerâncias
    raio_busca_val = 1500.0 if "Milímetros" in unidade_desenho else (150.0 if "Centímetros" in unidade_desenho else 1.5)
    raio_busca = st.number_input("Raio de Busca (Geometria)", value=raio_busca_val, help="Distância máx do texto até a linha do duto.")
    
    comp_padrao = st.number_input("Comp. Padrão (Estimativa)", value=1.10, help="Usado quando a geometria falha.")
    
    st.divider()
    classe_pressao = st.selectbox("Classe de Pressão", ["Classe A", "Classe B", "Classe C"])
    perda_corte = st.number_input("% Perda / Corte", value=10.0)
    tipo_isolamento = st.selectbox("Isolamento", ["Lã de Vidro", "Borracha Elast.", "Isopor", "Sem Isolamento"])

# ============================================================================
# 2. FUNÇÕES AUXILIARES
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

def limpar_texto_cad(texto_raw):
    """Remove formatação MTEXT do AutoCAD (\\A1; \\P etc)"""
    if not texto_raw: return ""
    # Remove códigos de controle
    t = re.sub(r'\\[ACFHQTW].*?;', '', texto_raw) # \A1;
    t = re.sub(r'\\P|\\N', ' ', t) # Quebra de linha
    t = t.replace('{', '').replace('}', '') # Chaves
    return t.strip().upper()

def parse_medida(texto_limpo):
    """
    Tenta extrair Largura e Altura de strings sujas.
    Aceita: 1.300x700, 500 x 300, 500*300
    """
    # Regex 'Gulosa': Pega (numeros+pontos) X (numeros+pontos)
    match = re.search(r'([\d\.]+)\s*[xX*]\s*([\d\.]+)', texto_limpo)
    if match:
        try:
            l_str = match.group(1).replace('.', '') # Remove ponto de milhar (1.300 -> 1300)
            a_str = match.group(2).replace('.', '')
            
            l_val = float(l_str)
            a_val = float(a_str)
            
            # Validação básica de HVAC (ninguém projeta duto < 50mm)
            if l_val >= 50 and a_val >= 50:
                return l_val, a_val
        except: pass
    return None, None

# ============================================================================
# 3. MOTOR DE GEOMETRIA (SIMPLIFICADO E ROBUSTO)
# ============================================================================
def get_len(e):
    try:
        if e.dxftype() == 'LINE':
            return math.hypot(e.dxf.end.x - e.dxf.start.x, e.dxf.end.y - e.dxf.start.y)
        elif e.dxftype() == 'LWPOLYLINE':
            pts = e.get_points()
            l = 0
            for i in range(len(pts)-1):
                l += math.hypot(pts[i+1][0]-pts[i][0], pts[i+1][1]-pts[i][1])
            return l
    except: return 0
    return 0

def tentar_medir_geometria(msp, texto_dxf, largura_alvo, layers_validos, fator_conv, raio):
    """Retorna (Comprimento Medido, Sucesso)"""
    w_cad = largura_alvo * fator_conv
    
    ins = texto_dxf.dxf.insert
    tx, ty = ins.x, ins.y
    
    melhor_comp = 0.0
    sucesso = False
    
    # Coleta linhas próximas (Bounding Box)
    # Para performance, não iteramos tudo se houver muitos objetos
    entidades = msp.query('LINE LWPOLYLINE')
    
    candidatos = []
    for e in entidades:
        if layers_validos and e.dxf.layer not in layers_validos: continue
        
        try:
            # Check distância Manhattan rápido
            if e.dxftype() == 'LINE': px, py = e.dxf.start.x, e.dxf.start.y
            else: px, py = e.get_points()[0][0], e.get_points()[0][1]
            
            if abs(px - tx) > raio or abs(py - ty) > raio: continue
            
            l = get_len(e)
            if l > 0: candidatos.append(l)
        except: pass
        
    # Heurística: Se acharmos uma linha cujo comprimento é maior que a metade da largura,
    # assumimos que é a parede. (Dutos costumam ser compridos).
    if candidatos:
        candidatos.sort(reverse=True)
        top_len = candidatos[0]
        
        # Se a linha mais longa perto do texto for razoável, usamos ela
        if top_len > (w_cad * 0.4): # Tolerância de 40% da largura
            melhor_comp = top_len
            sucesso = True
            
    return melhor_comp, sucesso

# ============================================================================
# 4. PROCESSAMENTO PRINCIPAL
# ============================================================================
def processar_dxf(doc, layers_duto, unid_str, raio, padrao_estimado):
    msp = doc.modelspace()
    
    # Fatores
    if "Metros" in unid_str:
        fator_txt_cad = 0.001
        fator_cad_m = 1.0
    elif "Centímetros" in unid_str:
        fator_txt_cad = 0.1
        fator_cad_m = 0.01
    else: # mm
        fator_txt_cad = 1.0
        fator_cad_m = 0.001
        
    dutos = []
    restos = []
    debug_log = []
    
    total_txt = 0
    
    for e in msp.query('TEXT MTEXT'):
        raw = e.dxf.text if e.dxftype() == 'TEXT' else e.text
        if not raw: continue
        
        t_clean = limpar_texto_cad(raw)
        if len(t_clean) < 3: continue
        
        total_txt += 1
        
        # 1. Tenta identificar DUTO (Regex)
        largura, altura = parse_medida(t_clean)
        
        if largura and altura:
            # TENTA MEDIR GEOMETRIA
            comp_cad, sucesso_geo = tentar_medir_geometria(
                msp, e, largura, layers_duto, fator_txt_cad, raio
            )
            
            comp_final_m = 0.0
            origem = ""
            
            if sucesso_geo:
                comp_final_m = comp_cad * fator_cad_m
                origem = "Medido (Geometria)"
            else:
                # FALLBACK: Se falhar a geometria, usa estimativa!
                comp_final_m = padrao_estimado
                origem = "Estimado (Padrão)"
                
            dutos.append({
                "Largura": largura,
                "Altura": altura,
                "Comp. (m)": comp_final_m,
                "Origem": origem,
                "Tag": t_clean
            })
            debug_log.append(f"✅ DUTO: {t_clean} -> {largura}x{altura} | {origem} ({comp_final_m:.2f}m)")
        else:
            # Se não for duto, guarda pra IA
            if any(c.isalpha() for c in t_clean):
                restos.append(t_clean)
                debug_log.append(f"❓ RESTO: {t_clean}")
            else:
                debug_log.append(f"🗑️ IGNORADO: {t_clean}")
                
    return dutos, restos, debug_log, total_txt

# ============================================================================
# 5. IA
# ============================================================================
def classificar_ia(lista):
    if not lista: return {}
    if "openai" not in st.secrets: return {}
    
    client = OpenAI(api_key=st.secrets["openai"]["api_key"])
    counts = Counter(lista)
    p_txt = "\n".join([f"{k} (x{v})" for k,v in counts.most_common(200)])
    
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
        r = client.chat.completions.create(model="gpt-4o", messages=[{"role":"system","content":sys},{"role":"user","content":p_txt}], temperature=0)
        
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
        # Seleção de Layer Opcional
        layers = sorted([l.dxf.name for l in doc.layers])
        def_idx = [i for i,s in enumerate(layers) if 'DUT' in s.upper() or 'DUCT' in s.upper()]
        
        st.info("Passo 1: Selecione o Layer das Paredes (Opcional, mas melhora a geometria).")
        sel_layers = st.multiselect("Layer Paredes:", layers, default=[layers[def_idx[0]]] if def_idx else None)
        
        if st.button("🚀 Processar Arquivo", type="primary"):
            with st.spinner("Analisando textos e geometria..."):
                dutos, restos, logs, total_lidos = processar_dxf(doc, sel_layers, unidade_desenho, raio_busca, comp_padrao)
                
                st.session_state['res_dutos'] = dutos
                st.session_state['res_logs'] = logs
                st.session_state['total_lidos'] = total_lidos
                
                if restos:
                    st.session_state['res_ia'] = classificar_ia(restos)
                else:
                    st.session_state['res_ia'] = {}
        
        limpar_temp(temp_path)

# ============================================================================
# 7. RESULTADOS
# ============================================================================
if 'res_dutos' in st.session_state:
    dutos = st.session_state['res_dutos']
    ia = st.session_state.get('res_ia', {})
    logs = st.session_state.get('res_logs', [])
    
    t1, t2, t3, t4, t5 = st.tabs(["🌪️ Dutos", "💨 Terminais", "⚙️ Equipamentos", "⚡ Elétrica", "🔍 Diagnóstico"])
    
    with t1:
        if dutos:
            df = pd.DataFrame(dutos)
            
            # Agrupa
            df_view = df.groupby(['Largura', 'Altura', 'Origem']).agg(
                Qtd=('Tag', 'count'),
                Comp_Total=('Comp. (m)', 'sum')
            ).reset_index()
            
            st.markdown(f"### 📋 Resultado ({len(dutos)} trechos identificados)")
            
            # Editor
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
            
        else:
            st.error("Nenhum duto encontrado!")
            st.info("Verifique a aba '🔍 Diagnóstico' para ver o que o robô leu no arquivo.")

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
        st.markdown("### Log de Leitura do Robô")
        st.write(f"Total de Textos Lidos: {st.session_state.get('total_lidos', 0)}")
        st.text_area("Log Bruto", "\n".join(logs), height=400)
