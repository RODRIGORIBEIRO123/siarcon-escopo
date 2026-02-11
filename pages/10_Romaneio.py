import streamlit as st
import pandas as pd
from docx import Document
from docx.shared import Pt, Inches, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import nsdecls
from docx.oxml import parse_xml
import io
import json
from datetime import datetime, date
import utils_db

# --- 🔒 SEGURANÇA ---
if 'logado' not in st.session_state or not st.session_state['logado']:
    st.warning("🔒 Acesso negado. Faça login.")
    st.stop()

st.set_page_config(page_title="Romaneio de Materiais", page_icon="📦", layout="wide")

# ============================================================================
# FUNÇÕES DE DOCUMENTO (DOCX)
# ============================================================================
def set_cell_background(cell, color_hex):
    """Função auxiliar para pintar fundo de célula no Word"""
    shading_elm = parse_xml(r'<w:shd {} w:fill="{}"/>'.format(nsdecls('w'), color_hex))
    cell._tc.get_or_add_tcPr().append(shading_elm)

def gerar_romaneio_docx(dados, df_materiais):
    doc = Document()
    
    # Ajuste de Margens (Estreitas para caber tabela)
    section = doc.sections[0]
    section.left_margin = Inches(0.5)
    section.right_margin = Inches(0.5)
    section.top_margin = Inches(0.5)
    section.bottom_margin = Inches(0.5)

    style = doc.styles['Normal']
    style.font.name = 'Calibri'
    style.font.size = Pt(10)

    # --- CABEÇALHO (Simulando a imagem) ---
    # Tabela de layout do cabeçalho
    table_head = doc.add_table(rows=1, cols=3)
    table_head.style = 'Table Grid'
    
    # Célula 1: Logo (Texto SIARCON por enquanto)
    c0 = table_head.cell(0, 0)
    p0 = c0.paragraphs[0]
    p0.add_run("SIARCON").bold = True
    p0.alignment = WD_ALIGN_PARAGRAPH.CENTER
    
    # Célula 2: Título Central
    c1 = table_head.cell(0, 1)
    p1 = c1.paragraphs[0]
    run_title = p1.add_run("ROMANEIO DE ENVIO DE MATERIAIS")
    run_title.bold = True
    run_title.font.size = Pt(12)
    p1.alignment = WD_ALIGN_PARAGRAPH.CENTER
    
    # Célula 3: Data
    c2 = table_head.cell(0, 2)
    p2 = c2.paragraphs[0]
    p2.add_run(f"DATA: {dados['data']}").bold = True
    p2.alignment = WD_ALIGN_PARAGRAPH.CENTER

    # --- SUB-CABEÇALHO (Cinza) ---
    # Tabela de dados da empresa/obra
    t_sub = doc.add_table(rows=2, cols=1)
    t_sub.style = 'Table Grid'
    
    # Linha 1: Empresa
    row0 = t_sub.rows[0]
    row0.cells[0].text = "Empresa: SIARCON ENGENHARIA LTDA - EPP"
    set_cell_background(row0.cells[0], "D9D9D9") # Cinza claro
    row0.cells[0].paragraphs[0].runs[0].bold = True
    
    # Linha 2: Obra
    row1 = t_sub.rows[1]
    row1.cells[0].text = f"Obra: {dados['obra'].upper()}"
    set_cell_background(row1.cells[0], "D9D9D9")
    row1.cells[0].paragraphs[0].runs[0].bold = True

    doc.add_paragraph("") # Espaço

    # --- TABELA DE MATERIAIS ---
    # Colunas: Material, Unidade, Quantidade
    t_mat = doc.add_table(rows=1, cols=3)
    t_mat.style = 'Table Grid'
    
    # Cabeçalho da Tabela
    hdr = t_mat.rows[0].cells
    headers = ["MATERIAL", "Unidade", "Quantidade"]
    for i, text in enumerate(headers):
        hdr[i].text = text
        hdr[i].paragraphs[0].runs[0].bold = True
        hdr[i].paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER
        set_cell_background(hdr[i], "D9D9D9") # Fundo Cinza

    # Dados da Tabela
    for index, row in df_materiais.iterrows():
        # Só adiciona se tiver descrição
        if str(row['MATERIAL']).strip():
            cells = t_mat.add_row().cells
            cells[0].text = str(row['MATERIAL'])
            cells[1].text = str(row['Unidade'])
            cells[1].paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER
            
            # Formata quantidade (remove decimais se for zero)
            qtd = row['Quantidade']
            try:
                if float(qtd).is_integer(): qtd = int(qtd)
            except: pass
            cells[2].text = str(qtd)
            cells[2].paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER

    # Linhas em branco para completar a página (opcional, como no romaneio físico)
    for _ in range(10):
        t_mat.add_row()

    doc.add_paragraph("")
    doc.add_paragraph("")
    doc.add_paragraph("")

    # --- RODAPÉ (ASSINATURAS) ---
    # Tabela invisível para alinhar assinaturas
    t_footer = doc.add_table(rows=2, cols=2)
    
    # Linha "Vistos:"
    c_vistos = t_footer.cell(0, 0)
    c_vistos.merge(t_footer.cell(0, 1))
    c_vistos.text = "Vistos:"
    c_vistos.paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER
    
    # Assinaturas
    r_sig = t_footer.rows[1]
    
    # Esquerda (Siarcon)
    c_siarcon = r_sig.cells[0]
    p_s = c_siarcon.paragraphs[0]
    p_s.add_run("_______________________________\n").bold = True
    p_s.add_run(f"{dados['responsavel_envio']}\n")
    p_s.add_run("Siarcon Engenharia Ltda - EPP")
    p_s.alignment = WD_ALIGN_PARAGRAPH.CENTER
    
    # Direita (Recebimento)
    c_cliente = r_sig.cells[1]
    p_c = c_cliente.paragraphs[0]
    p_c.add_run("_______________________________\n").bold = True
    p_c.add_run(f"Responsável pelo recebimento: {dados['responsavel_recebimento']}")
    p_c.alignment = WD_ALIGN_PARAGRAPH.CENTER

    b = io.BytesIO()
    doc.save(b)
    b.seek(0)
    return b

# ============================================================================
# INTERFACE
# ============================================================================
st.title("📦 Romaneio de Materiais")
st.markdown("---")

# 1. CABEÇALHO
c1, c2 = st.columns([3, 1])
obra = c1.text_input("Nome da Obra (Cliente)", value="EUROFARMA")
data_atual = date.today().strftime("%d/%m/%Y")
data_doc = c2.text_input("Data", value=data_atual)

st.write("### 📋 Lista de Materiais")

# 2. EDITOR DE DADOS (TABELA EDITÁVEL)
# Cria um dataframe inicial vazio com algumas linhas
if 'df_romaneio' not in st.session_state:
    st.session_state['df_romaneio'] = pd.DataFrame(
        [{"MATERIAL": "", "Unidade": "PC", "Quantidade": 0} for _ in range(5)]
    )

config_colunas = {
    "MATERIAL": st.column_config.TextColumn("Descrição do Material", width="large", required=True),
    "Unidade": st.column_config.SelectboxColumn("Unid.", options=["PC", "KG", "M", "CX", "PAR", "BR", "RL"], width="small", required=True),
    "Quantidade": st.column_config.NumberColumn("Qtd.", min_value=0, step=1, width="small", required=True)
}

df_editado = st.data_editor(
    st.session_state['df_romaneio'],
    column_config=config_colunas,
    num_rows="dynamic", # Permite adicionar linhas
    use_container_width=True,
    hide_index=True
)

st.markdown("---")

# 3. RODAPÉ
c3, c4 = st.columns(2)
resp_envio = c3.text_input("Responsável pelo Envio (Siarcon)", value="João Bigoni")
resp_receb = c4.text_input("Responsável pelo Recebimento (Cliente)", value="Global")

# 4. AÇÃO
col_btn1, col_btn2 = st.columns(2)

# Preparar dados para salvar
dados_romaneio = {
    'data': data_doc,
    'obra': obra,
    'responsavel_envio': resp_envio,
    'responsavel_recebimento': resp_receb,
    'materiais_json': df_editado.to_json(orient="records") # Salva tabela como texto
}

if col_btn1.button("💾 Salvar Romaneio"):
    if utils_db.registrar_romaneio(dados_romaneio):
        st.success("Romaneio salvo no banco de dados!")
    else:
        st.error("Erro ao salvar. Verifique o utils_db.py")

if col_btn2.button("📄 Gerar DOCX para Impressão", type="primary"):
    # Filtra linhas vazias antes de imprimir
    df_final = df_editado[df_editado["MATERIAL"].str.strip() != ""]
    
    if not df_final.empty:
        arquivo_docx = gerar_romaneio_docx(dados_romaneio, df_final)
        
        nome_arq = f"Romaneio - {obra} - {datetime.now().strftime('%d-%m-%Y')}.docx"
        st.download_button(
            label="📥 Baixar Romaneio (.docx)",
            data=arquivo_docx,
            file_name=nome_arq,
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        )
    else:
        st.warning("Preencha pelo menos um material para gerar o documento.")
