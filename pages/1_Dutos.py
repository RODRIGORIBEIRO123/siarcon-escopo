import streamlit as st
import pandas as pd
from datetime import datetime
import time

# ============================================================================
# 1. CONFIGURAÇÃO E CONTEXTO (CORREÇÃO DO LOOP DE CADASTRO)
# ============================================================================
st.set_page_config(page_title="Escopo - Dutos", page_icon="🔧", layout="wide")

# Verifica Login
if 'logado' not in st.session_state or not st.session_state['logado']:
    st.warning("🔒 Acesso negado. Faça login no Dashboard.")
    st.stop()

# Recupera o contexto do Dashboard (CORREÇÃO PRINCIPAL)
cliente_atual = st.session_state.get('cliente_ativo', None)
projeto_atual = st.session_state.get('projeto_ativo', None)

if not cliente_atual or not projeto_atual:
    st.error("⚠️ Nenhum projeto selecionado. Volte ao Dashboard e selecione um projeto.")
    st.stop()

# Define a disciplina desta página (MUDE ISSO NAS OUTRAS PÁGINAS)
DISCIPLINA_ATUAL = "Dutos"

st.title(f"🔧 Escopo Manual: {DISCIPLINA_ATUAL}")
st.caption(f"Projeto: **{projeto_atual}** | Cliente: **{cliente_atual}**")

# Inicializa banco de dados na memória se não existir
if 'db_escopo' not in st.session_state:
    st.session_state['db_escopo'] = []

# ============================================================================
# 2. FORMULÁRIO DE CADASTRO (COM AUTO-REFRESH)
# ============================================================================
with st.sidebar:
    st.header(f"➕ Adicionar em {DISCIPLINA_ATUAL}")
    
    with st.form("form_item", clear_on_submit=True):
        # Campos
        descricao = st.text_input("Descrição do Item:")
        c1, c2 = st.columns(2)
        qtd = c1.number_input("Quantidade", min_value=0.0, value=1.0, step=1.0)
        unid = c2.selectbox("Unidade", ["pç", "m", "m²", "kg", "vb", "h", "gl", "cj"])
        obs = st.text_area("Observações / Detalhes")
        
        # Botão Salvar
        enviado = st.form_submit_button("💾 Salvar Item")

        if enviado:
            if not descricao:
                st.error("A descrição é obrigatória.")
            else:
                # Cria o registro
                novo_item = {
                    "id": len(st.session_state['db_escopo']) + 1,
                    "data": datetime.now().strftime("%d/%m/%Y %H:%M"),
                    "projeto": projeto_atual,     # Pega do Dashboard
                    "cliente": cliente_atual,     # Pega do Dashboard
                    "disciplina": DISCIPLINA_ATUAL, # Fixa a disciplina da página
                    "descricao": descricao,
                    "qtd": qtd,
                    "unid": unid,
                    "obs": obs,
                    "origem": "Manual"
                }
                
                # Salva no banco global
                st.session_state['db_escopo'].append(novo_item)
                
                # Feedback e RECARGA FORÇADA (Correção do Bug visual)
                st.success(f"Item adicionado a {DISCIPLINA_ATUAL}!")
                time.sleep(0.5) 
                st.rerun()

# ============================================================================
# 3. VISUALIZAÇÃO DA TABELA (FILTRADA)
# ============================================================================
# Converte lista para DataFrame
df = pd.DataFrame(st.session_state['db_escopo'])

if not df.empty:
    # Filtra apenas: Projeto Atual E Disciplina Atual
    filtro = (df['projeto'] == projeto_atual) & (df['disciplina'] == DISCIPLINA_ATUAL)
    df_filtrado = df[filtro].copy()

    if not df_filtrado.empty:
        st.markdown("### 📋 Itens Cadastrados")
        
        # Edição direta na tabela
        df_editado = st.data_editor(
            df_filtrado,
            column_config={
                "descricao": "Descrição",
                "qtd": st.column_config.NumberColumn("Qtd", format="%.2f"),
                "unid": "Unid.",
                "obs": "Observação",
                "data": "Data",
                "id": None,           # Esconde coluna técnica
                "projeto": None,      # Já sabemos o projeto
                "cliente": None,
                "disciplina": None,   # Já sabemos a disciplina
                "origem": None
            },
            use_container_width=True,
            num_rows="dynamic", # Permite adicionar/remover linhas direto na tabela
            key=f"editor_{DISCIPLINA_ATUAL}"
        )
        
        # KPI Rápido
        total_itens = len(df_filtrado)
        st.caption(f"Total de itens nesta disciplina: {total_itens}")
        
    else:
        st.info(f"Nenhum item cadastrado para **{DISCIPLINA_ATUAL}** neste projeto.")
else:
    st.info("O banco de dados de escopo está vazio.")

# ============================================================================
# 4. AÇÃO EXTRA (LIMPEZA)
# ============================================================================
st.divider()
if st.button(f"🗑️ Limpar Lista de {DISCIPLINA_ATUAL}", type="secondary"):
    # Mantém tudo que NÃO for (Projeto Atual + Disciplina Atual)
    st.session_state['db_escopo'] = [
        item for item in st.session_state['db_escopo'] 
        if not (item['projeto'] == projeto_atual and item['disciplina'] == DISCIPLINA_ATUAL)
    ]
    st.rerun()
