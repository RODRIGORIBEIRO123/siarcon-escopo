import streamlit as st
import ezdxf
from ezdxf import recover
import math
import pandas as pd
import io
import re

# --- 🔒 SEGURANÇA ---
if 'logado' not in st.session_state or not st.session_state['logado']:
    st.warning("🔒 Acesso negado. Faça login no Dashboard.")
    st.stop()

st.set_page_config(page_title="Leitor DXF (Layers)", page_icon="📐", layout="wide")

st.title("📐 Leitor de Dutos por Camadas (Layers)")
st.markdown("""
**Esta é a forma mais precisa de medir.** Em vez de adivinhar, selecionaremos a Camada (Layer) onde estão os Dutos e a Camada onde estão os Textos.
O sistema somará o comprimento de todas as linhas e atribuirá à etiqueta mais próxima.
""")

# ============================================================================
# 1. FUNÇÕES GEOMÉTRICAS (Distância e Comprimento)
# ============================================================================
def calcular_distancia_pontos(p1, p2):
    return math.hypot(p2[0] - p1[0], p2[1] - p1[1])

def obter_comprimento_e_centro(entity):
    """Retorna (comprimento, ponto_central_x, ponto_central_y)"""
    try:
        if entity.dxftype() == 'LINE':
            start = entity.dxf.start
            end = entity.dxf.end
            comp = calcular_distancia_pontos(start, end)
            center = ((start[0] + end[0])/2, (start[1] + end[1])/2)
            return comp, center
        
        elif entity.dxftype() == 'LWPOLYLINE':
            pts = entity.get_points()
            comp_total = 0
            # Centro aproximado (média dos pontos)
            sum_x, sum_y = 0, 0
            count = len(pts)
            
            for i in range(len(pts) - 1):
                comp_total += calcular_distancia_pontos(pts[i], pts[i+1])
                sum_x += pts[i][0]
                sum_y += pts[i][1]
            
            # Fecha o poligono se necessário
            if entity.closed:
                comp_total += calcular_distancia_pontos(pts[-1], pts[0])
            
            center = (sum_x/count, sum_y/count)
            return comp_total, center
    except:
        return 0, (0,0)
    return 0, (0,0)

# ============================================================================
# 2. MOTOR DE LEITURA (COM SELEÇÃO DE LAYERS)
# ============================================================================
def ler_layers_do_arquivo(bytes_file):
    try:
        try: content_str = bytes_file.getvalue().decode("cp1252")
        except: content_str = bytes_file.getvalue().decode("utf-8", errors='ignore')
        stream = io.StringIO(content_str)
        doc, auditor = recover.read(stream)
        
        # Lista Layers únicos
        layers = sorted(list(set([layer.dxf.name for layer in doc.layers])))
        return layers, doc
    except Exception as e:
        st.error(f"Erro ao ler layers: {e}")
        return [], None

def processar_por_layers(doc, layer_dutos, layer_textos, raio_maximo, fator_linha):
    msp = doc.modelspace()
    
    # 1. Extrair TODAS as etiquetas do layer de texto selecionado
    etiquetas = [] # Lista de {'texto': '500x300', 'pos': (x,y), 'comprimento_acumulado': 0}
    
    query_texto = f'TEXT MTEXT[layer=="{layer_textos}"]'
    for e in msp.query(query_texto):
        txt = e.dxf.text if e.dxftype() == 'TEXT' else e.text
        if not txt: continue
        t_clean = txt.strip().upper()
        
        # Filtro básico: Deve ter números (ex: 500x300, ø200)
        if any(c.isdigit() for c in t_clean):
            try:
                insert = e.dxf.insert
                etiquetas.append({
                    'texto': t_clean,
                    'pos': (insert[0], insert[1]),
                    'soma_linhas': 0.0,
                    'qtd_linhas': 0
                })
            except: pass
            
    if not etiquetas:
        return [], "Nenhuma etiqueta encontrada no Layer selecionado."

    # 2. Extrair TODAS as linhas do layer de dutos
    # Se layer_dutos for igual layer_textos, pegamos tudo, senão filtramos
    query_linhas = f'LINE LWPOLYLINE[layer=="{layer_dutos}"]'
    linhas_processadas = 0
    
    # Otimização: Vamos iterar as linhas e encontrar a etiqueta mais próxima para CADA linha
    # Isso garante que toda linha seja contabilizada para alguém.
    
    for linha in msp.query(query_linhas):
        comp, centro_linha = obter_comprimento_e_centro(linha)
        if comp <= 0: continue
        
        # Encontra etiqueta mais próxima (Nearest Neighbor)
        etiqueta_mais_proxima = None
        menor_distancia = float('inf')
        
        # Busca rápida (poderia ser otimizado com KDTree, mas para <5000 itens loop é ok)
        for i, et in enumerate(etiquetas):
            # Check rápido de bounding box antes de calcular hipotenusa
            if abs(et['pos'][0] - centro_linha[0]) > raio_maximo: continue
            if abs(et['pos'][1] - centro_linha[1]) > raio_maximo: continue
            
            dist = calcular_distancia_pontos(et['pos'], centro_linha)
            if dist < menor_distancia:
                menor_distancia = dist
                etiqueta_mais_proxima = i
        
        # Se a linha estiver dentro do raio de atração da etiqueta, atribui a ela
        if etiqueta_mais_proxima is not None and menor_distancia <= raio_maximo:
            etiquetas[etiqueta_mais_proxima]['soma_linhas'] += comp
            etiquetas[etiqueta_mais_proxima]['qtd_linhas'] += 1
            linhas_processadas += 1
            
    # Consolida resultados (soma etiquetas iguais, ex: duas de 500x300)
    resumo = {}
    for item in etiquetas:
        t = item['texto']
        if item['soma_linhas'] > 0: # Só considera se achou linha perto
            if t not in resumo: resumo[t] = 0.0
            resumo[t] += item['soma_linhas']
            
    # Formata para lista final aplicando o fator (divisão por 2 se for parede dupla)
    resultado_final = []
    for k, v in resumo.items():
        # Aplica o fator de correção (ex: dividir por 2 se desenhou paredes)
        comp_ajustado = v / fator_linha
        resultado_final.append({'Bitola': k, 'Comprimento Total (m)': comp_ajustado})
        
    return resultado_final, f"Processadas {linhas_processadas} linhas de duto."

# ============================================================================
# 3. INTERFACE
# ============================================================================
with st.sidebar:
    st.header("⚙️ Calibração")
    
    unidade_desenho = st.selectbox("Unidade do CAD", ["Centímetros (cm)", "Metros (m)", "Milímetros (mm)"], index=0)
    
    # Configura Raio de Atração
    if unidade_desenho == "Centímetros (cm)": raio_def = 200.0 # 2 metros de raio
    elif unidade_desenho == "Metros (m)": raio_def = 2.0
    else: raio_def = 2000.0
    
    raio_atracao = st.number_input("Raio de Atração (Busca)", value=raio_def, help="Distância máxima que um texto pode 'puxar' uma linha para si.")
    
    st.divider()
    
    st.info("Desenho de Duto:")
    modo_desenho = st.radio("Como o duto foi desenhado?", ["Linha Dupla (Paredes)", "Linha Única (Eixo)"])
    fator_divisao = 2.0 if modo_desenho == "Linha Dupla (Paredes)" else 1.0
    
    st.divider()
    classe_pressao = st.selectbox("Classe Pressão", ["Classe A", "Classe B", "Classe C"])
    perda = st.number_input("% Perda", value=10.0)
    isolamento = st.selectbox("Isolamento", ["Lã de Vidro", "Borracha", "Isopor", "Nenhum"])

# --- UPLOAD ---
uploaded_dxf = st.file_uploader("📂 Carregar DXF (Qualquer versão)", type=["dxf"])

if uploaded_dxf:
    # 1. LÊ LAYERS
    layers_disponiveis, doc_carregado = ler_layers_do_arquivo(uploaded_dxf)
    
    if layers_disponiveis:
        st.success("Arquivo lido! Selecione as camadas abaixo para filtrar o 'ruído'.")
        
        c1, c2 = st.columns(2)
        
        # Tenta adivinhar layers comuns
        idx_duto = 0
        idx_texto = 0
        for i, l in enumerate(layers_disponiveis):
            if "DUTO" in l.upper() or "M-DUCT" in l.upper(): idx_duto = i
            if "TEXT" in l.upper() or "TAG" in l.upper() or "COT" in l.upper(): idx_texto = i
            
        layer_dutos = c1.selectbox("Selecione o Layer dos DUTOS (Linhas):", layers_disponiveis, index=idx_duto)
        layer_textos = c2.selectbox("Selecione o Layer dos TEXTOS (Etiquetas):", layers_disponiveis, index=idx_texto)
        
        if st.button("🚀 Calcular Comprimentos Reais", type="primary"):
            with st.spinner("Mapeando proximidade entre linhas e textos..."):
                
                # Conversão de unidade para Metros no final
                fator_unidade = 1.0
                if unidade_desenho == "Centímetros (cm)": fator_unidade = 0.01
                elif unidade_desenho == "Milímetros (mm)": fator_unidade = 0.001
                
                lista_res, log = processar_por_layers(doc_carregado, layer_dutos, layer_textos, raio_atracao, fator_divisao)
                
                if lista_res:
                    # Cria DataFrame
                    df = pd.DataFrame(lista_res)
                    
                    # Converte para Metros
                    df['Comprimento Total (m)'] = df['Comprimento Total (m)'] * fator_unidade
                    
                    # Tenta separar Largura e Altura com Regex
                    def extrair_dim(txt):
                        # Procura padrao 500x300
                        match = re.search(r'(\d+)\s*[xX]\s*(\d+)', txt)
                        if match:
                            return float(match.group(1)), float(match.group(2)), "Retangular"
                        # Procura diametro
                        match_d = re.search(r'[øØ](\d+)', txt)
                        if match_d:
                            return float(match_d.group(1)), float(match_d.group(1)), "Circular"
                        return 0, 0, "Outro"

                    # Aplica extração
                    df[['Largura', 'Altura', 'Tipo']] = df['Bitola'].apply(lambda x: pd.Series(extrair_dim(x)))
                    
                    # Filtra o que não é duto (Lixo que estava no layer de texto)
                    df_dutos = df[df['Largura'] > 0].copy()
                    
                    if not df_dutos.empty:
                        st.divider()
                        
                        # CÁLCULOS FINAIS
                        df_dutos['Perímetro (m)'] = (2*df_dutos['Largura'] + 2*df_dutos['Altura']) / 1000
                        # Se for circular, perimetro = pi * D
                        mask_circ = df_dutos['Tipo'] == 'Circular'
                        df_dutos.loc[mask_circ, 'Perímetro (m)'] = (math.pi * df_dutos.loc[mask_circ, 'Largura']) / 1000
                        
                        df_dutos['Área (m²)'] = df_dutos['Perímetro (m)'] * df_dutos['Comprimento Total (m)']
                        
                        # Totais
                        fator_perda = 1 + (perda/100)
                        area_total = (df_dutos['Área (m²)'] * fator_perda).sum()
                        peso_total = area_total * 5.6 # kg/m2 medio
                        
                        # --- EXIBIÇÃO ---
                        c_kpi1, c_kpi2, c_kpi3 = st.columns(3)
                        c_kpi1.metric("Área de Chapa (c/ Perda)", f"{area_total:,.2f} m²")
                        c_kpi2.metric("Peso Estimado", f"{peso_total:,.0f} kg")
                        c_kpi3.metric("Isolamento", f"{area_total:,.2f} m²" if isolamento != "Nenhum" else "-")
                        
                        st.subheader("Detalhamento por Bitola")
                        st.dataframe(
                            df_dutos[['Bitola', 'Tipo', 'Comprimento Total (m)', 'Área (m²)']]
                            .sort_values(by='Área (m²)', ascending=False)
                            .style.format({'Comprimento Total (m)': '{:.2f}', 'Área (m²)': '{:.2f}'})
                        )
                        
                        st.caption(f"Log: {log}")
                    else:
                        st.warning("Linhas foram medidas, mas nenhum texto parecia ser uma bitola (ex: 500x300). Verifique se selecionou o layer de texto correto.")
                        st.write("Textos encontrados:", df['Bitola'].unique())
                else:
                    st.error("Não foi possível conectar linhas aos textos. Tente aumentar o 'Raio de Atração' no menu lateral.")

    else:
        st.error("Não foi possível ler os layers deste arquivo.")
