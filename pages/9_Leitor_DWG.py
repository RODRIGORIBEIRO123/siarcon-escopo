import streamlit as st
import ezdxf
from ezdxf import recover
from ezdxf.addons import odafc # Módulo de conversão
from ezdxf.addons.drawing import RenderContext, Frontend
from ezdxf.addons.drawing.matplotlib import MatplotlibBackend
import matplotlib.pyplot as plt
import pandas as pd
import os
import tempfile
import shutil

st.set_page_config(page_title="Leitor CAD (DWG/DXF)", page_icon="📐", layout="wide")

st.title("📐 Leitor Inteligente CAD")
st.markdown("Suporta **.DWG** (via conversão automática) e **.DXF** nativo.")

# --- VERIFICAÇÃO DO CONVERSOR ---
# Verifica se o ODA File Converter está instalado no sistema
oda_instalado = shutil.which("ODAFileConverter") or shutil.which("ODAFileConverter.exe")

if not oda_instalado:
    st.warning("⚠️ **Aviso:** O software 'ODA File Converter' não foi detectado neste computador.")
    st.info("Para ler arquivos **.DWG**, você precisa instalar o ODA File Converter. Sem ele, apenas **.DXF** funcionará.")
else:
    st.success("✅ Conversor ODA detectado! Leitura de DWG habilitada.")

# --- UPLOAD ---
arquivo_cad = st.file_uploader("Arraste seu projeto (DWG ou DXF)", type=["dxf", "dwg"])

def processar_arquivo(uploaded_file):
    # 1. Salva o arquivo original temporariamente
    sulfixo = f".{uploaded_file.name.split('.')[-1].lower()}"
    with tempfile.NamedTemporaryFile(delete=False, suffix=sulfixo) as tmp:
        tmp.write(uploaded_file.getbuffer())
        path_original = tmp.name

    doc = None
    
    # 2. Lógica de Leitura
    try:
        if sulfixo == ".dwg":
            # --- ROTA DE CONVERSÃO (DWG -> DXF) ---
            if oda_instalado:
                with st.spinner("🔄 Convertendo DWG para DXF (isso pode levar alguns segundos)..."):
                    # O ezdxf usa o ODA instalado para ler o DWG e entregar um objeto doc
                    doc = odafc.readfile(path_original)
            else:
                st.error("❌ Você enviou um DWG, mas o conversor não está instalado.")
                return None
        else:
            # --- ROTA DIRETA (DXF) ---
            try:
                doc = ezdxf.readfile(path_original)
            except:
                # Tenta recuperar se tiver erros leves
                doc, auditor = recover.readfile(path_original)

    except Exception as e:
        st.error(f"Erro ao processar arquivo: {e}")
    finally:
        # Limpa o arquivo original do disco
        if os.path.exists(path_original):
            os.remove(path_original)
            
    return doc

if arquivo_cad:
    st.divider()
    
    # Processa o arquivo
    doc = processar_arquivo(arquivo_cad)

    if doc:
        msp = doc.modelspace()
        
        # --- ABAS DE RESULTADO ---
        tab1, tab2, tab3 = st.tabs(["👁️ Planta Baixa", "📝 Dados/Texto", "📚 Layers"])

        # 1. VISUALIZAÇÃO
        with tab1:
            st.caption("Renderização simplificada (Matplotlib)")
            with st.spinner("Desenhando..."):
                try:
                    fig = plt.figure(figsize=(12, 8))
                    ax = fig.add_axes([0, 0, 1, 1])
                    ctx = RenderContext(doc)
                    out = MatplotlibBackend(ax)
                    Frontend(ctx, out).draw_layout(msp, finalize=True)
                    st.pyplot(fig)
                except Exception as e:
                    st.warning(f"Não foi possível gerar a imagem: {e}")

        # 2. TEXTOS (EXTRAÇÃO DE DADOS)
        with tab2:
            st.subheader("Conteúdo de Texto")
            textos = []
            # Busca MText (Texto Múltiplo) e Text (Texto Simples)
            for entity in msp.query('TEXT MTEXT'):
                textos.append({
                    "Conteúdo": entity.dxf.text,
                    "Layer": entity.dxf.layer
                })
            
            if textos:
                df = pd.DataFrame(textos)
                st.dataframe(df, use_container_width=True)
                
                # Busca Rápida
                busca = st.text_input("🔎 Procurar por (ex: 'Aço', 'Especificação')")
                if busca:
                    res = df[df['Conteúdo'].str.contains(busca, case=False, na=False)]
                    st.write("Resultados:")
                    st.dataframe(res)
            else:
                st.info("Nenhum texto detectado neste arquivo.")

        # 3. LAYERS
        with tab3:
            lista_layers = [layer.dxf.name for layer in doc.layers]
            st.write(f"Total de Layers: {len(lista_layers)}")
            st.code(lista_layers)

else:
    # Dicas na tela inicial
    c1, c2 = st.columns(2)
    with c1:
        st.info("💡 **Dica DWG:**\nPara ler arquivos .DWG, certifique-se de instalar o **ODA File Converter** no servidor.")
    with c2:
        st.info("💡 **Dica DXF:**\nArquivos .DXF são lidos nativamente e são mais rápidos.")
