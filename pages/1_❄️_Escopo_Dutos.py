import streamlit as st
from docx import Document
from docx.shared import Pt
from docx.enum.text import WD_ALIGN_PARAGRAPH
import io
import zipfile
from datetime import date, timedelta
import utils_db  # <--- Importamos nosso novo ajudante

# --- CONFIGURAÇÃO ---
st.set_page_config(page_title="Escopo Dutos | SIARCON", page_icon="❄️", layout="wide")

# --- CARREGAR DADOS DO GOOGLE SHEETS ---
if 'opcoes_db' not in st.session_state:
    with st.spinner("Conectando ao banco de dados..."):
        st.session_state['opcoes_db'] = utils_db.carregar_opcoes()

# --- FUNÇÃO DOCX (Mesma lógica de antes) ---
def gerar_docx(dados):
    document = Document()
    try:
        style = document.styles['Normal']
        font = style.font
        font.name = 'Calibri'
        font.size = Pt(11)
    except: pass

    title = document.add_heading('Escopo de fornecimento - Rede de dutos', 0)
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p = document.add_paragraph(f"Data: {date.today().strftime('%d/%m/%Y')} | Rev: {dados['revisao']}")
    p.alignment = WD_ALIGN_PARAGRAPH.RIGHT

    document.add_heading('1. OBJETIVO E RESUMO', level=1)
    table = document.add_table(rows=5, cols=2)
    try: table.style = 'Table Grid'
    except: pass
    
    ref_proj = dados['projetos_ref']
    if dados['nomes_anexos']: ref_proj += " | Anexos: " + ", ".join(dados['nomes_anexos'])

    infos = [("Cliente:", dados['cliente']), ("Local/Obra:", dados['obra']), 
             ("Projetos Ref:", ref_proj), ("Fornecedor:", dados['fornecedor']), 
             ("Responsável:", dados['responsavel'])]
    for i, (k, v) in enumerate(infos):
        row = table.rows[i]
        row.cells[0].text = k
        row.cells[0].paragraphs[0].runs[0].bold = True
        row.cells[1].text = v
    
    document.add_paragraph(f"\nResumo: {dados['resumo_escopo']}")

    document.add_heading('2. TÉCNICO', level=1)
    for item in dados['itens_tecnicos']: document.add_paragraph(item, style='List Bullet')
    if dados['tecnico_livre']: document.add_paragraph(dados['tecnico_livre'], style='List Bullet')

    document.add_heading('3. QUALIDADE', level=1)
    for item in dados['itens_qualidade']: document.add_paragraph(item, style='List Bullet')
    if dados['qualidade_livre']: document.add_paragraph(dados['qualidade_livre'], style='List Bullet')

    document.add_heading('4. MATRIZ RESPONSABILIDADES', level=1)
    table_m = document.add_table(rows=1, cols=3)
    try: table_m.style = 'Table Grid'
    except: pass
    h = table_m.rows[0].cells
    h[0].text = "ITEM"; h[1].text = "SIARCON"; h[2].text = dados['fornecedor'].upper()
    for item, resp in dados['matriz'].items():
        row = table_m.add_row().cells
        row[0].text = item
        if resp == "SIARCON": row[1].text = "X"; row[1].paragraphs[0].alignment = 1
        else: row[2].text = "X"; row[2].paragraphs[0].alignment = 1

    document.add_heading('5. SMS', level=1)
    document.add_paragraph("Documentos Padrão (ASO, Fichas, NR-06...)", style='List Bullet')
    for doc in dados['nrs_selecionadas']: document.add_paragraph(f"- {doc}")

    document.add_heading('6. CRONOGRAMA', level=1)
    document.add_paragraph(f"Início: {dados['data_inicio'].strftime('%d/%m/%Y')} | Integração: {dados['dias_integracao']} dias antes.")
    if dados['data_fim']: document.add_paragraph(f"Término: {dados['data_fim'].strftime('%d/%m/%Y')}")

    if dados['obs_gerais']: document.add_heading('7. OBS', level=1); document.add_paragraph(dados['obs_gerais'])

    document.add_heading('8. COMERCIAL', level=1)
    document.add_paragraph(f"Total: {dados['valor_total']} | Pagamento: {dados['condicao_pgto']}")
    if dados['info_comercial']: document.add_paragraph(dados['info_comercial'])
    
    document.add_paragraph("_"*60)
    document.add_paragraph(f"DE ACORDO: {dados['fornecedor']}")

    buffer = io.BytesIO()
    document.save(buffer)
    buffer.seek(0)
    return buffer

# --- FRONT END ---
st.title("❄️ Escopo de Dutos")

tab1, tab2, tab3, tab4, tab5 = st.tabs(["1. Cadastro", "2. Técnico", "3. Matriz", "4. SMS", "5. Comercial"])

with tab1:
    c1, c2 = st.columns(2)
    with c1:
        cliente = st.text_input("Cliente", "Hitachi")
        obra = st.text_input("Obra", "Guarulhos")
        fornecedor = st.text_input("Fornecedor")
    with c2:
        responsavel = st.text_input("Responsável", "Engenharia")
        revisao = st.text_input("Revisão", "R-00")
        projetos_ref = st.text_input("Projetos Ref.")
    resumo_escopo = st.text_area("Resumo")
    arquivos_anexos = st.file_uploader("Anexos", accept_multiple_files=True)

with tab2:
    # TÉCNICO - COM APRENDIZADO REAL NO GOOGLE SHEETS
    st.subheader("Técnico")
    opcoes_tec = st.session_state['opcoes_db']['tecnico']
    itens_tecnicos = st.multiselect("Selecione:", options=opcoes_tec)
    
    col_add, col_free = st.columns(2)
    with col_add:
        novo_tec = st.text_input("➕ Cadastrar novo item no Google Sheets (Técnico)")
        if st.button("Salvar Item"):
            if novo_tec and novo_tec not in opcoes_tec:
                utils_db.aprender_novo_item("tecnico", novo_tec)
                st.success("Item salvo na nuvem! Recarregue a página (F5) para ver.")
                # Limpa cache para puxar o novo item
                del st.session_state['opcoes_db'] 
    with col_free: tecnico_livre = st.text_area("Texto Livre (Técnico)")
    
    st.divider()
    
    # QUALIDADE
    st.subheader("Qualidade")
    opcoes_qual = st.session_state['opcoes_db']['qualidade']
    itens_qualidade = st.multiselect("Selecione Qualidade:", options=opcoes_qual)
    
    c_q1, c_q2 = st.columns(2)
    with c_q1:
        novo_qual = st.text_input("➕ Cadastrar novo item (Qualidade)")
        if st.button("Salvar Qualidade"):
            if novo_qual:
                utils_db.aprender_novo_item("qualidade", novo_qual)
                st.success("Salvo! Recarregue a página.")
                del st.session_state['opcoes_db']
    with c_q2: qualidade_livre = st.text_input("Texto Livre (Qualidade)")

with tab3:
    if not fornecedor: st.warning("Preencha Fornecedor na aba 1")
    escolhas_matriz = {}
    itens_matriz = ["Materiais dutos", "Difusão", "Consumíveis", "Vedação", "Plataformas", "Escadas", "Ferramental", "Alimentação", "Encargos", "Viagem", "EPIs"]
    for item in itens_matriz:
        c1, c2 = st.columns([3,2])
        c1.write(f"**{item}**")
        escolhas_matriz[item] = c2.radio(f"r_{item}", ["SIARCON", fornecedor.upper() if fornecedor else "CONTRATADA"], horizontal=True, label_visibility="collapsed")
        st.divider()

with tab4:
    opcoes_sms = st.session_state['opcoes_db']['sms']
    nrs = st.multiselect("SMS Adicional:", options=opcoes_sms)
    
    # Adicionar novo SMS
    novo_sms = st.text_input("➕ Novo Doc SMS")
    if st.button("Salvar SMS"):
        if novo_sms:
            utils_db.aprender_novo_item("sms", novo_sms)
            st.success("Salvo!")
            del st.session_state['opcoes_db']

    st.divider()
    d_ini = st.date_input("Início")
    d_int = st.number_input("Dias Integração", 5)
    d_fim = st.date_input("Fim", date.today()+timedelta(days=30))

with tab5:
    valor = st.text_input("Total", "R$ 0,00")
    pgto = st.text_area("Pagamento")
    info = st.text_input("Info Extra")
    obs = st.text_area("Obs")

st.markdown("---")
if st.button("🚀 GERAR CONTRATO & REGISTRAR NO BANCO", type="primary", use_container_width=True):
    if not fornecedor:
        st.error("Faltou o fornecedor!")
    else:
        dados = {
            'cliente': cliente, 'obra': obra, 'fornecedor': fornecedor, 'responsavel': responsavel, 
            'revisao': revisao, 'projetos_ref': projetos_ref, 'resumo_escopo': resumo_escopo,
            'itens_tecnicos': itens_tecnicos, 'tecnico_livre': tecnico_livre,
            'itens_qualidade': itens_qualidade, 'qualidade_livre': qualidade_livre,
            'matriz': escolhas_matriz, 'nrs_selecionadas': nrs,
            'data_inicio': d_ini, 'dias_integracao': d_int, 'data_fim': d_fim,
            'obs_gerais': obs, 'valor_total': valor, 'condicao_pgto': pgto, 'info_comercial': info,
            'nomes_anexos': [f.name for f in arquivos_anexos] if arquivos_anexos else []
        }
        
        # 1. Gera Arquivo
        docx = gerar_docx(dados)
        nome_arq = f"Escopo_{fornecedor}.docx"
        
        # 2. Registra no Google Sheets
        with st.spinner("Salvando histórico..."):
            utils_db.registrar_projeto(dados)
            st.success("✅ Projeto registrado no Banco de Dados!")

        # 3. Download
        if arquivos_anexos:
            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, "w") as zf:
                zf.writestr(nome_arq, docx.getvalue())
                for f in arquivos_anexos: zf.writestr(f.name, f.getvalue())
            st.download_button("📥 Baixar ZIP", zip_buffer.getvalue(), f"Pacote_{fornecedor}.zip", "application/zip")
        else:
            st.download_button("📥 Baixar DOCX", docx.getvalue(), nome_arq, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")
