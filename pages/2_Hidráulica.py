import streamlit as st
import pandas as pd
from datetime import datetime
import time
import utils_db 

# ============================================================================
# CONFIGURAÇÃO E RECUPERAÇÃO DE DADOS
# ============================================================================
st.set_page_config(page_title="Hidráulica", page_icon="💧", layout="wide")

# 1. Recupera contexto do Dashboard
projeto_ativo = st.session_state.get('projeto_ativo', '')
cliente_ativo = st.session_state.get('cliente_ativo', '')

# Trava se não tiver projeto selecionado
if not projeto_ativo:
    st.error("⛔ Nenhum projeto selecionado.")
    if st.button("Voltar ao Dashboard"):
        st.switch_page("_📊_Dashboard.py")
    st.stop()

# Título da Página (Igual ao seu print)
st.title("💧 Hidraulica")

# ============================================================================
# ABAS (CADASTRO, TÉCNICO, MATRIZ, ETC.)
# ============================================================================
# Recria exatamente as abas da sua imagem
tab1, tab2, tab3, tab4, tab5 = st.tabs(["Cadastro", "Técnico", "Matriz", "SMS", "Comercial"])

# --- ABA 1: CADASTRO (IGUAL AO PRINT) ---
with tab1:
    with st.form("form_cadastro_hidraulica"):
        # Linha 1: Cliente e Engenharia
        c1, c2 = st.columns(2)
        # Preenche automaticamente com o que veio do Dashboard
        val_cliente = c1.text_input("Cliente", value=cliente_ativo)
        val_eng = c2.text_input("Engenharia", value="Siarcon") # Valor padrão ou buscar do banco

        # Linha 2: Obra e Suprimentos
        c3, c4 = st.columns(2)
        val_obra = c3.text_input("Obra", value=projeto_ativo)
        val_sup = c4.text_input("Suprimentos")

        # Linha 3: Fornecedor e Revisão
        c5, c6 = st.columns(2)
        # Busca lista de fornecedores do utils_db se possível
        lista_fornecedores = [f['Fornecedor'] for f in utils_db.listar_fornecedores()] 
        if not lista_fornecedores: lista_fornecedores = ["Cadastrar Novo..."]
        
        val_forn = c5.selectbox("Fornecedor (Banco):", lista_fornecedores)
        val_rev = c6.text_input("Revisão", value="R-00")

        # Linha 4: Razão Social e Resumo
        c7, c8 = st.columns(2)
        val_razao = c7.text_input("Razão Social:")
        val_resumo = c8.text_area("Resumo Escopo", height=100)

        # Linha 5: CNPJ
        val_cnpj = st.text_input("CNPJ:")

        st.divider()
        
        # Botões de Ação (Igual ao print)
        b1, b2, b3 = st.columns([1, 4, 1])
        with b1:
            btn_salvar = st.form_submit_button("☁️ SALVAR")
        with b3:
            # Botão visual (lógica de docx pode ser adicionada depois)
            st.form_submit_button("💾 SALVAR E DOCX")

        if btn_salvar:
            # Atualiza os dados no banco
            dados_atualizados = {
                "_id": st.session_state.get('id_projeto_editar'), # Mantém o ID
                "cliente": val_cliente,
                "obra": val_obra,
                "fornecedor": val_forn,
                # Adicione outros campos se seu banco suportar
            }
            # Tenta salvar
            try:
                utils_db.registrar_projeto(dados_atualizados)
                st.success("Dados atualizados com sucesso!")
                # Atualiza memória também
                st.session_state['projeto_ativo'] = val_obra
                st.session_state['cliente_ativo'] = val_cliente
            except Exception as e:
                st.error(f"Erro ao salvar: {e}")

# --- ABA 2: TÉCNICO (Espaço reservado) ---
with tab2:
    st.info("Área Técnica - Em desenvolvimento")

# --- ABA 3: MATRIZ ---
with tab3:
    st.info("Matriz de Responsabilidades - Em desenvolvimento")

# --- ABA 4: SMS ---
with tab4:
    st.info("Segurança do Trabalho - Em desenvolvimento")

# --- ABA 5: COMERCIAL ---
with tab5:
    st.info("Dados Comerciais - Em desenvolvimento")


# Botão de Voltar Fora das Abas
st.divider()
if st.button("⬅️ Voltar ao Dashboard"):
    st.switch_page("_📊_Dashboard.py")
