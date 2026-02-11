import streamlit as st
import pandas as pd
from docx import Document
from docx.shared import Pt, Inches
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import nsdecls
from docx.oxml import parse_xml
import io
import time
from datetime import datetime, date
import utils_db

# --- 🔒 SEGURANÇA ---
if 'logado' not in st.session_state or not st.session_state['logado']:
    st.warning("🔒 Acesso negado. Faça login.")
    st.stop()

st.set_page_config(page_title="Romaneio de Materiais", page_icon="📦", layout="wide")

# Carrega opções do banco
if 'opcoes_db' not in st.session_state: 
    st.session_state['opcoes_db'] = utils_db.carregar_opcoes()

# ============================================================================
# FUNÇÕES DE DOCUMENTO (DOCX)
# ============================================================================
def set_cell_background(cell, color_hex):
    shading_elm = parse_xml(r'<w:shd {} w:fill="{}"/>'.format(nsdecls('w'), color_hex))
    cell._tc.get_or_add_tcPr().append(shading_elm)

def gerar_romaneio_docx(dados, df_materiais):
    doc = Document()
    
    section = doc.sections[0]
    section.left_margin = Inches(0.5); section.right_margin = Inches(0.5)
    section.top_margin = Inches(0.5); section.bottom_margin = Inches(0.5)
    
    style = doc.styles['Normal']
    style.font.name = 'Calibri'; style.font.size = Pt(10)

    # CABEÇALHO
    table_head = doc.add_table(rows=1, cols=3); table_head.style = 'Table Grid'
    
    c0 = table_head.cell(0, 0); p0 = c0.paragraphs[0]
    p0.add_run("SIARCON").bold = True; p0.alignment = WD_ALIGN_PARAGRAPH.CENTER
    
    c1 = table_head.cell(0, 1); p1 = c1.paragraphs[0]
    run_title = p1.add_run("ROMANEIO DE ENVIO DE MATERIAIS")
    run_title.bold = True; run_title.font.size = Pt(12)
    p1.alignment = WD_ALIGN_PARAGRAPH.CENTER
    
    c2 = table_head.cell(0, 2); p2 = c2.paragraphs[0]
    p2.add_run(f"DATA: {dados['data']}").bold = True; p2.alignment = WD_ALIGN_PARAGRAPH.CENTER

    # DADOS EMPRESA
    t_sub = doc.add_table(rows=2, cols=1); t_sub.style = 'Table Grid'
    
    row0 = t_sub.rows[0]; row0.cells[0].text = "Empresa: SIARCON ENGENHARIA LTDA - EPP"
    set_cell_background(row0.cells[0], "D9D9D9"); row0.cells[0].paragraphs[0].runs[0].bold = True
    
    row1 = t_sub.rows[1]; row1.cells[0].text = f"Obra: {dados['obra'].upper()}"
    set_cell_background(row1.cells[0], "D9D9D9"); row1.cells[0].paragraphs[0].runs[0].bold = True

    doc.add_paragraph("") 

    # TABELA DE MATERIAIS
    t_mat = doc.add_table(rows=1, cols=4); t_mat.style = 'Table Grid'
    t_mat.autofit = False
    t_mat.columns[0].width = Inches(3.0) 
    t_mat.columns[1].width = Inches(2.7) 
    t_mat.columns[2].width = Inches(0.8) 
    t_mat.columns[3].width = Inches(1.0) 
    
    hdr = t_mat.rows[0].cells
    headers = ["DESCRIÇÃO DO MATERIAL", "DETALHE", "UNID.", "QTD."]
    for i, text in enumerate(headers):
        hdr[i].text = text
        hdr[i].paragraphs[0].runs[0].bold = True
        hdr[i].paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER
        set_cell_background(hdr[i], "D9D9D9")

    for index, row in df_materiais.iterrows():
        desc = str(row.get('MATERIAL', '')).strip()
        if desc:
            cells = t_mat.add_row().cells
            cells[0].text = desc
            cells[1].text = str(row.get('DETALHE', ''))
            cells[2].text = str(row.get('UNID', '')); cells[2].paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER
            
            qtd = row.get('QTD', 0)
            try: 
                if float(qtd).is_integer(): qtd = int(qtd)
            except: pass
            cells[3].text = str(qtd); cells[3].paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER

    for _ in range(max(0, 15 - len(df_materiais))): t_mat.add_row()

    doc.add_paragraph(""); doc.add_paragraph("")

    # RODAPÉ
    t_footer = doc.add_table(rows=2, cols=2); t_footer.autofit = True
    c_vistos = t_footer.cell(0, 0); c_vistos.merge(t_footer.cell(0, 1))
    c_vistos.text = "Vistos:"; c_vistos.paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER
    
    r_sig = t_footer.rows[1]
    p_s = r_sig.cells[0].paragraphs[0]
    p_s.add_run("_______________________________\n").bold = True
    p_s.add_run(f"{dados['responsavel_envio']}\n"); p_s.add_run("Siarcon Engenharia Ltda - EPP")
    p_s.alignment = WD_ALIGN_PARAGRAPH.CENTER
    
    p_c = r_sig.cells[1].paragraphs[0]
    p_c.add_run("_______________________________\n").bold = True
    p_c.add_run(f"Responsável: {dados['responsavel_recebimento']}\n"); p_c.add_run("Recebimento na Obra")
    p_c.alignment = WD_ALIGN_PARAGRAPH.CENTER

    b = io.BytesIO(); doc.save(b); b.seek(0); return b

# ============================================================================
# INTERFACE
# ============================================================================
st.title("📦 Romaneio de Materiais")

# 1. DADOS
c1, c2 = st.columns([3, 1])
obra = c1.text_input("Nome da Obra (Cliente)", value="EUROFARMA")
data_atual = date.today().strftime("%d/%m/%Y")
data_doc = c2.text_input("Data", value=data_atual)

st.write("### 📋 Lista de Materiais")

# Recupera lista de materiais do banco
opcoes_materiais = sorted(st.session_state['opcoes_db'].get('materiais_romaneio', []))

# --- LÓGICA DE CORREÇÃO DO DATAFRAME (ANTI-ERRO KEYERROR) ---
cols_esperadas = ["MATERIAL", "DETALHE", "UNID", "QTD"]

if 'df_romaneio' not in st.session_state:
    # Cria novo do zero
    st.session_state['df_romaneio'] = pd.DataFrame(
        [{"MATERIAL": "", "DETALHE": "", "UNID": "PC", "QTD": 0} for _ in range(5)]
    )
else:
    # Se já existe (memória antiga), verifica se tem todas as colunas
    df_atual = st.session_state['df_romaneio']
    
    # Adiciona colunas que faltam (ex: DETALHE que não tinha antes)
    for col in cols_esperadas:
        if col not in df_atual.columns:
            df_atual[col] = "" if col != "QTD" else 0
            
    # Reordena e salva de volta
    st.session_state['df_romaneio'] = df_atual[cols_esperadas]

# Configuração das Colunas
config_colunas = {
    "MATERIAL": st.column_config.SelectboxColumn("Descrição do Material (Banco)", options=opcoes_materiais, width="large", required=True),
    "DETALHE": st.column_config.TextColumn("Detalhe / Complemento", width="medium"),
    "UNID": st.column_config.SelectboxColumn("Unid.", options=["PC", "KG", "M", "CX", "PAR", "BR", "RL", "CJ", "UN"], width="small", required=True),
    "QTD": st.column_config.NumberColumn("Qtd.", min_value=0, step=1, format="%d", width="small", required=True)
}

df_editado = st.data_editor(
    st.session_state['df_romaneio'],
    column_config=config_colunas,
    num_rows="dynamic",
    use_container_width=True,
    hide_index=True
)

# 4. CADASTRO DE NOVO MATERIAL (ABAIXO DA LISTA)
st.markdown("---")
with st.expander("➕ Não encontrou o material na lista acima? Cadastre aqui no Banco de Dados"):
    c_new1, c_new2 = st.columns([4, 1])
    novo_material = c_new1.text_input("Nome do Novo Material (Ex: Chapa Galvanizada #26)")
    if c_new2.button("💾 Cadastrar"):
        if novo_material:
            if utils_db.aprender_novo_item("materiais_romaneio", novo_material):
                st.session_state['opcoes_db'] = utils_db.carregar_opcoes() 
                st.success(f"'{novo_material}' cadastrado! Ele aparecerá na lista acima.")
                time.sleep(1)
                st.rerun()
            else: st.error("Erro ao salvar no banco.")
        else: st.warning("Digite o nome do material.")

st.markdown("---")

# 5. RODAPÉ E AÇÕES
c3, c4 = st.columns(2)
resp_envio = c3.text_input("Responsável pelo Envio (Siarcon)", value="João Bigoni")
resp_receb = c4.text_input("Responsável pelo Recebimento (Cliente)", value="Global")

col_btn1, col_btn2 = st.columns(2)

dados_romaneio = {
    'data': data_doc, 'obra': obra,
    'responsavel_envio': resp_envio, 'responsavel_recebimento': resp_receb,
    'materiais_json': df_editado.to_json(orient="records")
}

if col_btn1.button("💾 Salvar Romaneio"):
    if utils_db.registrar_romaneio(dados_romaneio): st.success("Romaneio salvo no banco de dados!")
    else: st.error("Erro ao salvar.")

if col_btn2.button("📄 Gerar DOCX para Impressão", type="primary"):
    df_final = df_editado[df_editado["MATERIAL"].astype(str).str.strip() != ""]
    if not df_final.empty:
        arquivo_docx = gerar_romaneio_docx(dados_romaneio, df_final)
        nome_arq = f"Romaneio - {obra} - {datetime.now().strftime('%d-%m-%Y')}.docx"
        st.download_button(label="📥 Baixar Romaneio (.docx)", data=arquivo_docx, file_name=nome_arq, mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document")
    else: st.warning("Preencha pelo menos um material.")
