import streamlit as st
import pandas as pd
import utils_db

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Dashboard | SIARCON", page_icon="📊", layout="wide")

st.title("📊 Painel de Controle de Projetos")
st.markdown("Visão geral de escopos gerados e status de contratos.")

# --- 1. CARREGAR DADOS ---
with st.spinner("Buscando dados no Google Sheets..."):
    # Chama a função nova que criamos no utils_db
    df = utils_db.listar_todos_projetos()

# --- 2. SE TIVER DADOS, MOSTRA O PAINEL ---
if not df.empty:
    # --- MÉTRICAS (KPIs) ---
    st.markdown("### 📈 Indicadores")
    col1, col2, col3, col4 = st.columns(4)
    
    total = len(df)
    # Conta quantos tem status "Gerado" (assumindo que esse é o status inicial)
    # Se a coluna 'Status' não existir por algum erro, considera 0
    pendentes = len(df[df["Status"] == "Gerado"]) if "Status" in df.columns else 0
    
    # Calcula valor total (precisa limpar o R$ e converter para somar)
    # Por enquanto vamos mostrar apenas contagem para não dar erro de conversão
    
    col1.metric("Total de Escopos", total)
    col2.metric("Pendentes Aprovação", pendentes)
    col3.metric("Concluídos", total - pendentes)
    col4.metric("Última Atualização", "Agora")

    st.divider()

    # --- FILTROS ---
    st.markdown("### 🔍 Pesquisa Detalhada")
    
    c_f1, c_f2, c_f3 = st.columns(3)
    with c_f1:
        # Pega lista única de clientes
        filtro_cliente = st.multiselect("Cliente:", options=df["Cliente"].unique())
    with c_f2:
        filtro_fornecedor = st.multiselect("Fornecedor:", options=df["Fornecedor"].unique())
    with c_f3:
        filtro_resp = st.multiselect("Responsável:", options=df["Responsável"].unique())

    # Aplica os filtros na tabela
    df_show = df.copy()
    if filtro_cliente:
        df_show = df_show[df_show["Cliente"].isin(filtro_cliente)]
    if filtro_fornecedor:
        df_show = df_show[df_show["Fornecedor"].isin(filtro_fornecedor)]
    if filtro_resp:
        df_show = df_show[df_show["Responsável"].isin(filtro_resp)]

    # --- TABELA DE DADOS ---
    st.markdown("### 📋 Lista de Projetos")
    
    # Exibe a tabela bonitinha
    st.dataframe(
        df_show,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Data": st.column_config.TextColumn("Data Criação"),
            "Valor": st.column_config.TextColumn("Valor Estimado"),
            "Status": st.column_config.Column(
                "Status Atual",
                help="Status do fluxo de aprovação",
                width="medium"
            ),
        }
    )

else:
    # Caso a planilha esteja vazia ou dê erro
    st.info("📭 Nenhum projeto encontrado no banco de dados.")
    st.markdown("Vá até o menu **Escopo Dutos** para criar o primeiro projeto.")

st.markdown("---")
# Botão para forçar atualização
if st.button("🔄 Atualizar Tabela"):
    st.rerun()
