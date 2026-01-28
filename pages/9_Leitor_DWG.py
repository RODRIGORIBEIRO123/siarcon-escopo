import streamlit as st
import ezdxf
import math
from openai import OpenAI
import pandas as pd
import io
from collections import Counter
import time

# --- 🔒 BLOCO DE SEGURANÇA ---
if 'logado' not in st.session_state or not st.session_state['logado']:
    st.warning("🔒 Acesso negado. Faça login no Dashboard.")
    st.stop()

st.set_page_config(page_title="Leitor DXF (Geométrico)", page_icon="📐", layout="wide")

st.title("📐 Leitor Técnico DXF + Geometria (Heavy Duty)")
st.markdown("""
**Instrução para arquivos pesados (>10MB):** O sistema analisa textos e geometrias. Se o arquivo for muito grande, a análise será limitada aos primeiros 3.000 itens para evitar travamento.
""")

# ============================================================================
# 1. CONFIGURAÇÕES
# ============================================================================
with st.sidebar:
    st.header("⚙️ Configurações")
    classe_pressao = st.selectbox("Classe de Pressão", ["Classe A (Baixa)", "Classe B (Média)", "Classe C (Alta)", "Classe D (Especial)"])
    
    st.divider()
    st.subheader("📏 Calibração")
    unidade_desenho = st.selectbox("Unidade do Desenho", ["Centímetros (cm)", "Metros (m)", "Milímetros (mm)"])
    
    raio_padrao = 50.0 if unidade_desenho == "Centímetros (cm)" else (0.5 if unidade_desenho == "Metros (m)" else 500.0)
    raio_busca = st.number_input("Raio de Busca (Geometria)", value=raio_padrao, help="Distância para procurar linhas ao redor do texto.")
    comp_minimo = st.number_input("Comprimento Mínimo (m)", value=1.0)
    
    st.divider()
    perda_corte = st.number_input("% Perda / Corte", value=10.0)
    tipo_isolamento = st.selectbox("Isolamento", ["Lã de Vidro", "Borracha Elast.", "Isopor", "Sem Isolamento"])

# ============================================================================
# 2. MOTOR GEOMÉTRICO OTIMIZADO
# ============================================================================

def calcular_distancia(p1, p2):
    return math.hypot(p2[0] - p1[0], p2[1] - p1[1])

def obter_comprimento_entidade(entity):
    try:
        if entity.dxftype() == 'LINE':
            return calcular_distancia(entity.dxf.start, entity.dxf.end)
        elif entity.dxftype() == 'LWPOLYLINE':
            pts = entity.get_points()
            if entity.closed: # Se for retângulo, pega o maior lado
                max_seg = 0
                for i in range(len(pts) - 1):
                    s = calcular_distancia(pts[i], pts[i+1])
                    if s > max_seg: max_seg = s
                return max_seg
            else: # Soma segmentos
                comp = 0
                for i in range(len(pts) - 1): comp += calcular_distancia(pts[i], pts[i+1])
                return comp
    except: return 0
    return 0

def extrair_dados_com_geometria(bytes_file, raio_search):
    itens_encontrados = []
    log_erro = "Sucesso"
    
    try:
        # Tenta decodificar
        try: content = bytes_file.getvalue().decode("cp1252")
        except: 
            try: content = bytes_file.getvalue().decode("utf-8", errors='ignore')
            except: return [], "Erro Fatal de Codificação (Arquivo Binário?)"

        stream = io.StringIO(content)
        doc = ezdxf.read(stream)
        msp = doc.modelspace()
        
        # OTIMIZAÇÃO: Carrega geometria apenas se necessário e limita quantidade
        geometrias = []
        # Pega no máximo 5000 linhas para não estourar memória
        for i, e in enumerate(msp.query('LINE LWPOLYLINE')):
            if i > 5000: break 
            geometrias.append(e)
            
        if not geometrias:
            log_erro = "Aviso: Nenhuma linha/polilinha encontrada. Modo somente texto."

        # Barra de progresso para o usuário ver
        progresso = st.progress(0, text="Lendo textos...")
        
        textos = list(msp.query('TEXT MTEXT'))
        total_textos = len(textos)
        
        if total_textos == 0:
            return [], "Nenhum objeto de texto (TEXT/MTEXT) encontrado no DXF."

        # LIMITADOR DE SEGURANÇA
        limite_analise = 3000
        if total_textos > limite_analise:
            st.toast(f"⚠️ Arquivo gigante! Analisando apenas os primeiros {limite_analise} textos.", icon="⚠️")
            textos = textos[:limite_analise]

        for idx, e in enumerate(textos):
            # Atualiza barra a cada 100 itens
            if idx % 100 == 0: progresso.progress(int((idx / len(
