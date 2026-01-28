import streamlit as st
import pandas as pd
import utils_db
from datetime import datetime

st.set_page_config(page_title="Dashboard | SIARCON", page_icon="📊", layout="wide")

st.title("📊 Gestão de Projetos SIARCON")

# ============================================================================
# 1. ÁREA DE CRIAÇÃO DE NOVOS PROJETOS
# ============================================================================
with st.expander("➕ CADASTRAR NOVO PROJETO (Clique para abrir)", expanded=True):
    st.info("Preencha os dados básicos e selecione quais escopos farão parte desta obra.")
    
    c1, c2, c3 = st.columns([2, 2, 3])
    novo_cliente = c1.text_input("Nome do Cliente")
    nova_obra = c2.text_input("Nome da Obra")
    
    # Lista de todas as disciplinas disponíveis no sistema
    disciplinas_disponiveis = [
        "Dutos", "Hidraulica", "Eletrica", "Automacao", 
        "TAB", "Movimentacoes", "Cobre"
    ]
    
    disciplinas_selecionadas = c3.multiselect("Quais disciplinas terão escopo?", options=disciplinas_disponiveis)
    
    if st.button("🚀 CRIAR PROJETOS NO KANBAN", type="primary"):
        if not novo_cliente or not nova_obra:
            st.error("Por favor, preencha o Cliente e a Obra.")
        elif not disciplinas_selecionadas:
            st.error("Selecione pelo menos uma disciplina.")
        else:
            # Cria um projeto para cada disciplina selecionada
            count = 0
            bar = st.progress(0)
            
            for i, disc in enumerate(disciplinas_selecionadas):
                # Monta o esqueleto do projeto
                dados_novo = {
                    '_id': f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{i}", # ID único
                    'status': 'Em Elaboração',
                    'disciplina': disc,
                    'cliente': novo_cliente,
                    'obra': nova_obra,
                    'fornecedor': '', # Ainda não definido
                    'valor_total': '',
                    'data_inicio': datetime.now().strftime("%Y-%m-%d")
                }
                
                # Salva no banco de dados
                utils_db.registrar_projeto(dados_novo)
                bar.progress((i + 1) / len(disciplinas_selecionadas))
                count += 1
            
            st.success(f"✅ {count} escopos criados com sucesso! Veja abaixo no Kanban.")
            st.cache_data.clear() # Limpa memória para mostrar os novos itens
            st.rerun() # Atualiza a tela

st.divider()

# ============================================================================
# 2. VISUALIZAÇÃO KANBAN
# ============================================================================
c_tit, c_btn = st.columns([4,1])
c_tit.subheader("📌 Quadro de Acompanhamento")
if c_btn.button("🔄 Atualizar Quadro"):
    st.cache_data.clear()
    st.rerun()

# Carrega Dados do Banco
df = utils_db.listar_todos_projetos()

if df.empty:
    st.warning("Nenhum projeto encontrado no banco de dados. Use o formulário acima para criar o primeiro!")
else:
    # Métricas Rápidas
    total_proj = len(df)
    try:
        total_financeiro = df['valor_total'].apply(lambda x: float(str(x).replace('R$', '').replace('.', '').replace(',', '.').strip()) if x else 0).sum()
    except: total_financeiro = 0
    
    m1, m2 = st.columns(2)
    m1.metric("Escopos Ativos", total_proj)
    m2.metric("Valor Total Estimado", f"R$ {total_financeiro:,.2f}")

    st.markdown("---")
    
    # Colunas do Kanban
    col1, col2, col3 = st.columns(3)
    
    # --- COLUNA 1: EM ELABORAÇÃO ---
    with col1:
        st.markdown("### 📝 Em Elaboração")
        st.markdown("*(Engenharia trabalhando)*")
        filtrados = df[df['status'] == 'Em Elaboração']
        
        for idx, row in filtrados.iterrows():
            with st.expander(f"📍 {row['disciplina']} | {row['cliente']}", expanded=True):
                st.caption(f"Obra: {row['obra']}")
                st.write(f"**ID:** {row['_id']}")
                if row['fornecedor']: st.write(f"🏢 {row['fornecedor']}")
                else: st.warning("Falta Fornecedor")
                
                # Botão para mover de fase (Simulação rápida)
                if st.button("Enviar p/ Cotação ➡️", key=f"btn_go_cot_{row['_id']}"):
                    utils_db.atualizar_status_projeto(row['_id'], "Enviado para Cotação")
                    st.toast("Status Atualizado!")
                    st.cache_data.clear()
                    st.rerun()

    # --- COLUNA 2: EM COTAÇÃO ---
    with col2:
        st.markdown("### 📩 Enviado para Cotação")
        st.markdown("*(Com Suprimentos)*")
        filtrados = df[df['status'] == 'Enviado para Cotação'] # Atenção ao nome exato
        
        for idx, row in filtrados.iterrows():
            with st.container(border=True):
                st.markdown(f"**{row['disciplina']}**")
                st.text(f"{row['cliente']} - {row['obra']}")
                st.caption(f"Fornecedor: {row['fornecedor']}")
                st.caption(f"Valor: {row['valor_total']}")
                
                c_a, c_b = st.columns(2)
                if c_a.button("⬅️ Voltar", key=f"back_{row['_id']}"):
                    utils_db.atualizar_status_projeto(row['_id'], "Em Elaboração")
                    st.cache_data.clear(); st.rerun()
                if c_b.button("✅ Finalizar", key=f"end_{row['_id']}"):
                    utils_db.atualizar_status_projeto(row['_id'], "Finalizado")
                    st.cache_data.clear(); st.rerun()

    # --- COLUNA 3: FINALIZADO ---
    with col3:
        st.markdown("### 🏁 Finalizado")
        st.markdown("*(Contratado/Arquivado)*")
        filtrados = df[df['status'] == 'Finalizado'] # Atenção ao nome exato do Selectbox
        
        for idx, row in filtrados.iterrows():
            with st.expander(f"✅ {row['disciplina']} - {row['cliente']}"):
                st.write(f"Obra: {row['obra']}")
                st.success(f"Fechado: {row['valor_total']}")
