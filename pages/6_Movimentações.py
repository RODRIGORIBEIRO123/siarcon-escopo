import streamlit as st
from docx import Document
from docx.shared import Pt
import io
from datetime import date
import utils_db

# ============================================================================
# 🚨 CONFIGURAÇÃO ESPECÍFICA: MOVIMENTAÇÕES
# ============================================================================
DISCIPLINA_ATUAL = "Movimentacoes" 

ITENS_MATRIZ = [
    "Guindaste", "Caminhão Munk", "Empilhadeira",
    "Equipe de Remoção Técnica", "Plano de Rigging", "Seguro de Carga",
    "Batedores/Escolta", "Autorizações Viárias", "Isolamento da Área"
]
# ============================================================================

st.set_page_config(page_title=f"Escopo {DISCIPLINA_ATUAL}", page_icon="🏗️", layout="wide")

# --- CARGA DE DADOS ---
if 'opcoes_db' not in st.session_state or st.sidebar.button("🔄 Forçar Recarga"):
    with st.spinner("Lendo banco de dados..."):
        st.cache_data.clear()
        st.session_state['opcoes_db'] = utils_db.carregar_opcoes()

# --- CHAVES DE CATEGORIA ---
cat_tecnica_db = f"tecnico_{DISCIPLINA_ATUAL.lower()}"
cat_qualidade_db = f"qualidade_{DISCIPLINA_ATUAL.lower()}"

# --- VERIFICAÇÃO DE EDIÇÃO (LÓGICA DO BOTÃO LÁPIS) ---
id_projeto = st.session_state.get('id_projeto_editar')
dados_edit = {}

if id_projeto:
    temp_dados = utils_db.buscar_projeto_por_id(id_projeto)
    if temp_dados and temp_dados.get('disciplina') == DISCIPLINA_ATUAL:
        dados_edit = temp_dados
        st.toast(f"✏️ Editando projeto: {dados_edit.get('obra')}")
    else:
        dados_edit = {}

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
if dados_edit: st.info(f"Modo Edição: {dados_edit.get('cliente')} - {dados_edit.get('obra')}")

opcoes = st.session_state.get('opcoes_db', {})

tab1, tab2, tab3, tab4, tab5 = st.tabs(["Cadastro", "Técnico", "Matriz", "SMS", "Comercial"])

with tab1:
    st.warning("⚠️ Suprimentos: Preencher campos do fornecedor.")
    c1, c2 = st.columns(2)
    
    # PREENCHIMENTO AUTOMÁTICO (EDIÇÃO)
    cliente = c1.text_input("Cliente", value=dados_edit.get('cliente', ''))
    obra = c1.text_input("Obra", value=dados_edit.get('obra', ''))
    
    db_forn = utils_db.listar_fornecedores()
    lista_nomes = [""] + [f['Fornecedor'] for f in db_forn]
    
    # Tenta pré-selecionar
    val_forn_db = dados_edit.get('fornecedor', '')
    index_forn = 0
    if val_forn_db in lista_nomes: index_forn = lista_nomes.index(val_forn_db)
    
    sel_forn = c1.selectbox("Selecionar Fornecedor (Banco):", lista_nomes, index=index_forn)
    
    cnpj_auto = ""
    if sel_forn:
        found = next((f for f in db_forn if f['Fornecedor'] == sel_forn), None)
        if found: cnpj_auto = str(found['CNPJ'])
    
    val_final_forn = sel_forn if sel_forn else dados_edit.get('fornecedor', '')
    val_final_cnpj = cnpj_auto if cnpj_auto else dados_edit.get('cnpj_fornecedor', '')

    forn = c1.text_input("Razão Social:", value=val_final_forn)
    cnpj = c1.text_input("CNPJ:", value=val_final_cnpj)
    
    resp_eng = c2.text_input("Engenharia", value=dados_edit.get('responsavel', ''))
    resp_sup = c2.text_input("Suprimentos", value=dados_edit.get('resp_suprimentos', ''))
    revisao = c2.text_input("Revisão", value=dados_edit.get('revisao', 'R-00'))
    resumo = c2.text_area("Resumo Escopo", value=dados_edit.get('resumo_escopo', ''))

    st.markdown("---")
    with st.expander("➕ Não achou? Cadastre um NOVO Fornecedor aqui"):
        cc1, cc2, cc3 = st.columns([2, 1, 1])
        novo_nome_f = cc1.text_input("Nome", key=f"nf_{DISCIPLINA_ATUAL}")
        novo_cnpj_f = cc2.text_input("CNPJ", key=f"cf_{DISCIPLINA_ATUAL}")
        cc3.write(""); cc3.write("")
        if cc3.button("💾", key=f"bf_{DISCIPLINA_ATUAL}"):
            if novo_nome_f:
                utils_db.cadastrar_fornecedor_db(novo_nome_f, novo_cnpj_f)
                st.success("Salvo!"); st.cache_data.clear(); st.rerun()

with tab2:
    st.subheader("Itens Técnicos")
    lista_tec = opcoes.get(cat_tecnica_db, [])
    
    # Recupera itens salvos para edição
    itens_salvos = dados_edit.get('itens_tecnicos', [])
    if isinstance(itens_salvos, str): itens_salvos = eval(itens_salvos)
    
    opcoes_finais = sorted(list(set(lista_tec + itens_salvos)))
    
    k_tec = f"tec_{DISCIPLINA_ATUAL.lower()}"
    itens_tec = st.multiselect("Selecione Itens:", opcoes_finais, default=itens_salvos, key=k_tec)
    
    c_add, c_txt = st.columns(2)
    novo_tec = c_add.text_input("Novo Item Técnico (DB):", key=f"new_{k_tec}")
    if c_add.button("💾 Adicionar", key=f"btn_{k_tec}"):
        if utils_db.aprender_novo_item(cat_tecnica_db, novo_tec): st.toast("Salvo!"); st.rerun()
            
    tec_livre = st.text_area("📝 Texto Livre (Técnico):", value=dados_edit.get('tecnico_livre', ''), height=150)
    
    st.divider()
    st.subheader("Qualidade")
    lista_qual = opcoes.get(cat_qualidade_db, [])
    
    itens_salvos_q = dados_edit.get('itens_qualidade', [])
    if isinstance(itens_salvos_q, str): itens_salvos_q = eval(itens_salvos_q)
    opcoes_finais_q = sorted(list(set(lista_qual + itens_salvos_q)))

    k_qual = f"qual_{DISCIPLINA_ATUAL.lower()}"
    itens_qual = st.multiselect("Selecione Itens:", opcoes_finais_q, default=itens_salvos_q, key=k_qual)
    
    c_add_q, c_vz = st.columns(2)
    novo_qual = c_add_q.text_input("Novo Item Qualidade (DB):", key=f"new_q_{k_qual}")
    if c_add_q.button("💾 Adicionar", key=f"btn_q_{k_qual}"):
        if utils_db.aprender_novo_item(cat_qualidade_db, novo_qual): st.toast("Salvo!"); st.rerun()

with tab3:
    escolhas = {}
    nome_f = forn.split(' ')[0].upper() if forn else "FORN"
    matriz_salva = dados_edit.get('matriz', {})
    if isinstance(matriz_salva, str): matriz_salva = eval(matriz_salva)

    for item in ITENS_MATRIZ:
        c_m1, c_m2 = st.columns([2,1])
        c_m1.write(f"**{item}**")
        
        val_padrao = 0 
        if item in matriz_salva and matriz_salva[item] != "SIARCON": val_padrao = 1
        
        escolhas[item] = c_m2.radio(item, ["SIARCON", nome_f], index=val_padrao, horizontal=True, label_visibility="collapsed", key=f"mtz_{item}")
        st.divider()

with tab4:
    st.subheader("SMS")
    nrs_salvas = dados_edit.get('nrs_selecionadas', [])
    if isinstance(nrs_salvas, str): nrs_salvas = eval(nrs_salvas)
    opcoes_sms = sorted(list(set(opcoes.get('sms', []) + nrs_salvas)))

    nrs = st.multiselect("NRs Aplicáveis:", opcoes_sms, default=nrs_salvas, key=f"sms_{DISCIPLINA_ATUAL}")
    
    c_add_s, c_vz = st.columns(2)
    novo_sms = c_add_s.text_input("Novo Item SMS (DB):", key=f"new_s_{DISCIPLINA_ATUAL}")
    if c_add_s.button("💾 Adicionar SMS", key=f"btn_s_{DISCIPLINA_ATUAL}"):
        if utils_db.aprender_novo_item("sms", novo_sms): st.toast("Salvo!"); st.rerun()
            
    st.divider()
    sms_livre = st.text_area("📝 Texto Livre (Segurança):", value=dados_edit.get('sms_livre', ''), height=150)

with tab5:
    c_v1, c_v2 = st.columns(2)
    val = c_v1.text_input("Valor Total (R$)", value=dados_edit.get('valor_total', ''))
    pgto = c_v2.text_area("Pagamento", value=dados_edit.get('condicao_pgto', ''))
    obs = st.text_area("Obs Gerais", value=dados_edit.get('obs_gerais', ''))
    
    status_atual = dados_edit.get('status', 'Em Elaboração')
    lista_status = ["Em Elaboração", "Em Análise Obras", "Em Cotação", "Finalizado", "Concluído"]
    idx_status = 0
    if status_atual in lista_status: idx_status = lista_status.index(status_atual)
    
    status = st.selectbox("Status", lista_status, index=idx_status)

st.markdown("---")
id_final = dados_edit.get('_id', None)

dados = {
    '_id': id_final,
    'disciplina': DISCIPLINA_ATUAL, 'cliente': cliente, 'obra': obra,
    'fornecedor': forn, 'cnpj_fornecedor': cnpj,
    'responsavel': resp_eng, 'resp_suprimentos': resp_sup,
    'revisao': revisao, 'resumo_escopo': resumo,
    'itens_tecnicos': itens_tec, 'tecnico_livre': tec_livre,
    'itens_qualidade': itens_qual, 'matriz': escolhas, 
    'nrs_selecionadas': nrs, 'sms_livre': sms_livre,
    'valor_total': val, 'condicao_pgto': pgto, 'obs_gerais': obs,
    'status': status, 'data_inicio': dados_edit.get('data_inicio', date.today().strftime("%Y-%m-%d"))
}

c_b1, c_b2 = st.columns(2)
if c_b1.button("☁️ SALVAR NO BANCO"):
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
