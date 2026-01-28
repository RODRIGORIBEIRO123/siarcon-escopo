import streamlit as st
from docx import Document
from docx.shared import Pt
import io
from datetime import date
import utils_db

# --- CONFIGURAÇÃO: ELÉTRICA ---
DISCIPLINA_ATUAL = "Elétrica"
ITENS_MATRIZ = [
    "Cabos e Fios", "Eletrocalhas e Perfilados", "Quadros e Painéis",
    "Disjuntores e Componentes", "Infraestrutura seca", "Mão de Obra Montagem",
    "Testes e Laudos", "As-Built", "ART/RRT"
]
# ... COLE O BLOCO PRINCIPAL AQUI ABAIXO ...# --- INÍCIO DO CÓDIGO COMUM ---
st.set_page_config(page_title=f"Escopo {DISCIPLINA_ATUAL}", page_icon="📝", layout="wide")

# --- CARGA DE DADOS ---
if 'opcoes_db' not in st.session_state or st.sidebar.button("🔄 Forçar Recarga"):
    with st.spinner("Lendo banco de dados..."):
        st.cache_data.clear()
        st.session_state['opcoes_db'] = utils_db.carregar_opcoes()

# --- DEFINE AS CHAVES DE CATEGORIA PARA O BANCO ---
cat_tecnica_db = f"tecnico_{DISCIPLINA_ATUAL.lower()}"
cat_qualidade_db = f"qualidade_{DISCIPLINA_ATUAL.lower()}"

def formatar_moeda(valor):
    try:
        v = float(str(valor).replace('R$', '').replace('.', '').replace(',', '.').strip())
        return f"R$ {v:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
    except: return valor

def gerar_docx(dados):
    doc = Document()
    try: style = doc.styles['Normal']; style.font.name = 'Calibri'; style.font.size = Pt(11)
    except: pass
    
    doc.add_heading(f'Escopo - {dados["disciplina"]}', 0)
    doc.add_paragraph(f"Data: {date.today().strftime('%d/%m/%Y')} | Rev: {dados.get('revisao','-')}")
    
    doc.add_heading('1. DADOS GERAIS', 1)
    t = doc.add_table(rows=1, cols=2)
    try: t.style = 'Table Grid'
    except: pass
    infos = [("Cliente", dados['cliente']), ("Obra", dados['obra']), ("Fornecedor", dados['fornecedor']),
             ("Engenharia", dados['responsavel']), ("Suprimentos", dados['resp_suprimentos'])]
    for k, v in infos:
        row = t.add_row().cells; row[0].text = k; row[0].paragraphs[0].runs[0].bold = True; row[1].text = str(v)

    doc.add_heading('2. ESCOPO TÉCNICO', 1)
    doc.add_paragraph(f"Resumo: {dados.get('resumo_escopo','')}")
    if dados.get('tecnico_livre'): 
        doc.add_paragraph("Obs Técnicas:", style='List Bullet')
        doc.add_paragraph(dados['tecnico_livre'])
    for item in dados.get('itens_tecnicos', []): doc.add_paragraph(item, style='List Bullet')

    doc.add_heading('3. QUALIDADE', 1)
    for item in dados.get('itens_qualidade', []): doc.add_paragraph(item, style='List Bullet')

    doc.add_heading('4. MATRIZ DE RESPONSABILIDADE', 1)
    tm = doc.add_table(rows=1, cols=3)
    try: tm.style = 'Table Grid'
    except: pass
    h = tm.rows[0].cells; h[0].text = "ITEM"; h[1].text = "SIARCON"; h[2].text = "FORNECEDOR"
    for i, r in dados.get('matriz', {}).items():
        row = tm.add_row().cells; row[0].text = i
        if r == "SIARCON": row[1].text = "X"
        else: row[2].text = "X"

    doc.add_heading('5. SMS E SEGURANÇA', 1)
    if dados.get('sms_livre'):
        doc.add_paragraph("Obs Segurança:", style='List Bullet')
        doc.add_paragraph(dados['sms_livre'])
    for nr in dados.get('nrs_selecionadas', []): doc.add_paragraph(nr, style='List Bullet')

    doc.add_heading('6. COMERCIAL', 1)
    doc.add_paragraph(f"Valor: {formatar_moeda(dados.get('valor_total',''))}")
    doc.add_paragraph(f"Pagamento: {dados.get('condicao_pgto','')}")
    if dados.get('obs_gerais'): doc.add_paragraph(f"Obs: {dados['obs_gerais']}")

    b = io.BytesIO(); doc.save(b); b.seek(0); return b

# --- INTERFACE ---
st.title(f"🛠️ {DISCIPLINA_ATUAL}")
opcoes = st.session_state.get('opcoes_db', {})

tab1, tab2, tab3, tab4, tab5 = st.tabs(["Cadastro", "Técnico", "Matriz", "SMS", "Comercial"])

with tab1:
    st.warning("⚠️ Suprimentos: Preencher campos do fornecedor.")
    
    # --- SELEÇÃO DE CLIENTE E OBRA ---
    c1, c2 = st.columns(2)
    cliente = c1.text_input("Cliente")
    obra = c1.text_input("Obra")
    
    # --- SELEÇÃO DE FORNECEDOR EXISTENTE ---
    db_forn = utils_db.listar_fornecedores()
    lista_nomes = [""] + [f['Fornecedor'] for f in db_forn]
    
    sel_forn = c1.selectbox("Selecionar Fornecedor (Banco de Dados):", lista_nomes)
    
    # Preenche automático se selecionou alguém
    cnpj_auto = ""
    if sel_forn:
        found = next((f for f in db_forn if f['Fornecedor'] == sel_forn), None)
        if found: cnpj_auto = str(found['CNPJ'])

    # Campos editáveis (caso queira ajustar algo manualmente)
    forn = c1.text_input("Razão Social (Preenchimento Automático):", value=sel_forn)
    cnpj = c1.text_input("CNPJ (Preenchimento Automático):", value=cnpj_auto)
    
    resp_eng = c2.text_input("Engenharia")
    resp_sup = c2.text_input("Suprimentos")
    revisao = c2.text_input("Revisão", "R-00")
    resumo = c2.text_area("Resumo Escopo")

    # --- CAMPO NOVO: CADASTRAR FORNECEDOR (O QUE FALTOU) ---
    st.markdown("---")
    with st.expander("➕ Não achou? Cadastre um NOVO Fornecedor aqui"):
        st.info("Isso salvará o fornecedor na aba 'FORNECEDORES' da planilha.")
        cc1, cc2, cc3 = st.columns([2, 1, 1])
        
        # Keys dinâmicas para não dar conflito entre páginas
        novo_nome_f = cc1.text_input("Nome do Novo Fornecedor", key=f"new_f_name_{DISCIPLINA_ATUAL}")
        novo_cnpj_f = cc2.text_input("CNPJ", key=f"new_f_cnpj_{DISCIPLINA_ATUAL}")
        
        # Espaçamento para alinhar o botão
        cc3.write("")
        cc3.write("")
        if cc3.button("💾 Cadastrar", key=f"btn_save_f_{DISCIPLINA_ATUAL}"):
            if novo_nome_f:
                if utils_db.cadastrar_fornecedor_db(novo_nome_f, novo_cnpj_f):
                    st.success(f"✅ {novo_nome_f} cadastrado com sucesso!")
                    st.cache_data.clear() # Limpa memória para ele aparecer na lista na hora
                    st.rerun() # Recarrega a página
                else:
                    st.error("Erro ao salvar na planilha.")
            else:
                st.warning("Digite pelo menos o nome.")

with tab2:
    st.subheader("Itens Técnicos")
    # Busca apenas os itens desta disciplina específica
    lista_tec = opcoes.get(cat_tecnica_db, [])
    # Se for Dutos, por compatibilidade com banco antigo, soma com 'tecnico' genérico
    if DISCIPLINA_ATUAL == "Dutos": lista_tec = list(set(lista_tec + opcoes.get('tecnico', [])))
    
    k_tec = f"tec_{DISCIPLINA_ATUAL.lower()}"
    itens_tec = st.multiselect("Selecione Itens:", sorted(lista_tec), key=k_tec)
    
    c_add, c_txt = st.columns(2)
    novo_tec = c_add.text_input("Novo Item Técnico (DB):", key=f"new_{k_tec}")
    if c_add.button("💾 Adicionar", key=f"btn_{k_tec}"):
        if utils_db.aprender_novo_item(cat_tecnica_db, novo_tec):
            st.toast("Salvo!"); st.rerun()
            
    tec_livre = st.text_area("📝 Texto Livre (Técnico):", height=150)
    
    st.divider()
    st.subheader("Controle de Qualidade")
    lista_qual = opcoes.get(cat_qualidade_db, [])
    if DISCIPLINA_ATUAL == "Dutos": lista_qual = list(set(lista_qual + opcoes.get('qualidade', [])))

    k_qual = f"qual_{DISCIPLINA_ATUAL.lower()}"
    itens_qual = st.multiselect("Selecione Itens:", sorted(lista_qual), key=k_qual)
    
    c_add_q, c_vz = st.columns(2)
    novo_qual = c_add_q.text_input("Novo Item Qualidade (DB):", key=f"new_q_{k_qual}")
    if c_add_q.button("💾 Adicionar Qualidade", key=f"btn_q_{k_qual}"):
        if utils_db.aprender_novo_item(cat_qualidade_db, novo_qual):
             st.toast("Salvo!"); st.rerun()

with tab3:
    escolhas = {}
    nome_f = forn.split(' ')[0].upper() if forn else "FORN"
    for item in ITENS_MATRIZ:
        c_m1, c_m2 = st.columns([2,1])
        c_m1.write(f"**{item}**")
        escolhas[item] = c_m2.radio(item, ["SIARCON", nome_f], horizontal=True, label_visibility="collapsed", key=f"mtz_{item}")
        st.divider()

with tab4:
    st.subheader("SMS")
    nrs = st.multiselect("NRs Aplicáveis:", opcoes.get('sms', []), key=f"sms_{DISCIPLINA_ATUAL}")
    
    c_add_s, c_vz = st.columns(2)
    novo_sms = c_add_s.text_input("Novo Item SMS (DB):", key=f"new_s_{DISCIPLINA_ATUAL}")
    if c_add_s.button("💾 Adicionar SMS", key=f"btn_s_{DISCIPLINA_ATUAL}"):
        if utils_db.aprender_novo_item("sms", novo_sms):
            st.toast("Salvo!"); st.rerun()
            
    st.divider()
    sms_livre = st.text_area("📝 Texto Livre (Segurança):", height=150)

with tab5:
    c_v1, c_v2 = st.columns(2)
    val = c_v1.text_input("Valor Total (R$)")
    pgto = c_v2.text_area("Pagamento")
    obs = st.text_area("Obs Gerais")
    status = st.selectbox("Status", ["Em Elaboração", "Finalizado"])

st.markdown("---")
dados = {
    'disciplina': DISCIPLINA_ATUAL, 'cliente': cliente, 'obra': obra,
    'fornecedor': forn, 'cnpj_fornecedor': cnpj,
    'responsavel': resp_eng, 'resp_suprimentos': resp_sup,
    'revisao': revisao, 'resumo_escopo': resumo,
    'itens_tecnicos': itens_tec, 'tecnico_livre': tec_livre,
    'itens_qualidade': itens_qual, 'matriz': escolhas, 
    'nrs_selecionadas': nrs, 'sms_livre': sms_livre,
    'valor_total': val, 'condicao_pgto': pgto, 'obs_gerais': obs,
    'status': status, 'data_inicio': date.today().strftime("%Y-%m-%d")
}

c_b1, c_b2 = st.columns(2)
if c_b1.button("☁️ APENAS SALVAR"):
    if not cliente or not obra: st.error("Preencha Cliente e Obra")
    else: 
        if utils_db.registrar_projeto(dados): st.success("Salvo!"); st.toast("Salvo")
        else: st.error("Erro")

if c_b2.button("💾 SALVAR E GERAR DOCX", type="primary"):
    if not cliente or not obra: st.error("Preencha Cliente e Obra")
    else:
        utils_db.registrar_projeto(dados)
        b = gerar_docx(dados)
        st.download_button(f"📥 Baixar DOCX", b, f"Escopo_{DISCIPLINA_ATUAL}.docx")
