import streamlit as st
import ezdxf
from ezdxf import recover
import pandas as pd
import tempfile
import os
import re
import math
from collections import Counter

# --- 🔒 SEGURANÇA ---
if 'logado' not in st.session_state or not st.session_state['logado']:
    st.warning("🔒 Acesso negado. Faça login no Dashboard.")
    st.stop()

st.set_page_config(page_title="Leitor DXF (Contagem)", page_icon="🔢", layout="wide")

st.title("🔢 Leitor Estatístico de Dutos")
st.markdown("""
**Abordagem Infalível:** Este método ignora as linhas desenhadas (que costumam dar erro) e foca 100% na leitura das **Etiquetas de Texto**.
O sistema conta quantas peças de cada medida existem e multiplica pelo comprimento padrão de peça (ex: 1.10m).
""")

# ============================================================================
# 1. FUNÇÕES DE EXTRAÇÃO DE TEXTO (BLINDADAS)
# ============================================================================

def limpar_texto_dxf(texto):
    """Remove códigos de formatação do AutoCAD (ex: \\A1;500)"""
    if not texto: return ""
    # Remove códigos de controle como \A1; \C7; etc
    t = re.sub(r'\\[ACFHQTW].*?;', '', texto)
    # Remove chaves {}
    t = t.replace('{', '').replace('}', '')
    return t.strip().upper()

def identificar_medida(texto):
    """
    Analisa se o texto é uma medida de duto.
    Retorna: (Largura, Altura, Tipo) ou (0,0,None)
    """
    t = limpar_texto_dxf(texto)
    
    # 1. Tenta Padrão Retangular (500x300, 500 X 300, 500*300)
    # Regex flexível para pegar números com x no meio
    match_ret = re.search(r'^(\d+)\s*[xX*]\s*(\d+)$', t)
    if match_ret:
        l = float(match_ret.group(1))
        h = float(match_ret.group(2))
        return l, h, "Retangular"
    
    # 2. Tenta Padrão Circular (ø200, 200ø, diam 200)
    # %%C é o código para símbolo de diâmetro no CAD
    match_circ = re.search(r'([øØ]|%%C|DIAM\.?)\s*(\d+)', t)
    match_circ_inv = re.search(r'(\d+)\s*([øØ]|%%C|DIAM\.?)', t)
    
    diam = 0
    if match_circ: diam = float(match_circ.group(2))
    elif match_circ_inv: diam = float(match_circ_inv.group(1))
    
    if diam > 0:
        return diam, diam, "Circular"
        
    return 0, 0, None

def ler_textos_dxf(uploaded_file):
    """
    Lê o DXF e extrai APENAS textos, ignorando geometria corrompida.
    """
    textos_validos = []
    erros = []
    temp_path = None
    
    try:
        # Salva temporário para evitar erro de buffer/rstrip
        with tempfile.NamedTemporaryFile(delete=False, suffix=".dxf") as tmp_file:
            tmp_file.write(uploaded_file.getvalue())
            temp_path = tmp_file.name
            
        # Usa recover para abrir até arquivo corrompido
        doc, auditor = recover.readfile(temp_path)
        
        if auditor.has_errors:
            erros.append(f"O arquivo continha erros que foram corrigidos automaticamente.")

        msp = doc.modelspace()
        
        # Varre apenas entidades de TEXTO
        for e in msp.query('TEXT MTEXT'):
            raw_text = e.dxf.text if e.dxftype() == 'TEXT' else e.text
            
            l, h, tipo = identificar_medida(raw_text)
            if tipo:
                textos_validos.append({
                    'Texto Original': raw_text,
                    'Largura': l,
                    'Altura': h,
                    'Tipo': tipo
                })
                
    except Exception as e:
        erros.append(f"Erro Fatal: {str(e)}")
    finally:
        if temp_path and os.path.exists(temp_path):
            try: os.remove(temp_path)
            except: pass
            
    return textos_validos, erros

# ============================================================================
# 2. INTERFACE E CÁLCULOS
# ============================================================================

with st.sidebar:
    st.header("⚙️ Parâmetros de Obra")
    
    st.info("Como não medimos as linhas, assumimos um comprimento padrão por etiqueta encontrada.")
    comp_padrao_peca = st.number_input("Comp. Padrão da Peça (m)", value=1.10, step=0.05, help="Geralmente dutos retos têm 1.10m ou 1.20m.")
    
    st.divider()
    classe_pressao = st.selectbox("Classe Pressão", ["Classe A (Baixa)", "Classe B (Média)", "Classe C (Alta)"])
    perda = st.number_input("% Perda / Corte", value=10.0)
    isolamento = st.selectbox("Isolamento", ["Lã de Vidro", "Borracha Elast.", "Isopor", "Nenhum"])

# --- UPLOAD ---
uploaded_dxf = st.file_uploader("📂 Carregar Projeto DXF", type=["dxf"])

if uploaded_dxf:
    with st.spinner("Contando etiquetas de duto..."):
        lista_itens, lista_erros = ler_textos_dxf(uploaded_dxf)
        
    if lista_itens:
        if lista_erros:
            with st.expander("⚠️ Avisos de Leitura (Clique para ver)"):
                for err in lista_erros: st.write(err)
        
        # Consolidação (Agrupar por medida igual)
        df_raw = pd.DataFrame(lista_itens)
        
        # Cria uma coluna de identificação única (ex: "500x300 (Retangular)")
        df_raw['Bitola'] = df_raw.apply(lambda x: f"{int(x['Largura'])}x{int(x['Altura'])}" if x['Tipo'] == 'Retangular' else f"ø{int(x['Largura'])}", axis=1)
        
        # Contagem
        df_agrupado = df_raw.groupby(['Bitola', 'Largura', 'Altura', 'Tipo']).size().reset_index(name='Qtd Peças')
        
        st.success(f"Sucesso! Encontramos {len(df_raw)} etiquetas de medida no desenho.")
        
        # --- TABELA INTERATIVA (O CORAÇÃO DA SOLUÇÃO) ---
        st.markdown("### 📋 Ajuste de Quantitativos")
        st.caption("Confira as quantidades. O 'Comp. Unitário' pode ser editado se houver peças especiais.")
        
        # Adiciona coluna de comprimento unitário (Padrão vs Editável)
        df_agrupado['Comp. Unit (m)'] = comp_padrao_peca
        
        # Configura editor
        df_editado = st.data_editor(
            df_agrupado,
            column_config={
                "Bitola": st.column_config.TextColumn("Bitola", disabled=True),
                "Qtd Peças": st.column_config.NumberColumn("Qtd (Tags)", help="Quantas vezes o texto aparece no desenho"),
                "Comp. Unit (m)": st.column_config.NumberColumn("Comp. Peça (m)", min_value=0.1, max_value=6.0, step=0.1),
            },
            hide_index=True,
            use_container_width=True,
            num_rows="dynamic"
        )
        
        st.divider()
        
        # --- CÁLCULOS FINAIS ---
        if not df_editado.empty:
            try:
                # 1. Calcula Perímetro
                # Retangular: (2L + 2A) / 1000
                # Circular: (Pi * D) / 1000
                def calc_perimetro(row):
                    if row['Tipo'] == 'Circular':
                        return (math.pi * row['Largura']) / 1000
                    else:
                        return (2 * row['Largura'] + 2 * row['Altura']) / 1000
                
                df_calc = df_editado.copy()
                df_calc['Perímetro (m)'] = df_calc.apply(calc_perimetro, axis=1)
                
                # 2. Calcula Comprimento Total da Rede
                df_calc['Rede Total (m)'] = df_calc['Qtd Peças'] * df_calc['Comp. Unit (m)']
                
                # 3. Calcula Área
                df_calc['Área Física (m²)'] = df_calc['Perímetro (m)'] * df_calc['Rede Total (m)']
                
                # 4. Totais
                fator_perda = 1 + (perda/100)
                area_total = (df_calc['Área Física (m²)'] * fator_perda).sum()
                peso_total = area_total * 5.6 # Estimativa kg/m2
                
                # --- EXIBIÇÃO DE RESULTADOS ---
                st.subheader("📊 Resultados Finais")
                
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("Área Total (c/ Perda)", f"{area_total:,.2f} m²", delta=f"{perda}% Perda")
                c2.metric("Peso Estimado", f"{peso_total:,.0f} kg", help="Considerando média de 5.6 kg/m²")
                c3.metric("Isolamento", f"{area_total:,.2f} m²" if isolamento != "Nenhum" else "-", delta=isolamento)
                c4.metric("Peças Totais", f"{df_calc['Qtd Peças'].sum()} un")
                
                with st.expander("Ver Memória de Cálculo Detalhada"):
                    st.dataframe(
                        df_calc[['Bitola', 'Qtd Peças', 'Rede Total (m)', 'Área Física (m²)']],
                        use_container_width=True
                    )
            except Exception as e:
                st.error(f"Erro no cálculo: {e}")
        
    else:
        st.warning("Não foram encontradas etiquetas de medida (ex: 500x300 ou ø200) no arquivo.")
        st.info("Dica: Verifique se o arquivo DXF contém textos editáveis e não blocos explodidos em linhas.")
