import streamlit as st
import pandas as pd
import utils_db

st.set_page_config(page_title="Dashboard | SIARCON", page_icon="📊", layout="wide")
st.title("📊 Painel de Controle")

# --- 1. CARREGAR DADOS ---
if st.button("🔄 Atualizar Dados"): st.rerun()

df = utils_db.listar_todos_projetos()

if not df.empty:
    # --- 2. MÉTRICAS RÁPIDAS ---
    col1, col2 = st.columns(2)
    col1.metric("Total de Projetos", len(df))
    col2.metric("Último Cliente", df.iloc[-1]['Cliente'])
    
    st.divider()

    # --- 3. SELEÇÃO SIMPLIFICADA (DROPDOWN) ---
    st.markdown("### ✏️ Editar Projeto")
    
    # Cria uma coluna "Nome Bonito" para aparecer na lista
    # Ex: "Linha 2 - Hitachi (Guarulhos)"
    df['Display'] = df['_id_linha'].astype(str) + " | " + df['Cliente'] + " - " + df['Obra']
    
    # Caixa de Seleção
    projeto_escolhido = st.selectbox(
        "Selecione o projeto na lista abaixo:",
        options=df['Display'],
        index=None, # Começa vazio
        placeholder="Clique aqui para buscar..."
    )

    # --- 4. AÇÃO ---
    if projeto_escolhido:
        # Encontra a linha original baseada na escolha
        row = df[df['Display'] == projeto_escolhido].iloc[0]
        
        st.info(f"Você selecionou: **{row['Cliente']}** (Valor: {row['Valor']})")
        
        if st.button("🚀 ABRIR EDITOR DE ESCOPO", type="primary"):
            # Guarda os dados na memória
            st.session_state['dados_projeto'] = row.to_dict()
            st.session_state['modo_edicao'] = True
            st.switch_page("pages/1_❄️_Escopo_Dutos.py")

    st.markdown("---")
    st.markdown("### 📋 Visão Geral (Tabela)")
    # Mostra a tabela apenas para consulta visual
    st.dataframe(
        df, 
        use_container_width=True, 
        hide_index=True,
        column_config={"Display": None, "_id_linha": None} # Esconde colunas técnicas
    )

else:
    st.info("📭 Nenhum projeto encontrado. Vá em 'Escopo Dutos' e crie o primeiro!")
