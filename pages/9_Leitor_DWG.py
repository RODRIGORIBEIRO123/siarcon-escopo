import streamlit as st
import ezdxf
from openai import OpenAI
import pandas as pd
import io
from collections import Counter

# --- 🔒 BLOCO DE SEGURANÇA ---
if 'logado' not in st.session_state or not st.session_state['logado']:
    st.warning("🔒 Acesso negado. Faça login no Dashboard.")
    st.stop()

st.set_page_config(page_title="Leitor DXF (ABNT)", page_icon="📐", layout="wide")

st.title("📐 Leitor Técnico (DXF) - Contagem Automática")
st.markdown("""
**Melhoria de Precisão:** O sistema agora conta quantas vezes cada etiqueta aparece no desenho.
Para os dutos, ele multiplica essa contagem pelo **Comprimento Padrão da Peça** (editável).
""")

# ============================================================================
# 1. CONFIGURAÇÕES (ABNT NBR 16401)
# ============================================================================
with st.sidebar:
    st.header("⚙️ Configurações (ABNT)")
    
    classe_pressao = st.selectbox(
        "Classe de Pressão (ABNT NBR 16401)", 
        [
            "Classe A (Baixa Pressão - até 500 Pa)", 
            "Classe B (Média Pressão - até 1000 Pa)", 
            "Classe C (Alta Pressão - até 2000 Pa)",
            "Classe D (Muito Alta - Especial)"
        ]
    )
    
    # NOVA CONFIGURAÇÃO PARA CÁLCULO DE COMPRIMENTO
    comp_padrao = st.number_input("Comprimento Padrão da Peça de Duto (m)", value=1.10, step=0.10, help="Usado para estimar a metragem linear baseada na quantidade de etiquetas encontradas.")
    
    perda_corte = st.number_input("% Perda / Corte (Chapas)", min_value=0.0, max_value=20.0, value=10.0, step=1.0)
    tipo_isolamento = st.selectbox("Isolamento", ["Lã de Vidro", "Borracha Elast.", "Poliestireno (Isopor)", "Sem Isolamento"])

# ============================================================================
# 2. FUNÇÕES DE EXTRAÇÃO INTELIGENTE
# ============================================================================
def extrair_e_contar_textos(bytes_file):
    """Lê o DXF e já retorna uma contagem de frequência de cada texto"""
    textos = []
    
    # Tenta decodificar (Fallback robusto)
    try: content_str = bytes_file.getvalue().decode("cp1252")
    except: 
        try: content_str = bytes_file.getvalue().decode("utf-8", errors='ignore')
        except: return {}, "Erro Fatal"

    # Leitura via EZDXF ou BRUTE FORCE (Híbrido)
    try:
        stream = io.StringIO(content_str)
        doc = ezdxf.read(stream)
        msp = doc.modelspace()
        for e in msp.query('TEXT MTEXT'):
            txt = e.dxf.text if e.dxftype() == 'TEXT' else e.text
            if txt and len(txt) > 2: textos.append(txt.strip())
        metodo = "Leitura Geométrica"
    except:
        # Modo Bruto se falhar
        linhas = content_str.split('\n')
        for i, linha in enumerate(linhas):
            if linha.strip() == '1' and i + 1 < len(linhas):
                t = linhas[i+1].strip()
                if len(t) > 2 and not t.startswith('{'): textos.append(t)
        metodo = "Leitura Bruta"
    
    # CONTAGEM INTELIGENTE (O Python conta, a IA só classifica)
    # Isso garante que o número de peças seja exato, sem alucinação da IA
    contagem = Counter(textos)
    return contagem, metodo

def analisar_com_ia_precisa(dicionario_contagem):
    if "openai" not in st.secrets:
        st.error("🚨 Chave OpenAI não configurada."); return None
    
    client = OpenAI(api_key=st.secrets["openai"]["api_key"])
    
    # Prepara o resumo para a IA (Texto : Quantidade)
    # Mandamos os top 400 itens mais frequentes para focar no que importa
    lista_para_ia = ""
    for k, v in dicionario_contagem.most_common(400):
        lista_para_ia += f"TEXTO: '{k}' | FREQUENCIA: {v}\n"
    
    prompt = """
    Você é um Engenheiro Sênior de Orçamentos HVAC.
    Abaixo está uma lista de TEXTOS extraídos de um DXF e quantas vezes aparecem.
    
    SEU OBJETIVO: Classificar esses textos e extrair detalhes técnicos.
    
    REGRAS DE EXTRAÇÃO:
    1. DUTOS: Procure dimensões (ex: 300x200, 50x30, ø250). Associe a Frequência à "Quantidade de Peças".
    2. TERMINAIS: Procure Grelhas (G-), Difusores (D-), Venezianas, Dampers.
    3. EQUIPAMENTOS (CRÍTICO): Procure por FANCOIL, CHILLER, SPLIT, K7, VRF.
       - Tente extrair DETALHES que estiverem no texto ou próximos (TR, BTU, HP, CV, Volts).
       - Ex: "FC-01 5TR" -> Tag: FC-01, Detalhe: 5TR.
    4. ELETRICA: Quadros (QGBT, QF), Painéis, Tomadas, Sensores.

    SAÍDA OBRIGATÓRIA (CSV com ponto e vírgula):
    
    ---DUTOS---
    Largura;Altura;Tipo;QtdPeças
    300;200;Rect;15
    500;400;Rect;8
    
    ---TERMINAIS---
    Item;QtdTotal
    Grelha Retorno 600x600;12
    Difusor Linear 2 vias;20
    
    ---EQUIPAMENTOS---
    Tag;Tipo;DetalhesTecnicos;Qtd
    FC-01;Fancoil;5TR 220V;2
    SPL-03;Split Hiwall;12000 BTU Inverter;5
    
    ---ELETRICA---
    Tag;Descrição;Qtd
    Q-01;Quadro de Força;1
    """
    
    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": f"Classifique estes itens contados:\n{lista_para_ia}"}
            ],
            temperature=0.0 # Temperatura zero para precisão máxima
        )
        return response.choices[0].message.content
    except Exception as e:
        st.error(f"Erro na IA: {e}")
        return None

def processar_resposta_ia(resposta):
    blocos = {"DUTOS": [], "TERMINAIS": [], "EQUIPAMENTOS": [], "ELETRICA": []}
    atual = None
    for linha in resposta.split('\n'):
        linha = linha.strip()
        if "---DUTOS---" in linha: atual = "DUTOS"; continue
        if "---TERMINAIS---" in linha: atual = "TERMINAIS"; continue
        if "---EQUIPAMENTOS---" in linha: atual = "EQUIPAMENTOS"; continue
        if "---ELETRICA---" in linha: atual = "ELETRICA"; continue
        
        # Filtra cabeçalhos e linhas vazias
        if atual and linha and ";" in linha and "Largura" not in linha and "Item" not in linha:
            blocos[atual].append(linha.split(';'))
    return blocos

# ============================================================================
# 3. INTERFACE PRINCIPAL
# ============================================================================
uploaded_dxf = st.file_uploader("📂 Carregar Arquivo .DXF (Salve como ASCII 2010)", type=["dxf"])

if uploaded_dxf:
    with st.spinner("Lendo e Contando itens no desenho..."):
        contagem, metodo = extrair_e_contar_textos(uploaded_dxf)
        
    if contagem:
        st.success(f"✅ Arquivo processado via {metodo}. {len(contagem)} textos únicos encontrados.")
        
        if st.button("🚀 Extrair Quantitativos (IA)", type="primary"):
            with st.spinner("Classificando Dutos, Equipamentos e Elétrica..."):
                resultado_ia = analisar_com_ia_precisa(contagem)
                if resultado_ia:
                    st.session_state['dados_dxf_v2'] = processar_resposta_ia(resultado_ia)
                    st.rerun()
    else:
        st.error("❌ Não foi possível ler textos. Verifique se o arquivo não é apenas uma imagem.")

# ============================================================================
# 4. EXIBIÇÃO (LAYOUT MANTIDO)
# ============================================================================
if 'dados_dxf_v2' in st.session_state:
    dados = st.session_state['dados_dxf_v2']
    
    tab_dutos, tab_term, tab_equip, tab_elet = st.tabs([
        "🌪️ Rede de Dutos (Cálculo)", 
        "💨 Terminais de Ar", 
        "⚙️ Equipamentos", 
        "⚡ Elétrica"
    ])
    
    # --- ABA DUTOS (AGORA COM CÁLCULO DE PEÇAS) ---
    with tab_dutos:
        st.info(f"Cálculo baseado em: {comp_padrao}m por peça (Configurável no menu lateral).")
        
        lista_dutos = dados["DUTOS"]
        if lista_dutos:
            # Cria DataFrame
            try:
                df_dutos = pd.DataFrame(lista_dutos, columns=["Largura", "Altura", "Tipo", "Qtd Peças (Tags)"])
            except:
                # Fallback caso a IA erre coluna
                df_dutos = pd.DataFrame(lista_dutos)
            
            # Força numérico
            df_dutos["Qtd Peças (Tags)"] = pd.to_numeric(df_dutos["Qtd Peças (Tags)"], errors='coerce').fillna(1)
            
            # Tabela Editável
            df_editado = st.data_editor(df_dutos, num_rows="dynamic", key="editor_dutos_v2")
            
            st.divider()
            st.subheader("📊 Memória de Cálculo ABNT")
            
            try:
                df_calc = df_editado.copy()
                for col in ["Largura", "Altura"]:
                    df_calc[col] = pd.to_numeric(df_calc[col], errors='coerce').fillna(0)
                
                # CÁLCULO AUTOMÁTICO DE COMPRIMENTO TOTAL
                # Comprimento = Qtd Peças * Comprimento Padrão
                df_calc["Comp. Total (m)"] = df_calc["Qtd Peças (Tags)"] * comp_padrao
                
                # Perímetro (m) = (2L + 2A)/1000
                df_calc["Perímetro (m)"] = (2 * df_calc["Largura"] + 2 * df_calc["Altura"]) / 1000
                
                # Área Física
                df_calc["Área (m²)"] = df_calc["Perímetro (m)"] * df_calc["Comp. Total (m)"]
                
                # Aplica Perda
                fator_perda = 1 + (perda_corte / 100)
                df_calc["Área Total c/ Perda (m²)"] = df_calc["Área (m²)"] * fator_perda
                
                area_total = df_calc["Área Total c/ Perda (m²)"].sum()
                peso_estimado = area_total * 5.6 # Estimativa kg/m2 chapa 24/22 média
                
                # Métricas
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("Área Chapa (m²)", f"{area_total:,.2f}")
                c2.metric("Peso Est. (kg)", f"{peso_estimado:,.0f}")
                
                isol_val = f"{area_total:,.2f} m²" if tipo_isolamento != "Sem Isolamento" else "---"
                c3.metric(f"Isolamento", isol_val, delta=tipo_isolamento)
                
                c4.metric("Peças Identificadas", int(df_calc["Qtd Peças (Tags)"].sum()))
                
                st.write("Detalhamento Automático:")
                st.dataframe(df_calc[["Largura", "Altura", "Qtd Peças (Tags)", "Comp. Total (m)", "Área Total c/ Perda (m²)"]])
                
            except Exception as e:
                st.error(f"Erro no cálculo: {e}")
        else:
            st.warning("Nenhum duto identificado.")

    # --- OUTRAS ABAS (COM MELHOR LEITURA DE DETALHES) ---
    with tab_term:
        if dados["TERMINAIS"]:
            st.data_editor(pd.DataFrame(dados["TERMINAIS"], columns=["Item", "Quantidade"]), num_rows="dynamic")
        else: st.info("Nenhum terminal encontrado.")

    with tab_equip:
        st.caption("A IA agora busca especificamente por TR, BTU, HP e Tensão nos textos.")
        if dados["EQUIPAMENTOS"]:
            try:
                st.data_editor(pd.DataFrame(dados["EQUIPAMENTOS"], columns=["Tag", "Tipo", "Detalhes Técnicos", "Qtd"]), num_rows="dynamic")
            except:
                st.data_editor(pd.DataFrame(dados["EQUIPAMENTOS"]))
        else: st.info("Nenhum equipamento encontrado.")

    with tab_elet:
        if dados["ELETRICA"]:
            try:
                st.data_editor(pd.DataFrame(dados["ELETRICA"], columns=["Tag", "Descrição", "Qtd"]), num_rows="dynamic")
            except:
                st.data_editor(pd.DataFrame(dados["ELETRICA"]))
        else: st.info("Nenhum item elétrico encontrado.")
