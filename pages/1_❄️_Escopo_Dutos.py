import streamlit as st
from docx import Document
from docx.shared import Pt
from docx.enum.text import WD_ALIGN_PARAGRAPH
import io
import zipfile
from datetime import date, timedelta
import urllib.parse
import utils_db
import utils_email # <--- Importamos o carteiro de volta

# --- CONFIGURAÇÃO ---
st.set_page_config(page_title="Escopo Dutos | SIARCON", page_icon="❄️", layout="wide")

# --- FUNÇÃO DE CALLBACK (SALVAR E LIMPAR) ---
def adicionar_item_callback(categoria, key_input):
    novo_item = st.session_state.get(key_input, "")
    if novo_item:
        retorno = utils_db.aprender_novo_item(categoria, novo_item)
        if retorno is True:
            st.session_state[key_input] = ""
            if 'opcoes_db' in st.session_state: del st.session_state['opcoes_db']
            st.toast(f"✅ Item '{novo_item}' salvo em {categoria}!", icon="✅")
        elif retorno == "Duplicado":
            st.toast(f"⚠️ O item '{novo_item}' já existe na lista!", icon="⚠️")
        else:
            st.toast("❌ Erro ao conectar com a planilha.", icon="❌")
    else:
        st.toast("⚠️ Digite algo antes de salvar.", icon="✍️")

# --- LÓGICA DE EDIÇÃO ---
dados_edicao = {}
id_linha_edicao = None

if 'modo_edicao' in st.session_state and st.session_state['modo_edicao']:
    st.info("✏️ MODO EDIÇÃO ATIVO: Você está alterando um registro existente.")
    dados_edicao = st.session_state.get('dados_projeto', {})
    id_linha_edicao = dados_edicao.get('_id_linha')
    
    if st.button("❌ Cancelar Edição (Limpar)"):
        st.session_state['modo_edicao'] = False
        st.session_state['dados_projeto'] = {}
        st.rerun()

# --- CARREGAR DADOS ---
if 'opcoes_db' not in st.session_state:
    with st.spinner("Carregando banco de dados..."):
        st.session_state['opcoes_db'] = utils_db.carregar_opcoes()

# --- FUNÇÃO DOCX ---
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
        if resp == "SIARCON": 
            row[1].text = "X"; row[1].paragraphs[0].alignment = 1
        else: 
            row[2].text = "X"; row[2].paragraphs[0].alignment = 1

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

tab1, tab2, tab3, tab4, tab5 = st.tabs(["1. Cadastro", "2. Técnico", "3. Matriz", "4. SMS", "5. Comercial e Status"])

with tab1:
    c1, c2 = st.columns(2)
    with c1:
        val_cli = dados_edicao.get('Cliente', '')
        cliente = st.text_input("Cliente", value=val_cli)
        
        val_obra = dados_edicao.get('Obra', '')
        obra = st.text_input("Obra", value=val_obra)
        
        val_forn = dados_edicao.get('Fornecedor', '')
        if val_forn == "PROPONENTE DE DUTOS": val_forn = "" 
        
        fornecedor_input = st.text_input("Fornecedor", value=val_forn, placeholder="Deixe em branco p/ genérico")
        
        if not fornecedor_input:
            fornecedor_final = "PROPONENTE DE DUTOS"
        else:
            fornecedor_final = fornecedor_input
            
    with c2:
        val_resp = dados_edicao.get('Responsável', 'Engenharia')
        responsavel = st.text_input("Responsável", value=val_resp)
        
        revisao = st.text_input("Revisão", "R-00")
        projetos_ref = st.text_input("Projetos Ref.")
        
        email_suprimentos = st.text_input("📧 E-mail de Suprimentos/Obras:", value="suprimentos@siarcon.com.br")

    resumo_escopo = st.text_area("Resumo")
    arquivos_anexos = st.file_uploader("Anexos", accept_multiple_files=True)

with tab2:
    st.subheader("Técnico")
    opcoes_tec = st.session_state['opcoes_db'].get('tecnico', [])
    itens_tecnicos = st.multiselect("Selecione:", options=opcoes_tec)
    
    col_add, col_free = st.columns(2)
    with col_add:
        st.text_input("➕ Cadastrar novo item (Técnico)", key="input_novo_tec")
        st.button("Salvar Item Técnico", on_click=adicionar_item_callback, args=("tecnico", "input_novo_tec"))
                
    with col_free: tecnico_livre = st.text_area("Texto Livre (Técnico)")
    
    st.divider()
    
    st.subheader("Qualidade")
    opcoes_qual = st.session_state['opcoes_db'].get('qualidade', [])
    itens_qualidade = st.multiselect("Selecione Qualidade:", options=opcoes_qual)
    
    c_q1, c_q2 = st.columns(2)
    with c_q1:
        st.text_input("➕ Cadastrar novo item (Qualidade)", key="input_novo_qual")
        st.button("Salvar Qualidade", on_click=adicionar_item_callback, args=("qualidade", "input_novo_qual"))

    with c_q2: qualidade_livre = st.text_input("Texto Livre (Qualidade)")

with tab3:
    escolhas_matriz = {}
    itens_matriz = ["Materiais dutos", "Difusão", "Consumíveis", "Vedação", "Plataformas", "Escadas", "Ferramental", "Alimentação", "Encargos", "Viagem", "EPIs"]
    
    nome_na_matriz = fornecedor_final.upper() if fornecedor_final else "PROPONENTE"
    st.info(f"Matriz de responsabilidades para: **{nome_na_matriz}**")
    
    for item in itens_matriz:
        c1, c2 = st.columns([3,2])
        c1.write(f"**{item}**")
        escolhas_matriz[item] = c2.radio(f"r_{item}", ["SIARCON", nome_na_matriz], horizontal=True, label_visibility="collapsed")
        st.divider()

with tab4:
    opcoes_sms = st.session_state['opcoes_db'].get('sms', [])
    nrs = st.multiselect("SMS Adicional:", options=opcoes_sms)
    
    st.text_input("➕ Novo Doc SMS", key="input_novo_sms")
    st.button("Salvar SMS", on_click=adicionar_item_callback, args=("sms", "input_novo_sms"))

    st.divider()
    d_ini = st.date_input("Início")
    d_int = st.number_input("Dias Integração", 5)
    d_fim = st.date_input("Fim", date.today()+timedelta(days=30))

with tab5:
    st.subheader("Informações Comerciais")
    val_total = dados_edicao.get('Valor', 'R$ 0,00')
    valor = st.text_input("Total", value=val_total)
    
    pgto = st.text_area("Pagamento")
    info = st.text_input("Info Extra")
    obs = st.text_area("Obs")

    st.divider()
    
    st.subheader("🚦 Workflow (Status do Projeto)")
    
    status_atual = dados_edicao.get('Status', 'Em Elaboração (Engenharia)')
    
    lista_status = [
        "Em Elaboração (Engenharia)",
        "Aguardando Obras",
        "Recebido (Suprimentos)",
        "Enviado para Cotação",
        "Em Negociação",
        "Contratação Finalizada"
    ]
    
    try: idx_status = lista_status.index(status_atual)
    except: idx_status = 0
    
    novo_status = st.selectbox("Fase Atual:", lista_status, index=idx_status)
    
    if novo_status == "Contratação Finalizada":
        st.warning("⚠️ Ao finalizar, você deve obrigatoriamente informar o nome da empresa vencedora na aba 1.")

st.markdown("---")

# --- LÓGICA DE SALVAMENTO ---
if status_atual == "Contratação Finalizada" and 'modo_edicao' in st.session_state:
    st.error("🔒 CONTRATAÇÃO FINALIZADA. Edição bloqueada.")
    st.download_button("📥 Baixar Contrato Final", gerar_docx(dados_edicao).getvalue(), f"Escopo_{val_forn}.docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document")

else:
    label_botao = "💾 ATUALIZAR PROJETO" if id_linha_edicao else "🚀 REGISTRAR"

    if st.button(label_botao, type="primary", use_container_width=True):
        
        erro_validacao = False
        if novo_status == "Contratação Finalizada":
            if fornecedor_final == "PROPONENTE DE DUTOS" or not fornecedor_final.strip():
                st.error("⛔ ERRO: Para marcar como 'Contratação Finalizada', você DEVE preencher o nome da empresa na Aba 1.")
                st.toast("Preencha o nome do fornecedor!", icon="⛔")
                erro_validacao = True
        
        if not erro_validacao:
            dados = {
                'cliente': cliente, 'obra': obra, 
                'fornecedor': fornecedor_final,
                'responsavel': responsavel, 
                'revisao': revisao, 'projetos_ref': projetos_ref, 'resumo_escopo': resumo_escopo,
                'itens_tecnicos': itens_tecnicos, 'tecnico_livre': tecnico_livre,
                'itens_qualidade': itens_qualidade, 'qualidade_livre': qualidade_livre,
                'matriz': escolhas_matriz, 'nrs_selecionadas': nrs,
                'data_inicio': d_ini, 'dias_integracao': d_int, 'data_fim': d_fim,
                'obs_gerais': obs, 'valor_total': valor, 'condicao_pgto': pgto, 'info_comercial': info,
                'status': novo_status,
                'nomes_anexos': [f.name for f in arquivos_anexos] if arquivos_anexos else []
            }
            
            docx_buffer = gerar_docx(dados)
            nome_arq_limpo = fornecedor_final.replace(" ", "_")
            nome_arq = f"Escopo_{nome_arq_limpo}.docx"
            docx_buffer.seek(0)
            
            with st.spinner("Salvando..."):
                utils_db.registrar_projeto(dados, id_linha=id_linha_edicao)
                st.success(f"✅ Projeto Atualizado! Fase: {novo_status}")

            st.divider()
            
            c1, c2, c3 = st.columns([1, 1.5, 1.5])
            
            with c1:
                st.info("Arquivo:")
                st.download_button("📥 Baixar DOCX", docx_buffer.getvalue(), nome_arq, "application/vnd.openxmlformats-officedocument.wordprocessingml.document", use_container_width=True)
            
            # --- TENTATIVA AUTOMÁTICA ---
            with c2:
                st.info("Opção A (Automático):")
                if st.button("🤖 Enviar via Sistema", use_container_width=True):
                    with st.spinner("O robô está tentando enviar..."):
                        
                        corpo_auto = f"""Olá,
                        
Segue documento atualizado do projeto {obra}.
Status: {novo_status}
Fornecedor: {fornecedor_final}

Att, Portal SIARCON"""

                        res = utils_email.enviar_email_com_anexo(
                            destinatario=email_suprimentos,
                            assunto=f"Status {novo_status}: {obra}",
                            corpo=corpo_auto,
                            arquivo_bytes=docx_buffer.getvalue(),
                            nome_arquivo=nome_arq
                        )
                        
                        if res is True:
                            st.balloons()
                            st.success("✅ E-mail enviado com sucesso pelo sistema!")
                        else:
                            st.error(f"⚠️ O envio automático falhou (O Google bloqueou). Use a Opção B ao lado.")
                            st.code(res)

            # --- OPÇÃO MANUAL (BACKUP) ---
            with c3:
                st.info("Opção B (Manual):")
                assunto_cot = f"Atualização: {obra} - {novo_status}"
                corpo_cot = f"Olá,\n\nSegue documento atualizado.\nObra: {obra}\nStatus: {novo_status}"
                link_cot = f"mailto:{email_suprimentos}?subject={urllib.parse.quote(assunto_cot)}&body={urllib.parse.quote(corpo_cot)}"
                
                st.markdown(f"""
                <a href="{link_cot}" target="_blank">
                    <button style="width:100%; background-color:#FF4B4B; color:white; border:none; padding:10px; border-radius:5px; font-weight:bold; cursor:pointer;">
                    📧 Abrir Outlook/Gmail
                    </button>
                </a>
                """, unsafe_allow_html=True)
