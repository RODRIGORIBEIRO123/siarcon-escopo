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

st.set_page_config(page_title="Leitor DXF (Padrão Planta)", page_icon="📐", layout="wide")

st.title("📐 Leitor Técnico DXF - Filtro Rígido")
st.markdown("""
Esta versão foi ajustada para ler etiquetas no formato **`1.300x700`** ou **`500x450`**, ignorando o "lixo" do arquivo.
""")

# ============================================================================
# 1. CONFIGURAÇÕES
# ============================================================================
with st.sidebar:
    st.header("⚙️ Parâmetros")
    
    st.info("ℹ️ Método: Contagem de Etiquetas x Comprimento Padrão.")
    comp_padrao = st.number_input("Comp. Padrão da Peça (m)", value=1.10, step=0.10, help="Comprimento médio estimado por etiqueta encontrada.")
    
    st.divider()
    classe_pressao = st.selectbox("Classe de Pressão", ["Classe A (Baixa)", "Classe B (Média)", "Classe C (Alta)"])
    perda_corte = st.number_input("% Perda / Corte", value=10.0)
    tipo_isolamento = st.selectbox("Isolamento", ["Lã de Vidro", "Borracha Elast.", "Isopor", "Sem Isolamento"])

# ============================================================================
# 2. MOTOR DE LEITURA (REGEX MATEMÁTICO)
# ============================================================================
def limpar_valor_dimensao(valor_str):
    """
    Converte strings como '1.300', '1300', '500' para float 1300.0, 500.0.
    Remove o ponto de milhar se existir.
    """
    try:
        # Remove espaços
        v = valor_str.strip()
        # Remove ponto de milhar comum em CAD BR (ex: 1.300 vira 1300)
        v_limpo = v.replace('.', '')
        return float(v_limpo)
    except:
        return 0.0

def extrair_dados_projeto(uploaded_file):
    dutos_encontrados = []
    outros_textos = [] # Para mandar pra IA (Equipamentos/Grelhas)
    
    temp_path = None
    try:
        # Salva arquivo temporário para leitura segura
        with tempfile.NamedTemporaryFile(delete=False, suffix=".dxf") as tmp_file:
            tmp_file.write(uploaded_file.getvalue())
            temp_path = tmp_file.name
            
        doc, auditor = recover.readfile(temp_path)
        msp = doc.modelspace()
        
        # Regex para capturar padrão LARGURAxALTURA
        # Aceita: 500x450, 1.300x700, 500 X 450
        regex_duto = re.compile(r'(\d{1,3}(?:\.\d{3})*|\d+)\s*[xX]\s*(\d{1,3}(?:\.\d{3})*|\d+)')
        
        # Regex para Diâmetro (ø200 ou 200ø)
        regex_circ = re.compile(r'[øØ](\d+)|(\d+)[øØ]')

        total_lidos = 0
        
        for e in msp.query('TEXT MTEXT'):
            txt = e.dxf.text if e.dxftype() == 'TEXT' else e.text
            if not txt: continue
            
            # Limpa formatação MTEXT
            txt_clean = re.sub(r'\\[ACFHQTW].*?;', '', txt).replace('{', '').replace('}', '').strip()
            if len(txt_clean) < 3 or len(txt_clean) > 50: continue # Ignora lixo muito curto ou muito longo
            
            total_lidos += 1
            
            # 1. Tenta identificar DUTO RETANGULAR (Prioridade)
            match_ret = regex_duto.search(txt_clean)
            if match_ret:
                largura = limpar_valor_dimensao(match_ret.group(1))
                altura = limpar_valor_dimensao(match_ret.group(2))
                
                # Filtro de sanidade: Dutos geralmente > 50mm
                if largura > 50 and altura > 50:
                    dutos_encontrados.append({
                        'Largura': largura, 
                        'Altura': altura, 
                        'Tipo': 'Retangular',
                        'Tag Original': txt_clean
                    })
                    continue # Já achou, vai pro próximo
            
            # 2. Tenta identificar DUTO CIRCULAR
            match_circ = regex_circ.search(txt_clean)
            if match_circ:
                val = match_circ.group(1) if match_circ.group(1) else match_circ.group(2)
                diam = limpar_valor_dimensao(val)
                if diam > 50:
                    dutos_encontrados.append({
                        'Largura': diam, 
                        'Altura': diam, 
                        'Tipo': 'Circular',
                        'Tag Original': txt_clean
                    })
                    continue

            # 3. Se não for duto, guarda para verificar Equipamentos (Se tiver letras)
            # Filtra coordenadas numéricas puras para não sujar (ex: "4.250")
            if any(c.isalpha() for c in txt_clean):
                if not re.match(r'^[\d\.\,\-\+]+$', txt_clean): # Ignora se for só numero e ponto
                    outros_textos.append(txt_clean)

    except Exception as e:
        return [], [], f"Erro: {str(e)}"
    finally:
        if temp_path and os.path.exists(temp_path):
            try: os.remove(temp_path)
            except: pass

    return dutos_encontrados, outros_textos, f"Varredura concluída em {total_lidos} textos."

# ============================================================================
# 3. IA APENAS PARA EQUIPAMENTOS (ECONOMIA E PRECISÃO)
# ============================================================================
def classificar_equipamentos_ia(lista_textos):
    if not lista_textos: return None
    if "openai" not in st.secrets: return None
    
    # Conta frequencia para reduzir tokens
    counts = Counter(lista_textos)
    # Pega top 200 textos que não são duto
    texto_prompt = "\n".join([f"'{k}' (Qtd: {v})" for k, v in counts.most_common(200)])
    
    client = OpenAI(api_key=st.secrets["openai"]["api_key"])
    prompt = """
    Analise esta lista de textos de um projeto HVAC.
    IGNORE coordenadas, nomes de sala, arquitetura.
    
    EXTRAIA APENAS:
    1. TERMINAIS: Grelhas (G-), Difusores, Venezianas.
    2. EQUIPAMENTOS: Fancoil (FC), Split, VRF. Tente achar capacidade (TR, BTU).
    3. ELETRICA: Quadros (Q-).
    
    FORMATO CSV (;):
    ---TERMINAIS---
    Item;Qtd
    Grelha Retorno 600x600;10
    
    ---EQUIPAMENTOS---
    Tag;Tipo;Detalhes;Qtd
    FC-01;Fancoil;5TR;2
    
    ---ELETRICA---
    Tag;Desc;Qtd
    """
    
    try:
        r = client.chat.completions.create(
            model="gpt-4o", messages=[{"role":"system","content":prompt},{"role":"user","content":texto_prompt}], temperature=0.1
        )
        return r.choices[0].message.content
    except: return None

def processar_resposta_ia(resposta):
    blocos = {"TERMINAIS": [], "EQUIPAMENTOS": [], "ELETRICA": []}
    atual = None
    if not resposta: return blocos
    for l in resposta.split('\n'):
        l = l.strip()
        if "---TERM" in l: atual = "TERMINAIS"; continue
        if "---EQUI" in l: atual = "EQUIPAMENTOS"; continue
        if "---ELET" in l: atual = "ELETRICA"; continue
        if atual and ";" in l and "Tag" not in l and "Item" not in l:
            blocos[atual].append(l.split(';'))
    return blocos

# ============================================================================
# 4. INTERFACE
# ============================================================================
uploaded_dxf = st.file_uploader("📂 Carregar DXF (Testado com seu arquivo)", type=["dxf"])

if uploaded_dxf:
    with st.spinner("Aplicando filtro 'Sniper' para achar 500x450, 1.300x700..."):
        dutos_raw, outros_txt, log = extrair_dados_projeto(uploaded_dxf)
    
    # Processa Dutos (Sem IA, Matemática Pura)
    df_dutos = pd.DataFrame()
    if dutos_raw:
        df_dutos = pd.DataFrame(dutos_raw)
        # Agrupa por bitola para contar
        df_dutos = df_dutos.groupby(['Largura', 'Altura', 'Tipo']).size().reset_index(name='Qtd Peças')
        st.success(f"✅ SUCESSO! {df_dutos['Qtd Peças'].sum()} etiquetas de dutos encontradas.")
    else:
        st.warning("⚠️ Nenhum duto no padrão 'LxA' encontrado. O arquivo pode estar explodido (linhas soltas em vez de texto).")

    # Botão para processar resto via IA
    dados_ia = {"TERMINAIS":[], "EQUIPAMENTOS":[], "ELETRICA":[]}
    if outros_txt:
        if st.button("🚀 Buscar Grelhas e Equipamentos (IA)", type="primary"):
            with st.spinner("Analisando itens especiais..."):
                res = classificar_equipamentos_ia(outros_txt)
                if res:
                    dados_ia = processar_resposta_ia(res)
                    st.session_state['dados_ia_cache'] = dados_ia
                    st.rerun()
    
    if 'dados_ia_cache' in st.session_state:
        dados_ia = st.session_state['dados_ia_cache']

    # ========================================================================
    # 5. VISUALIZAÇÃO (SEU LAYOUT ORIGINAL)
    # ========================================================================
    t1, t2, t3, t4 = st.tabs(["🌪️ Rede de Dutos", "💨 Terminais", "⚙️ Equipamentos", "⚡ Elétrica"])

    with t1:
        if not df_dutos.empty:
            # Coluna de Comprimento Padrão
            df_dutos["Comp. Padrão (m)"] = comp_padrao
            
            # Editor
            st.markdown("### 📋 Quantitativo de Dutos Detectados")
            df_edit = st.data_editor(
                df_dutos,
                key="editor_dutos_final",
                use_container_width=True,
                column_config={
                    "Largura": st.column_config.NumberColumn(format="%d mm"),
                    "Altura": st.column_config.NumberColumn(format="%d mm"),
                    "Qtd Peças": st.column_config.NumberColumn("Qtd (Tags)"),
                }
            )
            
            # Cálculos
            df_calc = df_edit.copy()
            
            # Perímetro
            def get_perim(row):
                if row['Tipo'] == 'Circular': return (math.pi * row['Largura'])/1000
                return (2*row['Largura'] + 2*row['Altura'])/1000
            
            df_calc['Perímetro (m)'] = df_calc.apply(get_perim, axis=1)
            df_calc['Comp. Total (m)'] = df_calc['Qtd Peças'] * df_calc['Comp. Padrão (m)']
            df_calc['Área (m²)'] = df_calc['Perímetro (m)'] * df_calc['Comp. Total (m)']
            
            # Totais
            fator = 1 + (perda_corte/100)
            area_tot = (df_calc['Área (m²)'] * fator).sum()
            peso_tot = area_tot * 5.6
            
            # KPIs
            st.divider()
            c1, c2, c3 = st.columns(3)
            c1.metric("Área Total (c/ Perda)", f"{area_tot:,.2f} m²")
            c2.metric("Peso Estimado", f"{peso_tot:,.0f} kg")
            iso_val = f"{area_tot:,.2f} m²" if tipo_isolamento != "Sem Isolamento" else "-"
            c3.metric("Isolamento", iso_val, delta=tipo_isolamento)
            
        else:
            st.info("Aguardando carregamento...")

    with t2:
        if dados_ia["TERMINAIS"]:
            st.data_editor(pd.DataFrame(dados_ia["TERMINAIS"], columns=["Item","Qtd"]), use_container_width=True)
        else: st.info("Nenhuma grelha identificada ainda.")

    with t3:
        if dados_ia["EQUIPAMENTOS"]:
            st.data_editor(pd.DataFrame(dados_ia["EQUIPAMENTOS"], columns=["Tag","Tipo","Detalhe","Qtd"]), use_container_width=True)
        else: st.info("Nenhum equipamento identificado ainda.")

    with t4:
        if dados_ia["ELETRICA"]:
            st.data_editor(pd.DataFrame(dados_ia["ELETRICA"], columns=["Tag","Desc","Qtd"]), use_container_width=True)
        else: st.info("Nenhum quadro identificado ainda.")
