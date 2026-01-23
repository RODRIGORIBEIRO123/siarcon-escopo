import streamlit as st
import pandas as pd
import utils_db

# --- CONFIGURAÇÃO INICIAL (DEVE SER A 1ª LINHA) ---
st.set_page_config(page_title="Dashboard | SIARCON", page_icon="📊", layout="wide")

try:
    st.title("📊 Painel de Projetos (Kanban)")

    # --- MAPEAMENTO DE PÁGINAS ---
    MAPA_PAGINAS = {
        "Dutos": "pages/1_❄️_Escopo_Dutos.py",
        "Hidráulica": "pages/2_💧_Escopo_Hidraulica.py",
        "Elétrica": "pages/3_⚡_Escopo_Eletrica.py",
        "Automação": "pages/4_🤖_Escopo_Automacao.py",
        "TAB": "pages/5_💨_Escopo_TAB.py",
        "Movimentações": "pages/6_🏗️_Escopo_Movimentacoes.py",
        "Linha de Cobre": "pages/7_🔥_Escopo_Cobre.py"
    }

    # --- 1. MENU DE CADASTRO DE OBRA ---
    with st.expander("🏗️ CADASTRAR NOVA OBRA (Gerar Escopos)", expanded=False):
        c1, c2 = st.columns(2)
        with c1: novo_cliente = st.text_input("Cliente")
        with c2: nova_obra = st.text_input("Nome da Obra")
            
        st.markdown("**Selecione os escopos:**")
        
        col_sel1, col_sel2, col_sel3 = st.columns(3)
        with col_sel1:
            check_dutos = st.checkbox("Dutos", value=True)
            check_hidra = st.checkbox("Hidráulica")
            check_eletrica = st.checkbox("Elétrica")
        with col_sel2:
            check_auto = st.checkbox("Automação")
            check_tab = st.checkbox("TAB")
        with col_sel3:
            check_mov = st.checkbox("Movimentações")
            check_cobre = st.checkbox("Linha de Cobre")
            
        if st.button("🚀 Criar Projeto"):
            if novo_cliente and nova_obra:
                lista = []
                if check_dutos: lista.append("Dutos")
                if check_hidra: lista.append("Hidráulica")
                if check_eletrica: lista.append("Elétrica")
                if check_auto: lista.append("Automação")
                if check_tab: lista.append("TAB")
                if check_mov: lista.append("Movimentações")
                if check_cobre: lista.append("Linha de Cobre")
                
                if lista:
                    with st.spinner("Criando cartões..."):
                        # Chama a função nova do utils_db
                        if hasattr(utils_db, 'criar_pacote_obra'):
                            sucesso = utils_db.criar_pacote_obra(novo_cliente, nova_obra, lista)
                            if sucesso:
                                st.success(f"✅ Obra criada com {len(lista)} escopos!")
                                st.rerun()
                            else:
                                st.error("Erro ao gravar no banco.")
                        else:
                            st.error("Erro: Seu arquivo utils_db.py está desatualizado. Atualize-o primeiro.")
                else:
                    st.warning("Selecione pelo menos um escopo.")
            else:
                st.warning("Preencha Cliente e Obra.")

    st.divider()

    if st.button("🔄 Atualizar Quadro"):
        st.rerun()

    # --- CARREGAR DADOS ---
    df = utils_db.listar_todos_projetos()

    # --- FUNÇÃO DO CARTÃO ---
    def card_projeto(row, cor_status="blue"):
        with st.container(border=True):
            st.markdown(f"**{row['Cliente']}**")
            st.caption(f"📍 {row['Obra']}")
            
            # Tratamento para colunas antigas ou vazias
            disciplina = row.get('Disciplina', 'Geral')
            if pd.isna(disciplina) or not disciplina: disciplina = "Geral"
            
            icones = {"Dutos": "❄️", "Hidráulica": "💧", "Elétrica": "⚡", "Automação": "🤖", "TAB": "💨", "Movimentações": "🏗️", "Linha de Cobre": "🔥"}
            icone = icones.get(disciplina, "📝")
            
            st.markdown(f"**{icone} {disciplina}**")
            st.markdown(f":{cor_status}[{row['Status']}]")
            
            c_edit, c_del = st.columns([0.85, 0.15])
            
            with c_edit:
                label_btn = "▶️ Iniciar" if row['Status'] == "Não Iniciado" else "✏️ Editar"
                if st.button(f"{label_btn}", key=f"btn_{row['_id_linha']}", use_container_width=True):
                    st.session_state['dados_projeto'] = row.to_dict()
                    st.session_state['modo_edicao'] = True
                    
                    # Tenta ir para a página correta
                    pagina = MAPA_PAGINAS.get(disciplina, "pages/1_❄️_Escopo_Dutos.py")
                    try:
                        st.switch_page(pagina)
                    except:
                        st.warning(f"A página '{pagina}' ainda não foi criada.")
            
            with c_del:
                if st.button("🗑️", key=f"del_{row['_id_linha']}"):
                    utils_db.excluir_projeto(row['_id_linha'])
                    st.rerun()

    # --- KANBAN ---
    if not df.empty:
        # Garante colunas mínimas para não quebrar
        if "Status" not in df.columns: df["Status"] = "Em Elaboração (Engenharia)"
        if "Disciplina" not in df.columns: df["Disciplina"] = ""
        
        c1, c2, c3, c4, c5 = st.columns(5)
        
        with c1:
            st.subheader("⚪ Não Iniciado")
            st.markdown("---")
            filtro = df[df["Status"] == "Não Iniciado"]
            for i, row in filtro.iterrows(): card_projeto(row, "grey")

        with c2:
            st.subheader("👷 Engenharia")
            st.markdown("---")
            filtro = df[df["Status"] == "Em Elaboração (Engenharia)"]
            for i, row in filtro.iterrows(): card_projeto(row, "blue")

        with c3:
            st.subheader("🚧 Obras")
            st.markdown("---")
            filtro = df[df["Status"] == "Aguardando Obras"]
            for i, row in filtro.iterrows(): card_projeto(row, "orange")

        with c4:
            st.subheader("💰 Suprimentos")
            st.markdown("---")
            lista = ["Recebido (Suprimentos)", "Enviado para Cotação", "Em Negociação"]
            filtro = df[df["Status"].isin(lista)]
            for i, row in filtro.iterrows(): card_projeto(row, "violet")

        with c5:
            st.subheader("✅ Concluídos")
            st.markdown("---")
            filtro = df[df["Status"] == "Contratação Finalizada"]
            for i, row in filtro.iterrows(): card_projeto(row, "green")

    else:
        st.info("📭 Nenhum projeto encontrado. Use o cadastro acima.")

except Exception as e:
    st.error("❌ Ocorreu um erro ao carregar o Dashboard.")
    st.code(e)
