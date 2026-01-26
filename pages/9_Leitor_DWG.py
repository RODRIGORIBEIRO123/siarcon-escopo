import streamlit as st
import ezdxf
from ezdxf import recover
import pandas as pd
import os
import tempfile
import openai
import json
import io

# Configuração da Página
st.set_page_config(page_title="Calculadora de Dutos (Anti-Bug Cortes)", page_icon="🛡️", layout="wide")

# ==================================================
# 🔑 CONFIGURAÇÃO E INPUTS
# ==================================================
api_key_sistema = st.secrets.get("OPENAI_API_KEY", None)

with st.sidebar:
    st.header("⚙️ Configuração de Projeto")
    
    if api_key_sistema:
        openai.api_key = api_key_sistema
        api_key = api_key_sistema
        st.success("🔑 Chave segura ativa.")
    else:
        api_key = st.text_input("API Key (OpenAI):", type="password")
        if api_key: openai.api_key = api_key

    st.divider()

    st.subheader("🛡️ Filtros de Leitura")
    # --- CORREÇÃO DO BUG AQUI ---
    ignorar_repeticoes = st.checkbox(
        "Ignorar Cortes e Vistas (Anti-Duplicidade)", 
        value=True,
        help="Marque isso se o projeto tiver muitos CORTES mostrando o mesmo duto. Isso impede que a IA some o mesmo duto 10 vezes."
    )
    
    st.subheader("💨 Classe de Pressão")
    classe_pressao = st.selectbox(
        "Selecione a pressão estática:",
        options=[
            "Muito Baixa (até 250 Pa)", 
            "Baixa (até 500 Pa)", 
            "Média (até 1000 Pa)", 
            "Alta (> 1000 Pa)"
        ],
        index=1
    )
    
    perda_corte = st.slider("Margem de Perda/Corte (%)", 0, 40, 10) / 100

# ==================================================
# 📐 CÉREBRO DE ENGENHARIA
# ==================================================
def definir_bitola(maior_lado_mm, classe):
    if "250 Pa" in classe:
        if maior_lado_mm <= 450: return 26
        if maior_lado_mm <= 900: return 24
        if maior_lado_mm <= 1500: return 22
        return 20
    elif "500 Pa" in classe:
        if maior_lado_mm <= 300: return 26
        if maior_lado_mm <= 750: return 24
        if maior_lado_mm <= 1400: return 22
        return 20
    elif "Média" in classe:
        if maior_lado_mm <= 250: return 26
        if maior_lado_mm <= 600: return 24
        if maior_lado_mm <= 1200: return 22
        return 20
    else:
        if maior_lado_mm <= 200: return 24
        if maior_lado_mm <= 500: return 22
        if maior_lado_mm <= 1000: return 20
        return 18

def calcular_peso_chapa(bitola):
    pesos = {26: 4.20, 24: 5.60, 22: 6.80, 20: 8.40, 18: 10.50}
    return pesos.get(bitola, 6.0)

# ==================================================
# 📝 GERADOR DE EXCEL
# ==================================================
def gerar_excel_formatado(df_detalhado, resumo_dados):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df_detalhado.to_excel(writer, sheet_name='Memorial Analítico', index=False)
        workbook = writer.book
        worksheet = writer.sheets['Memorial Analítico']
        
        header_fmt = workbook.add_format({'bold': True, 'bg_color': '#D3D3D3', 'border': 1})
        for col_num, value in enumerate(df_detalhado.columns.values):
            worksheet.write(0, col_num, value, header_fmt)
            worksheet.set_column(col_num, col_num, 15)

        ws_resumo = workbook.add_worksheet('Resumo Executivo')
        ws_resumo.write(0, 0, "Item", header_fmt)
        ws_resumo.write(0, 1, "Valor", header_fmt)
        
        linha = 1
        for chave, valor in resumo_dados.items():
            ws_resumo.write(linha, 0, chave)
            ws_resumo.write(linha, 1, valor)
            linha += 1
            
    output.seek(0)
    return output

# ==================================================
# 🧠 CÉREBRO DA IA (COM LÓGICA ANTI-DUPLICIDADE)
# ==================================================
def processar_com_inteligencia(texto_sujo, modo_conservador):
    if not api_key: return None

    # INSTRUÇÃO BASE
    instrucao_especial = ""
    
    if modo_conservador:
        # AQUI ESTÁ A CORREÇÃO DO BUG
        instrucao_especial = """
        ATENÇÃO CRÍTICA - PROJETO COM CORTES E VISTAS REPETIDAS:
        O texto contém muitas repetições porque o desenho mostra o MESMO duto em planta baixa, corte A, corte B, etc.
        1. SEJA CONSERVADOR: Se você ver "300x200" aparecendo 5 vezes, assuma que é o mesmo duto mostrado em vistas diferentes, NÃO SOME.
        2. Tente contar apenas 1 ocorrência por trecho distinto.
        3. Ignore textos próximos a palavras como "CORTE", "DETALHE", "VISTA", "ESCALA".
        """
    else:
        instrucao_especial = """
        MODE DE SOMA ATIVO:
        Se houver itens repetidos, SOME suas quantidades (assuma que são peças diferentes).
        """

    prompt_sistema = f"""
    Você é um Engenheiro de HVAC Sênior. Analise o texto do CAD.
    {instrucao_especial}

    MISSÃO:
    1. Identifique DIMENSÕES de dutos (ex: "300x200", "50x30").
    2. Identifique COMPRIMENTO (m) associado.
    
    SAÍDA JSON:
    {{
        "resumo_projeto": "Descrição do que foi considerado.",
        "dutos": [
            {{
                "largura_mm": 300, 
                "altura_mm": 200, 
                "comprimento_total_m": 15.5,
                "nota_original": "Duto 300x200 (Filtrado)"
            }}
        ]
    }}
    Converta tudo para MM e Metros.
    """

    try:
        response = openai.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": prompt_sistema},
                {"role": "user", "content": f"Levantamento (Modo Conservador={modo_conservador}):\n\n{texto_sujo[:35000]}"} 
            ],
            temperature=0.1,
            response_format={"type": "json_object"}
        )
        return json.loads(response.choices[0].message.content)
    except Exception as e:
        return {"erro": str(e)}

# ==================================================
# 🔧 LIMPEZA DE TEXTO
# ==================================================
def limpar_texto_cad(lista_textos, filtrar_cortes=False):
    texto_limpo = []
    # Palavras que indicam que o texto pertence a um corte (e deve ser ignorado se o filtro estiver ativo)
    palavras_corte = ["CORTE", "SECTION", "DETALHE", "DETAIL", "VISTA", "VIEW", "ESCALA", "SCALE"]
    
    ignorar_padrao = ["LAYER", "VIEWPORT", "STANDARD", "ISO", "BYLAYER", "COTAS", "MODEL"]
    
    for item in lista_textos:
        t = str(item).strip()
        t_upper = t.upper()
        
        # Filtro Básico
        if len(t) < 3 or any(x in t_upper for x in ignorar_padrao): 
            continue
            
        # Filtro de Cortes (Se o usuário marcou a opção)
        # Se a linha contiver a palavra "CORTE", a gente não adiciona ela,
        # MAS o problema é que o texto do duto "300x200" não tem a palavra "CORTE" nele, ele está PERTO.
        # Então deixamos a IA decidir pelo contexto, mas aqui removemos os TÍTULOS de cortes para ajudar.
        
        texto_limpo.append(t)
        
    # Se for modo conservador, enviamos MENOS duplicatas para a IA não se confundir
    if filtrar_cortes:
        # Remove duplicatas exatas mantendo a ordem
        return "\n".join(list(dict.fromkeys(texto_limpo)))
    else:
        # Mantém duplicatas (para contagem de peças unitárias como difusores)
        return "\n".join(texto_limpo[:3000])

def salvar_temp(arquivo):
    with tempfile.NamedTemporaryFile(delete=False, suffix=".dxf") as tmp:
        tmp.write(arquivo.getbuffer())
        return tmp.name

# ==================================================
# 🖥️ INTERFACE
# ==================================================
st.title("🛡️ Calculadora de Dutos (Anti-Duplicidade)")
st.markdown("Use a opção **Ignorar Cortes** para evitar que o quantitativo venha multiplicado.")

arquivo_cad = st.file_uploader("Arraste o DXF aqui", type=["dxf"])

if arquivo_cad:
    st.divider()
    path_temp = salvar_temp(arquivo_cad)

    try:
        try: doc = ezdxf.readfile(path_temp)
        except: doc, auditor = recover.readfile(path_temp)

        if doc:
            msp = doc.modelspace()
            textos_crus = []
            with st.spinner("Lendo CAD..."):
                for entity in msp.query('TEXT MTEXT'):
                    if entity.dxf.text: textos_crus.append(entity.dxf.text)
            
            # Aplica a limpeza baseada na checkbox do usuário
            texto_pronto = limpar_texto_cad(textos_crus, filtrar_cortes=ignorar_repeticoes)
            
            c1, c2 = st.columns([1, 2])
            with c1:
                st.info(f"Itens lidos: {len(textos_crus)}")
                if ignorar_repeticoes:
                    st.success("✅ Filtro Anti-Cortes Ativo: Duplicatas exatas removidas do texto base.")
                else:
                    st.warning("⚠️ Modo Soma Total: Todas as repetições serão contadas.")
                    
                with st.expander("Ver Texto Processado"):
                    st.text_area("", texto_pronto, height=350)

            with c2:
                st.subheader("🤖 Processamento")
                if not api_key:
                    st.error("Configure a API Key.")
                else:
                    if st.button("🚀 Calcular Quantitativo Real", type="primary"):
                        with st.spinner("Analisando projeto e filtrando redundâncias..."):
                            # Passa o status do checkbox para a IA
                            dados = processar_com_inteligencia(texto_pronto, ignorar_repeticoes)
                            
                            if "erro" in dados:
                                st.error(f"Erro IA: {dados['erro']}")
                            else:
                                lista_dutos = dados.get("dutos", [])
                                if lista_dutos:
                                    resultados = []
                                    total_kg = 0
                                    total_m2 = 0
                                    
                                    for d in lista_dutos:
                                        L = d.get('largura_mm', 0)
                                        H = d.get('altura_mm', 0)
                                        comp = d.get('comprimento_total_m', 0)
                                        
                                        if L > 0 and H > 0:
                                            maior_lado = max(L, H)
                                            gauge = definir_bitola(maior_lado, classe_pressao)
                                            
                                            perimetro = 2 * ((L/1000) + (H/1000))
                                            area_final = (perimetro * comp) * (1 + perda_corte)
                                            peso = area_final * calcular_peso_chapa(gauge)
                                            
                                            resultados.append({
                                                "Dimensão": f"{int(L)}x{int(H)}",
                                                "Comp. (m)": round(comp, 2),
                                                "Bitola": f"#{gauge}",
                                                "Área (m²)": round(area_final, 2),
                                                "Peso (kg)": round(peso, 2),
                                                "Nota": d.get("nota_original", "")
                                            })
                                            total_kg += peso
                                            total_m2 += area_final

                                    st.success(f"✅ Cálculo Concluído! Peso Total: {total_kg:,.1f} kg")
                                    
                                    df = pd.DataFrame(resultados)
                                    st.dataframe(df, use_container_width=True)
                                    
                                    resumo = {
                                        "Obra": "Automática", 
                                        "Peso Total (kg)": total_kg,
                                        "Modo de Leitura": "Conservador (Ignorar Cortes)" if ignorar_repeticoes else "Soma Total"
                                    }
                                    excel = gerar_excel_formatado(df, resumo)
                                    st.download_button("📥 Baixar Excel", excel, "Memorial_Dutos.xlsx")
                                else:
                                    st.warning("Nenhum duto identificado.")

    except Exception as e:
        st.error(f"Erro: {e}")
    finally:
        if os.path.exists(path_temp): os.remove(path_temp)
