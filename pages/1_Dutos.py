import streamlit as st
from docx import Document
from docx.shared import Pt
import io
from datetime import date, timedelta
import utils_db  # Importa sua nova conexão com o Google Sheets

# --- 1. CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Escopo Dutos | SIARCON", page_icon="❄️", layout="wide")
DISCIPLINA_ATUAL = "Dutos"

# --- 2. CARGA DE DADOS INICIAIS ---
# Força o carregamento das opções do Google Sheets
if 'opcoes_db' not in st.session_state or st.sidebar.button("🔄 Recarregar Dados"):
    with st.spinner("Sincronizando com Google Sheets..."):
        st.session_state['opcoes_db'] = utils_db.carregar_opcoes()

# --- 3. FUNÇÕES AUXILIARES ---
def adicionar_item_callback(categoria, key_input):
    novo = st.session_state.get(key_input, "")
    if novo:
        # Salva no Google Sheets
        if utils_db.aprender_novo_item(categoria, novo):
            st.session_state[key_input] = "" # Limpa campo
            st.session_state['opcoes_db'] = utils_db.carregar_opcoes() # Atualiza lista
            st.toast(f"✅ Item '{novo}' salvo no banco!", icon="💾")
        else:
            st.error("Erro ao salvar item.")

def cadastrar_fornecedor_callback():
    nome = st.session_state.get("novo_forn_nome")
    cnpj = st.session_state.get("novo_forn_cnpj")
    if nome:
        res = utils_db.cadastrar_fornecedor_db(nome, cnpj)
        if res == "Existe":
            st.warning("Fornecedor já existe!")
        elif res:
            st.toast("Fornecedor Cadastrado!", icon="🏢")
            st.rerun() # Recarrega para aparecer na lista
        else:
            st.error("Erro ao cadastrar.")

def formatar_moeda_brl(valor):
    if not valor: return ""
    try:
        v = float(str(valor).replace('R$', '').replace('.', '').replace(',', '.').strip())
        return f"R$ {v:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
    except: return valor

# --- 4. GERADOR DE DOCUMENTO DOCX ---
def gerar_docx(dados):
    document = Document()
    try: style = document.styles['Normal']; style.font.name = 'Calibri'; style.font.size = Pt(11)
    except: pass
    
    document.add_heading(f'Escopo de Fornecimento - {DISCIPLINA_ATUAL}', 0)
    document.add_paragraph(f"Data: {date.today().strftime('%d/%m/%Y')} | Rev: {dados.get('revisao', '-')}")

    document.add_heading('1. OBJETIVO', 1)
    table = document.add_table(rows=1, cols=2)
    try: table.style = 'Table Grid'
    except: pass
    
    # Preenche tabela
    infos = [
        ("Cliente", dados.get('cliente', '')), ("Obra", dados.get('obra', '')),
        ("Fornecedor", dados.get('fornecedor', '')), ("CNPJ", dados.get('cnpj_fornecedor', '')),
        ("Resp. Eng", dados.get('responsavel', '')), ("Resp. Obras", dados.get('resp_obras', '')),
        ("Suprimentos", dados.get('resp_suprimentos', ''))
    ]
    for k, v in infos:
        row = table.add_row().cells
        row[0].text = k; row[0].paragraphs[0].runs[0].bold = True
        row[1].text = str(v)

    document.add_paragraph(f"\nResumo: {dados.get('resumo_escopo', '')}")

    document.add_heading('2. TÉCNICO', 1)
    for item in dados.get('itens_tecnicos', []): document.add_paragraph(item, style='List Bullet')
    if dados.get('tecnico_livre'): document.add_paragraph(dados['tecnico_livre'])

    document.add_heading('3. MATRIZ DE RESPONSABILIDADE', 1)
    t_m = document.add_table(rows=1, cols=3)
    try: t_m.style = 'Table Grid'
    except: pass
    h = t_m.rows[0].cells; h[0].text = "ITEM"; h[1].text = "SIARCON"; h[2].text = dados.get('fornecedor', 'FORN')
    
    for item, resp in dados.get('matriz', {}).items():
        row = t_m.add_row().cells
        row[0].text = item
        if resp == "SIARCON": row[1].text = "X"
        else: row[2].text = "X"

    document.add_heading('4. SMS & SEGURANÇA', 1)
    for nr in dados.get('nrs_selecionadas', []): document.add_paragraph(nr, style='List Bullet')

    document.add_heading('5. COMERCIAL', 1)
    document.add_paragraph(f"Valor Global: {formatar_moeda_brl(dados.get('valor_total', ''))}")
    document.add_paragraph(f"Pagamento: {dados.get('condicao_pgto', '')}")
    if dados.get('obs_gerais'): document.add_paragraph(f"Obs: {dados['obs_gerais']}")
    
    b = io.BytesIO(); document.save(b); b.seek(0); return b

# --- 5. INTERFACE DO USUÁRIO ---
st.title(f"❄️ Escopo de {DISCIPLINA_ATUAL}")

# Recupera listas do banco (cache)
opcoes = st.session_state.get('opcoes_db', {'tecnico': [], 'qualidade': [], 'sms': []})

tab1, tab2, tab3, tab4, tab5 = st.tabs(["1. Cadastro", "2. Técnico", "3. Matriz", "4. SMS", "5. Comercial"])

with tab1:
    c1, c2 = st.columns(2)
    with c1:
        cliente = st.text_input("Cliente")
        obra = st.text_input("Obra")
        
        # Seleção de Fornecedor do Banco
        db_fornecedores = utils_db.listar_fornecedores()
        lista_nomes = [""] + [f['Fornecedor'] for f in db_fornecedores]
        sel_forn = st.selectbox("Fornecedor (Banco):", options=lista_nomes)
        
        # Preenchimento automático se selecionar do banco
        val_nome = sel_forn
        val_cnpj = ""
        if sel_forn:
            found = next((f for f in db_fornecedores if f['Fornecedor'] == sel_forn), None)
            if found: val_cnpj = str(found['CNPJ'])
        
        forn = st.text_input("Razão Social:", value=val_nome)
        cnpj_forn = st.text_input("CNPJ:", value=val_cnpj)
        
        with st.expander("➕ Cadastrar Novo Fornecedor"):
            st.text_input("Nome", key="novo_forn_nome")
            st.text_input("CNPJ", key="novo_forn_cnpj")
            st.button("Salvar no Banco", on_click=cadastrar_fornecedor_callback)

    with c2:
        resp_eng = st.text_input("Resp. Engenharia")
        resp_obr = st.text_input("Resp. Obras")
        resp_sup = st.text_input("Resp. Suprimentos")
        revisao = st.text_input("Revisão", "R-00")
        resumo = st.text_area("Resumo do Escopo")

with tab2:
    st.subheader("Itens Técnicos")
    # Multiselect carregado do Google Sheets
    itens_tec = st.multiselect("Selecione:", options=opcoes.get('tecnico', []), key="tec_dutos")
    
    c_a, c_b = st.columns(2)
    c_a.text_input("Adicionar novo item ao banco:", key="novo_item_tec")
    c_a.button("💾 Salvar Item", on_click=adicionar_item_callback, args=("tecnico", "novo_item_tec"))
    
    tec_livre = c_b.text_area("Texto Livre (Específico deste projeto)")
    
    st.divider()
    st.subheader("Qualidade")
    itens_qual = st.multiselect("Itens Qualidade:", options=opcoes.get('qualidade', []), key="qual_dutos")

with tab3:
    st.info("Defina quem fornece o item: SIARCON ou FORNECEDOR")
    escolhas = {}
    # LISTA ESPECÍFICA DE DUTOS
    ITENS_MATRIZ = [
        "Chapas galvanizadas", "Perfis e cantoneiras", "Mão de obra fabricação", 
        "Mão de obra montagem", "Consumíveis (parafusos, vedantes)", "Andaimes/Plataformas", 
        "Transporte horizontal/vertical", "Projetos executivos", "ART"
    ]
    nome_f = forn.split(' ')[0].upper() if forn else "FORN"
    
    for i in ITENS_MATRIZ:
        c1, c2 = st.columns([2,1])
        c1.write(f"**{i}**")
        escolhas[i] = c2.radio(f"radio_{i}", ["SIARCON", nome_f], horizontal=True, label_visibility="collapsed", key=f"m_{i}")
        st.divider()

with tab4:
    st.subheader("Segurança (SMS)")
    nrs = st.multiselect("NRs Aplicáveis:", options=opcoes.get('sms', []), key="sms_dutos")

with tab5:
    c1, c2 = st.columns(2)
    val = c1.text_input("Valor Total (R$)", placeholder="0,00")
    pgto = c2.text_area("Condição de Pagamento")
    obs = st.text_area("Observações Gerais")
    status = st.selectbox("Status do Projeto", ["Em Elaboração", "Enviado para Cotação", "Contratação Finalizada"])

st.markdown("---")

# --- 6. BOTÃO DE SALVAR PRINCIPAL ---
if st.button("💾 SALVAR PROJETO E GERAR ARQUIVO", type="primary"):
    if not cliente or not obra:
        st.error("Preencha Cliente e Obra para salvar.")
    else:
        # 1. Monta o pacote de dados
        dados_projeto = {
            'disciplina': DISCIPLINA_ATUAL,
            'cliente': cliente, 'obra': obra,
            'fornecedor': forn, 'cnpj_fornecedor': cnpj_forn,
            'responsavel': resp_eng, 'resp_obras': resp_obr, 'resp_suprimentos': resp_sup,
            'revisao': revisao, 'resumo_escopo': resumo,
            'itens_tecnicos': itens_tec, 'tecnico_livre': tec_livre,
            'itens_qualidade': itens_qual,
            'matriz': escolhas,
            'nrs_selecionadas': nrs,
            'valor_total': val, 'condicao_pgto': pgto, 'obs_gerais': obs,
            'status': status,
            'data_inicio': date.today().strftime("%Y-%m-%d")
        }
        
        # 2. SALVA NO GOOGLE SHEETS
        with st.spinner("Salvando na nuvem..."):
            sucesso = utils_db.registrar_projeto(dados_projeto)
        
        if sucesso:
            st.success("✅ Projeto Salvo com Sucesso no Banco de Dados!")
            st.toast("Salvo na aba Projetos!", icon="☁️")
            
            # 3. Gera o DOCX para baixar
            docx = gerar_docx(dados_projeto)
            nome_arquivo = f"Escopo_{DISCIPLINA_ATUAL}_{cliente}_{obra}.docx".replace(" ", "_")
            st.download_button("📥 Baixar DOCX", docx.getvalue(), nome_arquivo)
        else:
            st.error("Erro ao salvar no banco de dados. Verifique sua conexão.")
