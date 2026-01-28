import streamlit as st
import ezdxf
from ezdxf import recover
import math
import pandas as pd
import tempfile
import os
import re

# --- 🔒 SEGURANÇA ---
if 'logado' not in st.session_state or not st.session_state['logado']:
    st.warning("🔒 Acesso negado. Faça login no Dashboard.")
    st.stop()

st.set_page_config(page_title="Leitor DXF (Cores)", page_icon="🎨", layout="wide")

st.title("🎨 Leitor de Dutos por COR (Visual)")
st.markdown("""
**Solução para Layers Bagunçados:**
Muitos projetos não organizam layers corretamente, mas usam **CORES** diferentes para Dutos e Arquitetura.
Selecione abaixo a cor das linhas dos dutos para fazer o levantamento preciso.
""")

# ============================================================================
# 1. FUNÇÕES AUXILIARES (GEOMETRIA E COR)
# ============================================================================

def calcular_distancia_pontos(p1, p2):
    return math.hypot(p2[0] - p1[0], p2[1] - p1[1])

def obter_comprimento_e_centro(entity):
    """Retorna (comprimento, ponto_central)"""
    try:
        if entity.dxftype() == 'LINE':
            start = entity.dxf.start
            end = entity.dxf.end
            comp = calcular_distancia_pontos(start, end)
            center = ((start[0] + end[0])/2, (start[1] + end[1])/2)
            return comp, center
        elif entity.dxftype() == 'LWPOLYLINE':
            pts = entity.get_points()
            if not pts: return 0, (0,0)
            comp_total = 0
            sum_x, sum_y = 0, 0
            count = len(pts)
            for i in range(len(pts) - 1):
                comp_total += calcular_distancia_pontos(pts[i], pts[i+1])
                sum_x += pts[i][0]; sum_y += pts[i][1]
            if entity.closed and count > 1:
                comp_total += calcular_distancia_pontos(pts[-1], pts[0])
            
            center = (sum_x/count, sum_y/count) if count > 0 else (0,0)
            return comp_total, center
    except: return 0, (0,0)
    return 0, (0,0)

def resolver_cor(entity, doc):
    """
    Retorna o número da cor (ACI).
    Se for 256 (ByLayer), busca a cor do layer.
    """
    try:
        c = entity.dxf.color
        if c == 256: # ByLayer
            layer_name = entity.dxf.layer
            layer = doc.layers.get(layer_name)
            return layer.dxf.color
        return c
    except:
        return 7 # Retorna branco/preto por padrão se falhar

# ============================================================================
# 2. PROCESSAMENTO (ARQUIVO SEGURO)
# ============================================================================
def ler_dxf_e_mapear_cores(uploaded_file):
    """Lê o arquivo e inventaria quais cores existem nele."""
    temp_path = None
    doc = None
    cores_linhas = {} # {cor_idx: quantidade}
    cores_textos = {}
    erro = None

    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".dxf") as tmp_file:
            tmp_file.write(uploaded_file.getvalue())
            temp_path = tmp_file.name
        
        doc, auditor = recover.readfile(temp_path)
        msp = doc.modelspace()

        # Inventário de Cores (Linhas)
        for e in msp.query('LINE LWPOLYLINE'):
            c = resolver_cor(e, doc)
            cores_linhas[c] = cores_linhas.get(c, 0) + 1

        # Inventário de Cores (Textos)
        for e in msp.query('TEXT MTEXT'):
            c = resolver_cor(e, doc)
            cores_textos[c] = cores_textos.get(c, 0) + 1
            
    except Exception as e:
        erro = str(e)
    finally:
        if temp_path and os.path.exists(temp_path):
            try: os.remove(temp_path)
            except: pass
            
    return doc, cores_linhas, cores_textos, erro

def processar_por_cor(doc, cor_dutos_selecionada, cor_textos_selecionada, raio_maximo, fator_linha, usar_todas_cores_dutos=False):
    msp = doc.modelspace()
    
    # 1. Extrair ETIQUETAS (Filtrando por cor se necessário)
    etiquetas = []
    
    # query genérica, filtro manual depois
    for e in msp.query('TEXT MTEXT'):
        # Filtro de Cor do Texto
        if cor_textos_selecionada != "Todas":
            c = resolver_cor(e, doc)
            if str(c) != str(cor_textos_selecionada): continue
            
        txt = e.dxf.text if e.dxftype() == 'TEXT' else e.text
        if not txt: continue
        t_clean = txt.strip().upper()
        
        # Validação Regex (Deve ter números)
        if any(char.isdigit() for char in t_clean):
            try:
                insert = e.dxf.insert
                etiquetas.append({
                    'texto': t_clean,
                    'pos': (insert[0], insert[1]),
                    'soma_linhas': 0.0
                })
            except: pass
            
    if not etiquetas:
        return [], "Nenhum texto válido encontrado com a cor selecionada."

    # 2. Extrair LINHAS (Filtrando por cor)
    linhas_processadas = 0
    linhas_ignoradas = 0
    
    # Otimização: Carregar apenas linhas relevantes
    for linha in msp.query('LINE LWPOLYLINE'):
        # Filtro de Cor da Linha
        if not usar_todas_cores_dutos:
            c = resolver_cor(linha, doc)
            if str(c) != str(cor_dutos_selecionada):
                linhas_ignoradas += 1
                continue
        
        comp, centro = obter_comprimento_e_centro(linha)
        if comp <= 0: continue
        
        # 3. Associação Geométrica (Nearest Neighbor)
        idx_mais_prox = -1
        menor_dist = float('inf')
        
        # Busca a etiqueta mais próxima dessa linha
        for i, et in enumerate(etiquetas):
            # Check rápido de Bounding Box
            if abs(et['pos'][0] - centro[0]) > raio_maximo: continue
            if abs(et['pos'][1] - centro[1]) > raio_maximo: continue
            
            dist = math.hypot(et['pos'][0] - centro[0], et['pos'][1] - centro[1])
            if dist < menor_dist:
                menor_dist = dist
                idx_mais_prox = i
        
        # Se achou uma etiqueta perto o suficiente, soma
        if idx_mais_prox != -1 and menor_dist <= raio_maximo:
            etiquetas[idx_mais_prox]['soma_linhas'] += comp
            linhas_processadas += 1
        else:
            linhas_ignoradas += 1

    # 4. Consolidar Resultados
    resumo = {}
    for item in etiquetas:
        if item['soma_linhas'] > 0:
            t = item['texto']
            if t not in resumo: resumo[t] = 0.0
            resumo[t] += item['soma_linhas']
            
    resultado_final = []
    for k, v in resumo.items():
        comp_ajustado = v / fator_linha
        resultado_final.append({'Bitola': k, 'Comprimento Total (m)': comp_ajustado})
        
    log = f"Processadas: {linhas_processadas} | Ignoradas (Cor/Longe): {linhas_ignoradas}"
    return resultado_final, log

# ============================================================================
# 3. INTERFACE
# ============================================================================
with st.sidebar:
    st.header("⚙️ Calibração")
    unidade_desenho = st.selectbox("Unidade do CAD", ["Centímetros (cm)", "Metros (m)", "Milímetros (mm)"])
    
    if unidade_desenho == "Centímetros (cm)": raio_def = 150.0
    elif unidade_desenho == "Metros (m)": raio_def = 1.5
    else: raio_def = 1500.0
    
    raio_atracao = st.number_input("Raio de Busca", value=raio_def, help="Distância máx entre Texto e Linha.")
    
    st.divider()
    st.info("Desenho dos Dutos:")
    modo_desenho = st.radio("Estilo:", ["Linha Dupla (Paredes)", "Linha Única (Eixo)"])
    fator_divisao = 2.0 if modo_desenho == "Linha Dupla (Paredes)" else 1.0
    
    st.divider()
    perda = st.number_input("% Perda Material", value=10.0)
    isolamento = st.selectbox("Isolamento", ["Lã de Vidro", "Borracha", "Isopor", "Nenhum"])

# --- UPLOAD ---
uploaded_dxf = st.file_uploader("📂 Carregar DXF (Qualquer versão)", type=["dxf"])

if uploaded_dxf:
    with st.spinner("Analisando cores do arquivo..."):
        doc_carregado, cores_lin, cores_txt, erro = ler_dxf_e_mapear_cores(uploaded_dxf)
    
    if erro:
        st.error(f"Erro ao ler arquivo: {erro}")
    else:
        st.success("Arquivo analisado! Selecione as Cores.")
        
        # Mapeamento de Cores AutoCAD para Nomes (Facilita a vida)
        def nome_cor(idx):
            mapa = {1:'Vermelho', 2:'Amarelo', 3:'Verde', 4:'Ciano', 5:'Azul', 6:'Magenta', 7:'Branco/Preto', 8:'Cinza', 256:'ByLayer'}
            return f"Cor {idx} ({mapa.get(idx, 'Outra')})"

        col1, col2 = st.columns(2)
        
        # Seleção Cor DUTOS
        opcoes_linhas = [(k, f"{nome_cor(k)} - {v} linhas encontradas") for k,v in cores_lin.items()]
        # Ordena por quantidade de linhas (provavelmente a cor com mais linhas é a arquitetura ou o duto)
        opcoes_linhas.sort(key=lambda x: x[1], reverse=True)
        
        with col1:
            st.markdown("### 🌪️ Dutos (Linhas)")
            usar_todas = st.checkbox("Usar TODAS as cores (Não recomendado)", value=False)
            cor_duto_sel = None
            if not usar_todas:
                sel_l = st.selectbox("Selecione a COR dos Dutos:", opcoes_linhas, format_func=lambda x: x[1])
                cor_duto_sel = sel_l[0] if sel_l else None
        
        # Seleção Cor TEXTOS
        opcoes_textos = [(k, f"{nome_cor(k)} - {v} textos encontrados") for k,v in cores_txt.items()]
        opcoes_textos.sort(key=lambda x: x[1], reverse=True)
        
        with col2:
            st.markdown("### 📝 Textos (Etiquetas)")
            usar_todos_txt = st.checkbox("Ler TODOS os textos", value=True)
            cor_txt_sel = "Todas"
            if not usar_todos_txt:
                sel_t = st.selectbox("Selecione a COR dos Textos:", opcoes_textos, format_func=lambda x: x[1])
                cor_txt_sel = sel_t[0] if sel_t else 7

        st.divider()
        
        if st.button("🚀 Calcular Comprimentos", type="primary"):
            if not usar_todas and cor_duto_sel is None:
                st.error("Selecione uma cor para os dutos.")
            else:
                with st.spinner("Realizando varredura geométrica..."):
                    # Fator Metro
                    fator_m = 0.01 if unidade_desenho == "Centímetros (cm)" else (0.001 if "Milímetros" in unidade_desenho else 1.0)
                    
                    lista_res, log = processar_por_cor(doc_carregado, cor_duto_sel, cor_txt_sel, raio_atracao, fator_divisao, usar_todas)
                    
                    if lista_res:
                        df = pd.DataFrame(lista_res)
                        
                        # Converte para Metros
                        df['Comprimento Total (m)'] = df['Comprimento Total (m)'] * fator_m
                        
                        # Extração de Medidas
                        def extrair(t):
                            match_r = re.search(r'(\d+)\s*[xX]\s*(\d+)', t)
                            if match_r: return float(match_r.group(1)), float(match_r.group(2)), "Retangular"
                            match_c = re.search(r'[øØ](\d+)|(\d+)[øØ]|DIAM\s*(\d+)', t.upper())
                            if match_c:
                                val = next((g for g in match_c.groups() if g), 0)
                                return float(val), float(val), "Circular"
                            return 0,0,"Outro"
                        
                        df[['Largura', 'Altura', 'Tipo']] = df['Bitola'].apply(lambda x: pd.Series(extrair(x)))
                        df_final = df[df['Largura'] > 0].copy()
                        
                        if not df_final.empty:
                            # CORREÇÃO DO ERRO DE DATAFRAME AQUI
                            # Garante que é número
                            df_final['Largura'] = pd.to_numeric(df_final['Largura'], errors='coerce').fillna(0)
                            df_final['Altura'] = pd.to_numeric(df_final['Altura'], errors='coerce').fillna(0)
                            df_final['Comprimento Total (m)'] = pd.to_numeric(df_final['Comprimento Total (m)'], errors='coerce').fillna(0)
                            
                            # Cálculos
                            df_final['Perímetro (m)'] = (2*df_final['Largura'] + 2*df_final['Altura']) / 1000
                            mask_circ = df_final['Tipo'] == 'Circular'
                            df_final.loc[mask_circ, 'Perímetro (m)'] = (math.pi * df_final.loc[mask_circ, 'Largura']) / 1000
                            
                            df_final['Área (m²)'] = df_final['Perímetro (m)'] * df_final['Comprimento Total (m)']
                            
                            # Totais
                            area_tot = (df_final['Área (m²)'] * (1 + perda/100)).sum()
                            peso_tot = area_tot * 5.6
                            
                            c1, c2, c3 = st.columns(3)
                            c1.metric("Área Total", f"{area_tot:,.2f} m²")
                            c2.metric("Peso", f"{peso_tot:,.0f} kg")
                            c3.metric("Isolamento", f"{area_tot:,.2f} m²" if isolamento != "Nenhum" else "-")
                            
                            st.subheader("📋 Detalhamento")
                            # Formatação Segura
                            try:
                                st.dataframe(
                                    df_final[['Bitola', 'Tipo', 'Comprimento Total (m)', 'Área (m²)']]
                                    .sort_values('Área (m²)', ascending=False)
                                    .style.format("{:.2f}")
                                )
                            except Exception as e:
                                st.dataframe(df_final) # Fallback sem estilo
                                
                            st.caption(f"Log Técnico: {log}")
                        else:
                            st.warning("Linhas medidas, mas sem associação com textos de bitola (ex: 500x300).")
                            st.write("Textos Lidos:", df['Bitola'].unique())
                    else:
                        st.error("Nenhuma linha foi associada a textos. Tente aumentar o Raio de Busca ou mudar a Cor selecionada.")
