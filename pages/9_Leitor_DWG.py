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

st.set_page_config(page_title="Leitor DXF (Geometria + IA)", page_icon="📐", layout="wide")

st.title("📐 Leitor Técnico DXF - Wall Matcher V2.1")
st.markdown("""
**Correção Total:** 1. Leitura de Layers blindada (sem erro de leitura).
2. Conexão com IA corrigida (sem erro de api_key).
3. Medição Geométrica por Largura (Pega a largura do texto e acha as paredes).
""")

# ============================================================================
# 1. CONFIGURAÇÕES
# ============================================================================
with st.sidebar:
    st.header("⚙️ Configurações")
    
    unidade_desenho = st.selectbox(
        "Unidade do CAD:", 
        ["Milímetros (1u=1mm)", "Centímetros (1u=1cm)", "Metros (1u=1m)"],
        index=0,
        help="Se o duto 500x300 mede 500 unidades no CAD, selecione Milímetros."
    )
    
    # Ajuste automático do raio de busca
    raio_val = 1500.0
    if unidade_desenho == "Centímetros (1u=1cm)": raio_val = 150.0
    elif unidade_desenho == "Metros (1u=1m)": raio_val = 1.5
    
    raio_busca = st.number_input("Raio de Busca (Geometria)", value=raio_val)
    comp_padrao = st.number_input("Comp. Padrão (Estimativa)", value=1.10, help="Usado se a geometria falhar.")
    
    st.divider()
    classe_pressao = st.selectbox("Classe de Pressão", ["Classe A (Baixa)", "Classe B (Média)", "Classe C (Alta)"])
    perda_corte = st.number_input("% Perda / Corte", value=10.0)
    tipo_isolamento = st.selectbox("Isolamento", ["Lã de Vidro", "Borracha Elast.", "Isopor", "Sem Isolamento"])

# ============================================================================
# 2. FUNÇÕES AUXILIARES (CARREGAMENTO SEGURO - CORREÇÃO ERRO A)
# ============================================================================
def carregar_dxf_seguro(uploaded_file):
    """
    Salva o arquivo em disco temporariamente. 
    Isso CORRIGE o erro de leitura de layers e 'rstrip'.
    """
    temp_path = None
    try:
        # Cria arquivo temporário no disco
        with tempfile.NamedTemporaryFile(delete=False, suffix=".dxf") as tmp_file:
            tmp_file.write(uploaded_file.getvalue())
            temp_path = tmp_file.name
        
        # O recover do ezdxf é robusto contra erros binários
        doc, auditor = recover.readfile(temp_path)
        return doc, temp_path, None
    except Exception as e:
        return None, temp_path, str(e)

def limpar_temp(path):
    if path and os.path.exists(path):
        try: os.remove(path)
        except: pass

# ============================================================================
# 3. LÓGICA DE GEOMETRIA (WALL MATCHER)
# ============================================================================
def get_line_len(entity):
    try:
        if entity.dxftype() == 'LINE':
            return math.hypot(entity.dxf.end.x - entity.dxf.start.x, entity.dxf.end.y - entity.dxf.start.y)
        elif entity.dxftype() == 'LWPOLYLINE':
            pts = entity.get_points()
            length = 0
            for i in range(len(pts)-1):
                length += math.hypot(pts[i+1][0]-pts[i][0], pts[i+1][1]-pts[i][1])
            return length
    except: return 0
    return 0

def medir_geometria_duto(msp, texto_obj, largura_alvo, altura_alvo, layers_validos, unid_fator, raio_max):
    # Converte targets para unidade do CAD
    w_cad = largura_alvo * unid_fator
    
    ins = texto_obj.dxf.insert
    tx, ty = ins.x, ins.y
    
    melhor_comp = 0.0
    status = "Estimado (Tag)" 

    candidatos = []
    
    # Pega linhas próximas (Otimizado)
    entidades = msp.query('LINE LWPOLYLINE')
    
    for e in entidades:
        # Filtro de Layer (Fundamental para não pegar lixo)
        if layers_validos and e.dxf.layer not in layers_validos: continue
        
        # Filtro de Bounding Box (Performance)
        try:
            if e.dxftype() == 'LINE':
                px, py = e.dxf.start.x, e.dxf.start.y
            else:
                pts = e.get_points()
                px, py = pts[0][0], pts[0][1]
            
            if abs(px - tx) > raio_max or abs(py - ty) > raio_max: continue
            
            comp = get_line_len(e)
            if comp > 0: candidatos.append({'obj': e, 'comp': comp})
        except: pass

    # Se achou linhas candidatas
    if candidatos:
        # Pega a maior linha próxima. 
        # Assumimos que a linha mais longa perto do texto 500x300 é a parede do duto.
        candidatos.sort(key=lambda x: x['comp'], reverse=True)
        top = candidatos[0]
        
        # Validação simples: Comprimento > Metade da Largura
        if top['comp'] > (w_cad * 0.5):
            melhor_comp = top['comp']
            status = "Geometria (Medido)"

    return melhor_comp, status

# ============================================================================
# 4. PROCESSAMENTO PRINCIPAL
# ============================================================================
def processar_dxf(doc, layers_duto, unid_cad_str, raio_busca):
    msp = doc.modelspace()
    
    # Fatores de conversão
    if unid_cad_str == "Metros (1u=1m)":
        fator_txt_to_cad = 0.001 
        fator_cad_to_m = 1.0
    elif unid_cad_str == "Centímetros (1u=1cm)":
        fator_txt_to_cad = 0.1
        fator_cad_to_m = 0.01
    else: # Milimetros
        fator_txt_to_cad = 1.0
        fator_cad_to_m = 0.001

    dutos = []
    outros_textos = []
    
    # Regex 500x300
    regex_dim = re.compile(r'(\d{1,4})\s*[xX*]\s*(\d{1,4})') 
    
    for e in msp.query('TEXT MTEXT'):
        txt = e.dxf.text if e.dxftype() == 'TEXT' else e.text
        if not txt: continue
        
        # Limpa formatação
        t_clean = re.sub(r'\\[ACFHQTW].*?;', '', txt).replace('{', '').replace('}', '').strip().upper()
        if len(t_clean) < 3 or len(t_clean) > 40: continue
        
        match = regex_dim.search(t_clean)
        if match:
            try:
                l_mm = float(match.group(1))
                a_mm = float(match.group(2))
                
                if l_mm > 50 and a_mm > 50:
                    # TENTA MEDIR
                    comp_cad, status = medir_geometria_duto(
                        msp, e, l_mm, a_mm, layers_duto, fator_txt_to_cad, raio_busca
                    )
                    
                    comp_final_m = 0
                    if status == "Geometria (Medido)":
                        comp_final_m = comp_cad * fator_cad_to_m
                    else:
                        comp_final_m = comp_padrao # Fallback se falhar
                        
                    dutos.append({
                        "Largura": l_mm,
                        "Altura": a_mm,
                        "Comp. (m)": comp_final_m,
                        "Origem": status,
                        "Tag": t_clean
                    })
                    continue
            except: pass
            
        if any(c.isalpha() for c in t_clean):
            outros_textos.append(t_clean)
            
    return dutos, outros_textos

# ============================================================================
# 5. IA (CORREÇÃO ERRO B)
# ============================================================================
def classificar_ia(lista_textos):
    if not lista_textos: return None
    
    # CORREÇÃO: Verifica secrets antes de usar
    if "openai" not in st.secrets:
        st.warning("⚠️ Chave OpenAI não configurada.")
        return None
    
    # CORREÇÃO: Usa a chave do secrets explicitamente
    client = OpenAI(api_key=st.secrets["openai"]["api_key"])
    
    counts = Counter(lista_textos)
    prompt_txt = "\n".join([f"{k} (x{v})" for k,v in counts.most_common(300)])
    
    sys_prompt = """
    Analise textos de HVAC. Ignore arquitetura.
    EXTRAIA:
    1. TERMINAIS: Grelhas, Difusores.
    2. EQUIPAMENTOS: Fancoil, Split, TR, BTU.
    3. ELETRICA: Quadros.
    
    SAÍDA CSV (;):
    ---TERMINAIS---
    Item;Qtd
    Grelha 600x600;10
    
    ---EQUIPAMENTOS---
    Tag;Tipo;Detalhe;Qtd
    FC-01;Fancoil;5TR;2
    
    ---ELETRICA---
    Tag;Desc;Qtd
    """
    
    try:
        r = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role":"system","content":sys_prompt}, {"role":"user","content":prompt_txt}],
            temperature=0.0
        )
        return r.choices[0].message.content
    except Exception as e:
        st.error(f"Erro na IA: {e}")
        return None

def parse_ia(res):
    blocos = {"TERMINAIS":[], "EQUIPAMENTOS":[], "ELETRICA":[]}
    curr = None
    if not res: return blocos
    for l in res.split('\n'):
        if "---TERM" in l: curr="TERMINAIS"; continue
        if "---EQUI" in l: curr="EQUIPAMENTOS"; continue
        if "---ELET" in l: curr="ELETRICA"; continue
        if curr and ";" in l and "Tag" not in l: blocos[curr].append(l.split(';'))
    return blocos

# ============================================================================
# 6. INTERFACE
# ============================================================================
uploaded_dxf = st.file_uploader("📂 Carregar DXF", type=["dxf"])

if uploaded_dxf:
    # Chama função SEGURA (TempFile)
    with st.spinner("Lendo estrutura..."):
        doc, temp_path, erro = carregar_dxf_seguro(uploaded_dxf)
    
    if erro:
        st.error(f"Erro ao ler arquivo: {erro}")
        limpar_temp(temp_path)
    else:
        # Se leu ok, mostra seleção de layers
        layers = sorted([l.dxf.name for l in doc.layers])
        default_idx = [i for i, s in enumerate(layers) if 'DUTO' in s.upper() or 'DUCT' in s.upper()]
        
        sel_layers = st.multiselect(
            "Selecione o(s) Layer(s) das LINHAS de Duto:", 
            layers, 
            default=[layers[default_idx[0]]] if default_idx else None
        )
        
        if st.button("🚀 Processar", type="primary"):
            with st.spinner("Analisando..."):
                dutos, restos = processar_dxf(doc, sel_layers, unidade_desenho, raio_busca)
                
                st.session_state['dutos_res'] = dutos
                if restos:
                    ia_txt = classificar_ia(restos)
                    st.session_state['ia_res'] = parse_ia(ia_txt)
                else:
                    st.session_state['ia_res'] = {"TERMINAIS":[], "EQUIPAMENTOS":[], "ELETRICA":[]}
        
        limpar_temp(temp_path)

# ============================================================================
# 7. EXIBIÇÃO
# ============================================================================
if 'dutos_res' in st.session_state:
    dutos = st.session_state['dutos_res']
    ia_data = st.session_state.get('ia_res', {})
    
    t1, t2, t3, t4 = st.tabs(["🌪️ Dutos", "💨 Terminais", "⚙️ Equipamentos", "⚡ Elétrica"])
    
    with t1:
        if dutos:
            df = pd.DataFrame(dutos)
            
            # Agrupa
            df_view = df.groupby(['Largura', 'Altura', 'Origem']).agg(
                Qtd=('Tag', 'count'),
                Comp_Total=('Comp. (m)', 'sum')
            ).reset_index()
            
            st.markdown("### 📋 Levantamento de Dutos")
            df_ed = st.data_editor(
                df_view, 
                use_container_width=True,
                column_config={
                    "Largura": st.column_config.NumberColumn(format="%d mm"),
                    "Altura": st.column_config.NumberColumn(format="%d mm"),
                    "Comp_Total": st.column_config.NumberColumn("Comp. Total (m)", format="%.2f")
                }
            )
            
            # Cálculos
            df_ed['Perímetro'] = (2*df_ed['Largura'] + 2*df_ed['Altura'])/1000
            df_ed['Área (m²)'] = df_ed['Perímetro'] * df_ed['Comp_Total'] * (1 + perda_corte/100)
            
            area = df_ed['Área (m²)'].sum()
            peso = area * 5.6
            
            st.divider()
            c1, c2, c3 = st.columns(3)
            c1.metric("Área Total", f"{area:,.2f} m²")
            c2.metric("Peso Total", f"{peso:,.0f} kg")
            c3.metric("Isolamento", f"{area:,.2f} m²" if tipo_isolamento != "Sem Isolamento" else "-")
            
        else:
            st.warning("Nenhum duto 'LxA' encontrado.")

    with t2:
        if ia_data.get("TERMINAIS"): st.data_editor(pd.DataFrame(ia_data["TERMINAIS"], columns=["Item","Qtd"]), use_container_width=True)
        else: st.info("Vazio")
        
    with t3:
        if ia_data.get("EQUIPAMENTOS"): st.data_editor(pd.DataFrame(ia_data["EQUIPAMENTOS"], columns=["Tag","Tipo","Detalhe","Qtd"]), use_container_width=True)
        else: st.info("Vazio")
        
    with t4:
        if ia_data.get("ELETRICA"): st.data_editor(pd.DataFrame(ia_data["ELETRICA"], columns=["Tag","Desc","Qtd"]), use_container_width=True)
        else: st.info("Vazio")
