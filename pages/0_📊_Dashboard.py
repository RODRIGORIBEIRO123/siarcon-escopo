import streamlit as st
import pandas as pd
import utils_db
from datetime import datetime

st.set_page_config(page_title="Dashboard | SIARCON", page_icon="📊", layout="wide")

st.title("📊 Gestão de Projetos SIARCON")

# ============================================================================
# 1. ÁREA DE CRIAÇÃO (STATUS INICIAL: NÃO INICIADO)
# ============================================================================
with st.expander("➕ CADASTRAR NOVO PROJETO", expanded=False):
    c1, c2, c3 = st.columns([2, 2, 3])
    novo_cliente = c1.text_input("Nome do Cliente")
    nova_obra = c2.text_input("Nome da Obra")
    
    disciplinas_disponiveis = [
        "Dutos", "Hidraulica", "Eletrica", "Automacao", 
        "TAB", "Movimentacoes", "Cobre"
    ]
    disciplinas_selecionadas = c3.multiselect("Disciplinas do Escopo:", options=disciplinas_disponiveis)
    
    if st.button("🚀 CRIAR PROJETOS", type="primary"):
        if not novo_cliente or not nova_obra or not disciplinas_selecionadas:
            st.error("Preencha Cliente, Obra e selecione ao menos uma disciplina.")
        else:
            count = 0
            for i, disc in enumerate(disciplinas_selecionadas):
                dados_novo = {
                    '_id': f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{i}",
                    'status': 'Não Iniciado',
                    'disciplina': disc,
                    'cliente': novo_cliente,
                    'obra': nova_obra,
                    'fornecedor': '',
                    'valor_total': '',
                    'data_inicio': datetime.now().strftime("%Y-%m-%d")
                }
                utils_db.registrar_projeto(dados_novo)
                count += 1
            
            st.success(f"{count} projetos criados em 'Não Iniciado'!")
            st.cache_data.clear()
            st.rerun()

st.divider()

# ============================================================================
# 2. KANBAN (5 COLUNAS)
# FLUXO: NÃO INICIADO > ENG > OBRAS > SUPRIMENTOS > CONCLUÍDO
# ============================================================================
if st.button("🔄 Atualizar Quadro"):
    st.cache_data.clear()
    st.rerun()

df = utils_db.listar_todos_projetos()

if df.empty:
    st.info("Nenhum projeto no quadro. Cadastre acima.")
else:
    # 5 Colunas para o novo fluxo
    col1, col2, col3, col4, col5 = st.columns(5)
    
    # --- COLUNA 1: NÃO INICIADO ---
    with col1:
        st.markdown("### 💤 Não Iniciado")
        filtrados = df[df['status'] == 'Não Iniciado']
        
        for idx, row in filtrados.iterrows():
            titulo = f"{row['disciplina']} | {row['obra']}"
            with st.container(border=True):
                st.write(f"**{titulo}**")
                st.caption(row['cliente'])
                if st.button("Iniciar (Eng) ➡️", key=f"start_{row['_id']}"):
                    utils_db.atualizar_status_projeto(row['_id'], "Em Elaboração")
                    st.cache_data.clear(); st.rerun()

    # --- COLUNA 2: ENGENHARIA (Em Elaboração) ---
    with col2:
        st.markdown("### 👷 Engenharia")
        st.caption("(Definição Técnica)")
        filtrados = df[df['status'] == 'Em Elaboração']
        
        for idx, row in filtrados.iterrows():
            titulo = f"{row['disciplina']} | {row['obra']}"
            with st.container(border=True):
                st.info(f"**{titulo}**")
                st.caption(row['cliente'])
                
                # Manda para Obras
                if st.button("Validar (Obras) ➡️", key=f"to_obras_{row['_id']}"):
                    utils_db.atualizar_status_projeto(row['_id'], "Em Análise Obras")
                    st.cache_data.clear(); st.rerun()

    # --- COLUNA 3: OBRAS (Em Análise) ---
    with col3:
        st.markdown("### 🏗️ Obras")
        st.caption("(Validação Campo)")
        # Status novo que criamos para essa etapa
        filtrados = df[df['status'] == 'Em Análise Obras']
        
        for idx, row in filtrados.iterrows():
            titulo = f"{row['disciplina']} | {row['obra']}"
            with st.container(border=True):
                st.warning(f"**{titulo}**")
                st.caption(row['cliente'])
                
                c_voltar, c_ir = st.columns(2)
                # Volta para Engenharia
                if c_voltar.button("⬅️ Eng", key=f"back_eng_from_obras_{row['_id']}"):
                    utils_db.atualizar_status_projeto(row['_id'], "Em Elaboração")
                    st.cache_data.clear(); st.rerun()
                
                # Vai para Suprimentos
                if c_ir.button("Sup ➡️", key=f"to_sup_{row['_id']}"):
                    utils_db.atualizar_status_projeto(row['_id'], "Em Cotação")
                    st.cache_data.clear(); st.rerun()

    # --- COLUNA 4: SUPRIMENTOS (Em Cotação) ---
    with col4:
        st.markdown("### 💰 Suprimentos")
        st.caption("(Cotação/Compra)")
        filtrados = df[df['status'] == 'Em Cotação']
        
        for idx, row in filtrados.iterrows():
            titulo = f"{row['disciplina']} | {row['obra']}"
            with st.container(border=True):
                st.error(f"**{titulo}**") # Vermelho/Rosa para destacar Suprimentos
                st.caption(row['cliente'])
                
                if row['fornecedor']: st.write(f"🏢 {row['fornecedor']}")
                if row['valor_total']: st.write(f"💲 {row['valor_total']}")

                # Botões de Devolução
                c_v1, c_v2 = st.columns(2)
                if c_v1.button("⬅️ Eng", key=f"ret_eng_{row['_id']}"):
                    utils_db.atualizar_status_projeto(row['_id'], "Em Elaboração")
                    st.cache_data.clear(); st.rerun()
                
                if c_v2.button("⬅️ Obras", key=f"ret_obras_{row['_id']}"):
                    utils_db.atualizar_status_projeto(row['_id'], "Em Análise Obras")
                    st.cache_data.clear(); st.rerun()

                # Botão de Conclusão (destacado)
                if st.button("✅ Concluir Compra", key=f"finish_{row['_id']}", type="primary"):
                    utils_db.atualizar_status_projeto(row['_id'], "Concluído")
                    st.cache_data.clear(); st.rerun()

    # --- COLUNA 5: CONCLUÍDO ---
    with col5:
        st.markdown("### ✅ Concluído")
        filtrados = df[df['status'] == 'Concluído']
        
        for idx, row in filtrados.iterrows():
            titulo = f"{row['disciplina']} | {row['obra']}"
            with st.expander(titulo):
                st.write(f"**Cliente:** {row['cliente']}")
                st.success(f"**Forn:** {row['fornecedor']}")
                st.write(f"**Valor:** {row['valor_total']}")
