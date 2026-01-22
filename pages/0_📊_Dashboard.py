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
    # Tenta pegar o cliente com segurança (.get não funciona bem em Series solta, usamos iloc ou verificação)
    ultimo_cliente = df.iloc[-1]['Cliente'] if 'Cliente' in df.columns else "---"
    col2.metric("Último Cliente", ultimo_cliente)
    
    st.divider()

    # --- 3. SELEÇÃO SIMPLIFICADA (DROPDOWN) ---
    st.markdown("### ✏️ Editar Projeto")
    
    # Verifica se as colunas essenciais existem antes de criar o Display
    if 'Cliente' in df.columns and 'Obra' in df.columns:
        df['Display'] = df['_id_linha'].astype(str) + " | " + df['Cliente'] + " - " + df['Obra']
    else:
        # Se os nomes estiverem errados na planilha, usa o índice
        df['Display'] = "Linha " + df['_id_linha'].astype(str)

    # Caixa de Seleção
    projeto_escolhido = st.selectbox(
        "Selecione o projeto na lista abaixo:",
        options=df['Display'],
        index=None,
        placeholder="Clique aqui para buscar..."
    )

    # --- 4. AÇÃO ---
    if projeto_escolhido:
        row = df[df['Display'] == projeto_escolhido].iloc[0]
        
        # --- CORREÇÃO DO ERRO AQUI ---
        # Tenta achar o valor em várias colunas possíveis ou deixa vazio
        valor_mostrado = "---"
        possiveis_nomes = ["Valor", "Valor Total", "Total", "valor", "valor_total"]
        
        for nome in possiveis_nomes:
            if nome in row:
                valor_mostrado = row[nome]
                break
        # -----------------------------

        st.info(f"Você selecionou: **{row.get('Cliente', 'Sem Cliente')}** (Valor: {valor_mostrado})")
        
        if st.button("🚀 ABRIR EDITOR DE ESCOPO", type="primary"):
            st.session_state['dados_projeto'] = row.to_dict()
            st.session_state['modo_edicao'] = True
            st.switch_page("pages/1_❄️_Escopo_Dutos.py")

    st.markdown("---")
    st.markdown("### 📋 Visão Geral (Tabela)")
    st.caption("Abaixo estão os dados exatos lidos da planilha. Verifique os nomes das colunas na Linha 1.")
    st.dataframe(
        df, 
        use_container_width=True, 
        hide_index=True,
        column_config={"Display": None, "_id_linha": None}
    )

else:
    st.info("📭 Nenhum projeto encontrado. Vá em 'Escopo Dutos' e crie o primeiro!")
