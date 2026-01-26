import streamlit as st
import ezdxf
from ezdxf import recover
from ezdxf.addons.drawing import RenderContext, Frontend
from ezdxf.addons.drawing.matplotlib import MatplotlibBackend
import matplotlib.pyplot as plt
import pandas as pd
import os
import tempfile

st.set_page_config(page_title="Leitor de Projetos CAD", page_icon="📐", layout="wide")

st.title("📐 Leitor de Projetos (DWG/DXF)")
st.markdown("Visualize o projeto e extraia textos, anotações e nomes de layers.")

# --- ÁREA DE UPLOAD ---
arquivo_cad = st.file_uploader("Arraste seu arquivo CAD aqui (.dxf é mais garantido)", type=["dxf", "dwg"])

# Função para salvar o arquivo temporariamente (ezdxf precisa ler do disco)
def salvar_temp(arquivo):
    with tempfile.NamedTemporaryFile(delete=False, suffix=f".{arquivo.name.split('.')[-1]}") as tmp:
        tmp.write(arquivo.getbuffer())
        return tmp.name

if arquivo_cad:
    st.divider()
    path_temp = salvar_temp(arquivo_cad)

    try:
        doc = None
        # Tenta ler o arquivo (com recuperação de erros se for corrompido)
        try:
            doc, auditor = recover.readfile(path_temp)
        except Exception as e:
            st.warning(f"Leitura direta falhou, tentando modo inseguro... Erro: {e}")
            try:
                doc = ezdxf.readfile(path_temp)
            except Exception as e2:
                st.error(f"Não foi possível ler este arquivo CAD. Tente salvar como DXF 2010 ou anterior.\nErro: {e2}")
                st.stop()

        if doc:
            # Pega o ModelSpace (onde o desenho fica)
            msp = doc.modelspace()
            
            # --- ABAS DE ANÁLISE ---
            tab_vis, tab_dados, tab_layers = st.tabs(["👁️ Visualização", "📝 Textos Extraídos", "📚 Layers (Camadas)"])

            # 1. VISUALIZAÇÃO (Renderiza o CAD como Imagem)
            with tab_vis:
                with st.spinner("Gerando imagem do projeto (isso pode demorar em arquivos pesados)..."):
                    try:
                        fig = plt.figure(figsize=(10, 6))
                        ax = fig.add_axes([0, 0, 1, 1])
                        ctx = RenderContext(doc)
                        out = MatplotlibBackend(ax)
                        Frontend(ctx, out).draw_layout(msp, finalize=True)
                        st.pyplot(fig)
                    except Exception as e:
                        st.error(f"Erro ao renderizar imagem: {e}")
                        st.info("O arquivo pode ser lido, mas é muito complexo para desenhar aqui. Veja os dados nas outras abas.")

            # 2. EXTRAÇÃO DE TEXTO (Onde está o ouro)
            with tab_dados:
                st.subheader("Conteúdo de Texto Encontrado")
                st.caption("Aqui aparecem especificações, notas de projeto e cotas.")
                
                textos = []
                # Varre entidades de Texto e MText (Texto Múltiplo)
                for entity in msp.query('TEXT MTEXT'):
                    val = entity.dxf.text
                    layer = entity.dxf.layer
                    if val and str(val).strip():
                        textos.append({"Texto": val, "Layer": layer})
                
                if textos:
                    df_textos = pd.DataFrame(textos)
                    st.dataframe(df_textos, use_container_width=True)
                    
                    # Filtro Rápido
                    filtro = st.text_input("🔍 Buscar no projeto (Ex: 'Duto', 'Cobre', 'Material')")
                    if filtro:
                        filtrado = df_textos[df_textos['Texto'].str.contains(filtro, case=False, na=False)]
                        st.write(f"Resultados para '{filtro}':")
                        st.dataframe(filtrado)
                else:
                    st.info("Nenhum objeto de texto encontrado neste desenho.")

            # 3. EXTRAÇÃO DE LAYERS (Para entender as disciplinas)
            with tab_layers:
                st.subheader("Estrutura de Camadas")
                layers = []
                for layer in doc.layers:
                    layers.append(layer.dxf.name)
                
                st.write(f"Total de Layers: {len(layers)}")
                st.code(layers)
                
                # Análise simples de disciplina pelo nome do layer
                if any("ELE" in l.upper() for l in layers): st.success("💡 Identifiquei layers de ELÉTRICA")
                if any("HID" in l.upper() for l in layers): st.info("💡 Identifiquei layers de HIDRÁULICA")
                if any("AR" in l.upper() or "MEC" in l.upper() for l in layers): st.warning("💡 Identifiquei layers de MECÂNICA/AR")

    except Exception as e:
        st.error(f"Erro crítico: {e}")
    
    finally:
        # Limpa o arquivo temporário para não encher o disco
        if os.path.exists(path_temp):
            os.remove(path_temp)

else:
    c1, c2 = st.columns(2)
    with c1:
        st.info("💡 **Dica 1:**\nArquivos **.DXF** abrem muito mais rápido e com menos erros que .DWG.")
    with c2:
        st.info("💡 **Dica 2:**\nEste leitor foca em **TEXTO**. Ele é ótimo para ler notas de rodapé e especificações técnicas dentro do CAD.")
