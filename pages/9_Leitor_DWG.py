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

st.set_page_config(page_title="Leitor DXF (Layers)", page_icon="📐", layout="wide")

st.title("📐 Leitor de Dutos por Camadas (V2 - TempFile)")
st.markdown("""
**Modo de Alta Precisão:**
Esta ferramenta salva seu arquivo temporariamente para garantir a leitura correta das camadas (Layers), mesmo em arquivos pesados ou binários.
""")

# ============================================================================
# 1. FUNÇÕES GEOMÉTRICAS
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
            sum_x, sum_y = 0, 0
            count = len(pts)
            
            # Soma segmentos
            for i in range(len(pts) - 1):
                comp_total += calcular_distancia_pontos(pts[i], pts[i+1])
                sum_x += pts[i][0]
                sum_y += pts[i][1]
            
            # Fecha polígono se necessário
            if entity.closed and count > 1:
                comp_total += calcular_distancia_pontos(pts[-1], pts[0])
            
            # Evita divisão por zero
            if count > 0:
                center = (sum_x/count, sum_y/count)
            else:
                center = (0,0)
                
            return comp_total, center
    except:
        return 0, (0,0)
    return 0, (0,0)

# ============================================================================
# 2. MOTOR DE LEITURA (VIA ARQUIVO TEMPORÁRIO)
# ============================================================================
def ler_dxf_seguro(uploaded_file):
    """
    Salva o arquivo em disco temporariamente para o ezdxf ler com segurança.
    Isso evita erros de 'rstrip' e codificação de bytes.
    """
    temp_path = None
    doc = None
    layers = []
    erro = None

    try:
        # 1. Cria arquivo temporário
        with tempfile.NamedTemporaryFile(delete=False, suffix=".dxf") as tmp_file:
            tmp_file.write(uploaded_file.getvalue())
            temp_path = tmp_file.name
        
        # 2. Usa o recover.readfile (Mais robusto que read stream)
        # Ele detecta automaticamente se é binário ou texto
        doc, auditor = recover.readfile(temp_path)
        
        if auditor.has_errors:
            # Opcional: logar erros, mas geralmente ele recupera o que dá
            pass

        # 3. Extrai Layers
        layers = sorted(list(set([layer.dxf.name for layer in doc.layers])))
        
    except Exception as e:
        erro = str(e)
    finally:
        # 4. Limpeza: Remove o arquivo temporário
        if temp_path and os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except:
                pass # Se falhar apagar agora, o sistema operacional limpa depois
                
    return layers, doc, erro

def processar_por_layers(doc, layer_dutos, layer_textos, raio_maximo, fator_linha):
    msp = doc.modelspace()
    
    # 1. Extrair ETIQUETAS
    etiquetas = []
    
    # query protegida
    try:
        query_texto = f'TEXT MTEXT[layer=="{layer_textos}"]'
        entidades_texto = msp.query(query_texto)
    except:
        return [], "Erro ao filtrar layer de texto. Verifique se o nome contém caracteres especiais."

    for e in entidades_texto:
        txt = e.dxf.text if e.dxftype() == 'TEXT' else e.text
        if not txt: continue
        t_clean = txt.strip().upper()
        
        # Filtro: Deve ter números (ex: 500x300, 200)
        if any(c.isdigit() for c in t_clean):
            try:
                insert = e.dxf.insert
                # Garante que insert tenha x,y (alguns têm z)
                etiquetas.append({
                    'texto': t_clean,
                    'pos': (insert[0], insert[1]),
                    'soma_linhas': 0.0,
                    'qtd_linhas': 0
                })
            except: pass
            
    if not etiquetas:
        return [], "Nenhuma etiqueta com números encontrada no Layer selecionado."

    # 2. Extrair LINHAS
    try:
        query_linhas = f'LINE LWPOLYLINE[layer=="{layer_dutos}"]'
        entidades_linhas = msp.query(query_linhas)
    except:
        return [], "Erro ao filtrar layer de dutos."

    linhas_processadas = 0
    
    # 3. ASSOCIAÇÃO GEOMÉTRICA
    for linha in entidades_linhas:
        comp, centro_linha = obter_comprimento_e_centro(linha)
        if comp <= 0: continue
        
        # Busca etiqueta mais próxima
        idx_mais_prox = -1
        menor_dist = float('inf')
        
        for i, et in enumerate(etiquetas):
            # Pré-filtro (Bounding Box simples para velocidade)
            dx = abs(et['pos'][0] - centro_linha[0])
            dy = abs(et['pos'][1] - centro_linha[1])
            
            if dx > raio_maximo or dy > raio_maximo: continue
            
            dist = math.hypot(dx, dy)
            if dist < menor_dist:
                menor_dist = dist
                idx_mais_prox = i
        
        # Atribui se estiver no raio
        if idx_mais_prox != -1 and menor_dist <= raio_maximo:
            etiquetas[idx_mais_prox]['soma_linhas'] += comp
            etiquetas[idx_mais_prox]['qtd_linhas'] += 1
            linhas_processadas += 1
            
    # 4. CONSOLIDAÇÃO
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
        
    return resultado_final, f"Sucesso! {linhas_processadas} segmentos de linha associados a textos."

# ============================================================================
# 3. INTERFACE
# ============================================================================
with st.sidebar:
    st.header("⚙️ Calibração")
    
    unidade_desenho = st.selectbox("Unidade do CAD", ["Centímetros (cm)", "Metros (m)", "Milímetros (mm)"])
    
    # Ajuste automático do raio sugerido
    if unidade_desenho == "Centímetros (cm)": raio_def = 150.0 # 1.5m
    elif unidade_desenho == "Metros (m)": raio_def = 1.5
    else: raio_def = 1500.0
    
    raio_atracao = st.number_input("Raio de Atração", value=raio_def, help="Distância máx entre o Texto e a Linha do duto.")
    
    st.divider()
    modo_desenho = st.radio("Estilo de Desenho:", ["Linha Dupla (Paredes)", "Linha Única (Unifilar)"])
    fator_divisao = 2.0 if modo_desenho == "Linha Dupla (Paredes)" else 1.0
    
    st.divider()
    classe_pressao = st.selectbox("Classe Pressão", ["Classe A", "Classe B", "Classe C"])
    perda = st.number_input("% Perda", value=10.0)
    isolamento = st.selectbox("Isolamento", ["Lã de Vidro", "Borracha", "Isopor", "Nenhum"])

# --- UPLOAD ---
uploaded_dxf = st.file_uploader("📂 Carregar DXF (Qualquer Versão)", type=["dxf"])

if uploaded_dxf:
    with st.spinner("Analisando estrutura do arquivo..."):
        # Chama a função segura que usa arquivo temporário
        layers_disponiveis, doc_carregado, erro_leitura = ler_dxf_seguro(uploaded_dxf)
    
    if erro_leitura:
        st.error("Falha ao ler o arquivo.")
        st.code(erro_leitura)
        st.info("Dica: Tente salvar como DXF 2010 ou R12 no AutoCAD.")
        
    elif layers_disponiveis:
        st.success(f"Arquivo lido com sucesso! {len(layers_disponiveis)} Layers encontrados.")
        
        c1, c2 = st.columns(2)
        
        # Tenta pré-selecionar layers com nomes sugestivos
        idx_d = 0
        idx_t = 0
        for i, l in enumerate(layers_disponiveis):
            lu = l.upper()
            if "DUTO" in lu or "DUCT" in lu or "M-SUPP" in lu: idx_d = i
            if "TEXT" in lu or "TAG" in lu or "COT" in lu or "ANNO" in lu: idx_t = i
            
        layer_dutos = c1.selectbox("Layer das LINHAS (Dutos):", layers_disponiveis, index=idx_d)
        layer_textos = c2.selectbox("Layer dos TEXTOS (Etiquetas):", layers_disponiveis, index=idx_t)
        
        if st.button("🚀 Calcular Comprimentos", type="primary"):
            if layer_dutos == layer_textos:
                st.warning("Atenção: Você selecionou o MESMO layer para Linhas e Textos. Isso pode funcionar, mas geralmente eles estão separados.")
            
            with st.spinner("Mapeando geometria..."):
                # Define fator de conversão para metros
                fator_m = 1.0
                if unidade_desenho == "Centímetros (cm)": fator_m = 0.01
                elif unidade_desenho == "Milímetros (mm)": fator_m = 0.001
                
                lista_res, log = processar_por_layers(doc_carregado, layer_dutos, layer_textos, raio_atracao, fator_divisao)
                
                if lista_res:
                    df = pd.DataFrame(lista_res)
                    
                    # Converte comprimento acumulado para Metros
                    df['Comprimento Total (m)'] = df['Comprimento Total (m)'] * fator_m
                    
                    # Regex para extrair Largura x Altura
                    def extrair_medidas(txt):
                        # Padrão 500x300 ou 500X300
                        match_rect = re.search(r'(\d+)\s*[xX]\s*(\d+)', txt)
                        if match_rect:
                            return float(match_rect.group(1)), float(match_rect.group(2)), "Retangular"
                        
                        # Padrão Diâmetro (ø200, 200ø, diam 200)
                        match_circ = re.search(r'[øØ](\d+)|(\d+)[øØ]|DIAM\s*(\d+)', txt.upper())
                        if match_circ:
                            # Pega qualquer grupo que não seja None
                            val = next((g for g in match_circ.groups() if g is not None), 0)
                            return float(val), float(val), "Circular"
                            
                        return 0, 0, "Indefinido"

                    df[['Largura', 'Altura', 'Tipo']] = df['Bitola'].apply(lambda x: pd.Series(extrair_medidas(x)))
                    
                    # Filtra apenas o que foi identificado como medida válida
                    df_final = df[df['Largura'] > 0].copy()
                    
                    if not df_final.empty:
                        # Cálculos Finais
                        df_final['Perímetro (m)'] = (2*df_final['Largura'] + 2*df_final['Altura']) / 1000
                        
                        # Ajuste para circular: Pi * D
                        mask_circ = df_final['Tipo'] == 'Circular'
                        df_final.loc[mask_circ, 'Perímetro (m)'] = (math.pi * df_final.loc[mask_circ, 'Largura']) / 1000
                        
                        df_final['Área (m²)'] = df_final['Perímetro (m)'] * df_final['Comprimento Total (m)']
                        
                        # Totais com Perda
                        fator_p = 1 + (perda/100)
                        area_tot = (df_final['Área (m²)'] * fator_p).sum()
                        peso_tot = area_tot * 5.6
                        
                        st.divider()
                        c_res1, c_res2, c_res3 = st.columns(3)
                        c_res1.metric("Área Total (c/ Perda)", f"{area_tot:,.2f} m²")
                        c_res2.metric("Peso Total", f"{peso_tot:,.0f} kg")
                        c_res3.metric("Isolamento", f"{area_tot:,.2f} m²" if isolamento != "Nenhum" else "-")
                        
                        st.subheader("📋 Tabela de Quantitativos")
                        st.dataframe(
                            df_final[['Bitola', 'Tipo', 'Comprimento Total (m)', 'Área (m²)']]
                            .sort_values('Área (m²)', ascending=False)
                            .style.format("{:.2f}")
                        )
                        st.success(log)
                    else:
                        st.warning("As linhas foram medidas, mas os textos próximos não parecem medidas (ex: 500x300).")
                        st.write("Exemplos do que foi lido:", df['Bitola'].head(10).tolist())
                else:
                    st.error("Nenhuma conexão feita. Verifique se os Layers estão corretos e se o 'Raio de Atração' é suficiente.")
