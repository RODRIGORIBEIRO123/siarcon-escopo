import streamlit as st
import pandas as pd
import utils_db

st.set_page_config(page_title="Dashboard | SIARCON", page_icon="📊", layout="wide")
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

# --- 1. CADASTRO ---
with st.expander("🏗️ CADASTRAR NOVA OBRA", expanded=False):
    c1, c2 = st.columns(2)
    with c1: novo_cliente = st.text_input("Cliente")
    with c2: nova_obra = st.text_input("Nome da Obra")
        
    st.markdown("**Selecione os escopos:**")
    col1, col2, col3 = st.columns(3)
    with col1:
        chk_dutos = st.checkbox("Dutos", value=True)
        chk_hidra = st.checkbox("Hidráulica")
        chk_elet = st.checkbox("Elétrica")
    with col2:
        chk_auto = st.checkbox("Automação")
        chk_tab = st.checkbox("TAB")
    with col3:
        chk_mov = st.checkbox("Movimentações")
        chk_cobre = st.checkbox("Linha de Cobre")
        
    if st.button("🚀 Criar Projeto"):
        if novo_cliente and nova_obra:
            lista = []
            if chk_dutos: lista.append("Dutos")
            if chk_hidra: lista.append("Hidráulica")
            if chk_elet: lista.append("Elétrica")
            if chk_auto: lista.append("Automação")
            if chk_tab: lista.append("TAB")
            if chk_mov: lista.append("Movimentações")
            if chk_cobre: lista.append("Linha de Cobre")
            
            if lista:
                with st.spinner("Criando..."):
                    if utils_db.criar_pacote_obra(novo_cliente, nova_obra, lista):
                        st.success(f"✅ Obra criada com {len(lista)} disciplinas!")
                        st.rerun()
            else: st.warning("Selecione um escopo.")
        else: st.warning("Preencha Cliente e Obra.")

st.divider()
if st.button("🔄 Atualizar Quadro"): st.rerun()

# --- KANBAN ---
df = utils_db.listar_todos_projetos()

def card_projeto(row, cor_status="blue"):
    with st.container(border=True):
        st.markdown(f"**{row['Cliente']}**")
        st.caption(f"📍 {row['Obra']}")
        
        # Pega a disciplina garantida pelo novo utils_db
        disciplina = str(row['Disciplina']).strip() 
        if not disciplina: disciplina = "Geral"
        
        # Ícone
        icones = {"Dutos":"❄️", "Hidráulica":"💧", "Elétrica":"⚡", "Automação":"🤖", "TAB":"💨", "Movimentações":"🏗️", "Linha de Cobre":"🔥"}
        icone = icones.get(disciplina, "📝")
        
        # EXIBE A DISCIPLINA COM DESTAQUE
        st.markdown(f"### {icone} {disciplina}") 
        
        st.markdown(f":{cor_status}[{row['Status']}]")
        
        c1, c2 = st.columns([0.8, 0.2])
        with c1:
            label = "▶️ Iniciar" if row['Status'] == "Não Iniciado" else "✏️ Editar"
            if st.button(label, key=f"btn_{row['_id_linha']}", use_container_width=True):
                st.session_state['dados_projeto'] = row.to_dict()
                st.session_state['modo_edicao'] = True
                
                pagina = MAPA_PAGINAS.get(disciplina)
                if pagina:
                    try: st.switch_page(pagina)
                    except: st.error(f"Página {disciplina} não criada.")
                else:
                    st.switch_page("pages/1_❄️_Escopo_Dutos.py")
        with c2:
            if st.button("🗑️", key=f"del_{row['_id_linha']}"):
                utils_db.excluir_projeto(row['_id_linha']); st.rerun()

if not df.empty:
    c1, c2, c3, c4, c5 = st.columns(5)
    with c1:
        st.subheader("⚪ Não Iniciado")
        st.markdown("---")
        for i, r in df[df["Status"]=="Não Iniciado"].iterrows(): card_projeto(r, "grey")
    with c2:
        st.subheader("👷 Engenharia")
        st.markdown("---")
        for i, r in df[df["Status"]=="Em Elaboração (Engenharia)"].iterrows(): card_projeto(r, "blue")
    with c3:
        st.subheader("🚧 Obras")
        st.markdown("---")
        for i, r in df[df["Status"]=="Aguardando Obras"].iterrows(): card_projeto(r, "orange")
    with c4:
        st.subheader("💰 Suprimentos")
        st.markdown("---")
        for i, r in df[df["Status"].isin(["Recebido (Suprimentos)", "Enviado para Cotação", "Em Negociação"])].iterrows(): card_projeto(r, "violet")
    with c5:
        st.subheader("✅ Concluídos")
        st.markdown("---")
        for i, r in df[df["Status"]=="Contratação Finalizada"].iterrows(): card_projeto(r, "green")
else:
    st.info("Nenhum projeto encontrado.")
