import streamlit as st
import pandas as pd
from datetime import datetime
import time
import utils_db 

# Configuração
st.set_page_config(page_title="Hidráulica", page_icon="💧", layout="wide")

# 1. Recupera Vínculo
projeto_ativo = st.session_state.get('projeto_ativo', '')
cliente_ativo = st.session_state.get('cliente_ativo', '')
id_projeto = st.session_state.get('id_projeto_editar', '')

if not projeto_ativo:
    st.error("⛔ Nenhum projeto selecionado.")
    if st.button("Voltar"): st.switch_page("_📊_Dashboard.py")
    st.stop()

# Título e Ícone conforme seu print
st.title("💧 Hidraulica")

# --- RECRIANDO AS ABAS DO SEU PRINT ---
tab1, tab2, tab3, tab4, tab5 = st.tabs(["Cadastro", "Técnico", "Matriz", "SMS", "Comercial"])

# === ABA 1: CADASTRO (IGUAL AO PRINT) ===
with tab1:
    with st.form("form_cadastro_geral"):
        c1, c2 = st.columns(2)
        val_cliente = c1.text_input("Cliente", value=cliente_ativo) # Já vem preenchido
        val_eng = c2.text_input("Engenharia", value="Siarcon")
        
        c3, c4 = st.columns(2)
        val_obra = c3.text_input("Obra", value=projeto_ativo) # Já vem preenchido
        val_sup = c4.text_input("Suprimentos")
        
        c5, c6 = st.columns(2)
        # Lista fornecedores do banco
        lista_forn = [f['Fornecedor'] for f in utils_db.listar_fornecedores()]
        val_forn = c5.selectbox("Fornecedor (Banco):", [""] + lista_forn)
        val_rev = c6.text_input("Revisão", value="R-00")
        
        c7, c8 = st.columns(2)
        val_razao = c7.text_input("Razão Social")
        val_resumo = c8.text_area("Resumo Escopo")
        
        val_cnpj = st.text_input("CNPJ")
        
        st.divider()
        b_col1, b_col2 = st.columns([1,5])
        with b_col1:
            if st.form_submit_button("☁️ SALVAR"):
                # Atualiza dados do projeto no banco
                dados = {
                    "_id": id_projeto,
                    "cliente": val_cliente,
                    "obra": val_obra,
                    "fornecedor": val_forn
                    # Adicione outros campos conforme seu utils_db suportar
                }
                utils_db.registrar_projeto(dados)
                st.success("Dados de cadastro atualizados!")
        with b_col2:
            st.form_submit_button("💾 SALVAR E DOCX") # Placeholder visual

# === ABA 2: TÉCNICO (ONDE ESTAVAM OS ITENS QUE SUMIRAM) ===
with tab2:
    st.subheader(f"Lista de Materiais - {projeto_ativo}")
    
    # 1. Formulário Rápido de Adição
    with st.expander("➕ Adicionar Novo Item", expanded=True):
        c_desc, c_qtd, c_unid, c_btn = st.columns([3, 1, 1, 1])
        with c_desc: desc_item = st.text_input("Descrição do Item")
        with c_qtd: qtd_item = st.number_input("Qtd", value=1.0)
        with c_unid: unid_item = st.selectbox("Unid.", ["pç", "m", "vb", "kg", "cj"])
        with c_btn: 
            st.write("") # Espaçamento
            if st.button("Adicionar"):
                if desc_item:
                    # Salva no banco local ou utils_db
                    if 'db_escopo' not in st.session_state: st.session_state['db_escopo'] = []
                    novo = {
                        "projeto": projeto_ativo,
                        "disciplina": "Hidráulica",
                        "descricao": desc_item,
                        "qtd": qtd_item,
                        "unid": unid_item,
                        "data": datetime.now().strftime("%d/%m")
                    }
                    st.session_state['db_escopo'].append(novo)
                    st.rerun()

    # 2. Tabela de Itens (O que você quer ver)
    if 'db_escopo' not in st.session_state: st.session_state['db_escopo'] = []
    df_escopo = pd.DataFrame(st.session_state['db_escopo'])
    
    if not df_escopo.empty:
        # Filtra pelo projeto atual
        filtro = (df_escopo['projeto'] == projeto_ativo) & (df_escopo['disciplina'] == "Hidráulica")
        df_show = df_escopo[filtro].copy()
        
        if not df_show.empty:
            st.data_editor(
                df_show, 
                column_config={"projeto": None, "disciplina": None},
                use_container_width=True,
                num_rows="dynamic",
                key="editor_hidraulica"
            )
        else:
            st.info("Nenhum item técnico cadastrado ainda.")
    else:
        st.info("Lista vazia.")

# === OUTRAS ABAS (Placeholder) ===
with tab3: st.info("Matriz de Responsabilidades")
with tab4: st.info("Segurança do Trabalho (SMS)")
with tab5: st.info("Comercial")

st.divider()
if st.button("⬅️ Voltar ao Dashboard"):
    st.switch_page("_📊_Dashboard.py")
