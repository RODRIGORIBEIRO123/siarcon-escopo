import streamlit as st
import ezdxf
from ezdxf import recover
from ezdxf.addons.drawing import RenderContext, Frontend
from ezdxf.addons.drawing.matplotlib import MatplotlibBackend
import matplotlib.pyplot as plt
import pandas as pd
import os
import tempfile

st.set_page_config(page_title="Leitor de Projetos (DXF)", page_icon="📐", layout="wide")

st.title("📐 Leitor de Projetos de Engenharia")
st.markdown("Visualizador e extrator de dados para arquivos **.DXF**.")

# --- ÁREA DE UPLOAD ---
# Aceita apenas DXF para evitar erros no servidor online
arquivo_cad = st.file_uploader("Arraste seu arquivo .DXF aqui", type=["dxf"])

# Função para salvar temp (o ezdxf precisa ler do disco)
def salvar_temp(arquivo):
    sulfixo = ".dxf"
    with tempfile.NamedTemporaryFile(delete=False, suffix=sulfixo) as tmp:
        tmp.write(arquivo.getbuffer())
        return tmp.name

if arquivo_cad:
    st.divider()
    path_temp = salvar_temp(arquivo_cad)

    try:
        doc = None
        # Tenta ler com recuperação de erros (comum em arquivos CAD antigos)
        try:
            doc = ezdxf.readfile(path_temp)
        except Exception:
            try:
                doc, auditor = recover.readfile(path_temp)
                if auditor.has_errors:
                    st.warning("O arquivo continha alguns erros, mas consegui recuperar.")
            except Exception as e:
                st.error(f"Erro fatal ao ler DXF: {e}")
                st.stop()

        if doc:
            msp = doc.modelspace()
            
            # Abas para organizar a informação
            tab_vis, tab_texto, tab_layers = st.tabs(["👁️ Planta Baixa (Visual)", "📝 Textos & Cotas", "📚 Camadas (Layers)"])

            # 1. VISUALIZAÇÃO GRÁFICA
            with tab_vis:
                st.caption("Renderização da planta baixa (pode levar alguns segundos em projetos grandes)")
                with st.spinner("Desenhando vetores..."):
                    try:
                        # Configuração do Matplotlib para desenhar o CAD
                        fig = plt.figure(figsize=(10, 6), dpi=150)
                        ax = fig.add_axes([0, 0, 1, 1])
                        
                        # Fundo escuro (estilo AutoCAD) ou claro? Vamos de claro para o relatório.
                        ctx = RenderContext(doc)
                        # Removemos o fundo preto padrão para facilitar leitura web
                        out = MatplotlibBackend(ax)
                        
                        Frontend(ctx, out).draw_layout(msp, finalize=True)
                        st.pyplot(fig)
                    except Exception as e:
                        st.error(f"Não consegui desenhar a planta: {e}")
                        st.info("Dica: Isso acontece se o arquivo tiver blocos 3D muito complexos.")

            # 2. EXTRAÇÃO DE TEXTO
            with tab_texto:
                st.subheader("Dados Extraídos (Notas, Legendas, Materiais)")
                
                textos_encontrados = []
                # Procura por TEXT e MTEXT (Texto Múltiplo)
                for entity in msp.query('TEXT MTEXT'):
                    conteudo = entity.dxf.text
                    layer = entity.dxf.layer
                    if conteudo and str(conteudo).strip():
                        textos_encontrados.append({"Texto": conteudo, "Layer": layer})
                
                if textos_encontrados:
                    df_texto = pd.DataFrame(textos_encontrados)
                    st.dataframe(df_texto, use_container_width=True)
                    
                    # Filtro de Busca Inteligente
                    st.markdown("##### 🔎 Mineração de Dados")
                    busca = st.text_input("Buscar palavra-chave (ex: 'Cobre', 'Aço', 'Especificação')")
                    if busca:
                        resultado = df_texto[df_texto['Texto'].str.contains(busca, case=False, na=False)]
                        st.write(f"Encontrei {len(resultado)} ocorrências:")
                        st.dataframe(resultado)
                else:
                    st.warning("Nenhum texto legível encontrado neste desenho.")

            # 3. LEITURA DE LAYERS (DISCIPLINAS)
            with tab_layers:
                st.subheader("Estrutura do Arquivo")
                layers = [layer.dxf.name for layer in doc.layers]
                
                # Análise simples de disciplina
                disciplinas_detectadas = []
                if any("ELE" in l.upper() or "ELÉ" in l.upper() for l in layers): disciplinas_detectadas.append("⚡ Elétrica")
                if any("HID" in l.upper() or "ÁGUA" in l.upper() for l in layers): disciplinas_detectadas.append("💧 Hidráulica")
                if any("AR" in l.upper() or "MEC" in l.upper() or "DUTO" in l.upper() for l in layers): disciplinas_detectadas.append("❄️ Ar Condicionado/Mecânica")
                
                if disciplinas_detectadas:
                    st.success(f"Parece ser um projeto de: {', '.join(disciplinas_detectadas)}")
                
                st.code(layers)

    except Exception as e:
        st.error(f"Erro desconhecido: {e}")
    
    finally:
        if os.path.exists(path_temp):
            os.remove(path_temp)

else:
    # Tela Inicial (Vazia)
    c1, c2, c3 = st.columns(3)
    with c1: st.info("💡 **Dica 1:**\nNo AutoCAD, use 'Salvar Como' > **DXF 2010**.")
    with c2: st.info("💡 **Dica 2:**\nO DXF é lido nativamente pelo sistema, garantindo 100% de precisão nos textos.")
    with c3: st.info("💡 **Dica 3:**\nSe o desenho não aparecer, verifique se está salvo na aba 'Model' e não no 'Layout'.")
