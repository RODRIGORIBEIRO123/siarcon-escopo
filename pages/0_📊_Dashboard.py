import streamlit as st
import pandas as pd
import utils_db

st.set_page_config(page_title="Dashboard | SIARCON", page_icon="📊", layout="wide")
st.title("📊 Painel de Projetos (Kanban)")

# --- ATUALIZAÇÃO ---
if st.button("🔄 Atualizar Quadro"): st.rerun()

# --- CARREGA DADOS ---
df = utils_db.listar_todos_projetos()

if not df.empty:
    if "Status" not in df.columns: df["Status"] = "Em Elaboração (Engenharia)"
    
    # --- MÉTRICAS DE TOPO ---
    total = len(df)
    # Contagem rápida para Obras
    pendencia_obras = len(df[df["Status"].str.contains("Aguardando Obras", na=False)])
    
    m1, m2 = st.columns([1, 3])
    m1.metric("Total de Projetos", total)
    if pendencia_obras > 0:
        m2.warning(f"⚠️ Atenção Obras: Existem {pendencia_obras} projetos na sua fila!")
    else:
        m2.success("✅ Fila de Obras Zerada! O fluxo está fluindo.")

    st.divider()

    # --- KANBAN (4 COLUNAS) ---
    col_eng, col_obras, col_supr, col_fim = st.columns(4)
    
    # ------------------------------------------------------------
    # 1. RAIA: ENGENHARIA (NASCIMENTO)
    # ------------------------------------------------------------
    with col_eng:
        st.subheader("👷 Engenharia")
        st.markdown("---")
        
        filtro_eng = df[df["Status"] == "Em Elaboração (Engenharia)"]
        
        for index, row in filtro_eng.iterrows():
            with st.container(border=True):
                st.markdown(f"**{row['Cliente']}**")
                st.caption(f"📍 {row['Obra']}")
                st.info("Em Elaboração")
                
                if st.button(f"✏️ Editar", key=f"btn_eng_{row['_id_linha']}"):
                    st.session_state['dados_projeto'] = row.to_dict()
                    st.session_state['modo_edicao'] = True
                    st.switch_page("pages/1_❄️_Escopo_Dutos.py")

    # ------------------------------------------------------------
    # 2. RAIA: OBRAS (VALIDAÇÃO)
    # ------------------------------------------------------------
    with col_obras:
        st.subheader("🚧 Obras")
        st.markdown("---")
        
        filtro_obras = df[df["Status"] == "Aguardando Obras"]
        
        for index, row in filtro_obras.iterrows():
            with st.container(border=True):
                st.markdown(f"**{row['Cliente']}**")
                st.caption(f"📍 {row['Obra']}")
                st.warning("⚠️ Validar Escopo")
                
                if st.button(f"✏️ Validar", key=f"btn_obr_{row['_id_linha']}"):
                    st.session_state['dados_projeto'] = row.to_dict()
                    st.session_state['modo_edicao'] = True
                    st.switch_page("pages/1_❄️_Escopo_Dutos.py")

    # ------------------------------------------------------------
    # 3. RAIA: SUPRIMENTOS (COTAÇÃO)
    # ------------------------------------------------------------
    with col_supr:
        st.subheader("💰 Suprimentos")
        st.markdown("---")
        
        lista_suprimentos = ["Recebido (Suprimentos)", "Enviado para Cotação", "Em Negociação"]
        filtro_supr = df[df["Status"].isin(lista_suprimentos)]
        
        for index, row in filtro_supr.iterrows():
            with st.container(border=True):
                st.markdown(f"**{row['Cliente']}**")
                st.caption(f"📍 {row['Obra']}")
                
                # Mostra o Fornecedor (ou Genérico)
                fornecedor = row.get('Fornecedor', '')
                if not fornecedor or fornecedor == "PROPONENTE DE DUTOS":
                    st.text("🏢 Múltiplos Proponentes")
                else:
                    st.text(f"🏢 {fornecedor}")
                
                # Tag de Status Específica
                status_atual = row['Status']
                if "Recebido" in status_atual: st.info("📥 Recebido")
                elif "Cotação" in status_atual: st.markdown(":orange[📤 Em Cotação]")
                elif "Negociação" in status_atual: st.markdown(":violet[🤝 Negociação]")
                
                if st.button(f"✏️ Atualizar", key=f"btn_sup_{row['_id_linha']}"):
                    st.session_state['dados_projeto'] = row.to_dict()
                    st.session_state['modo_edicao'] = True
                    st.switch_page("pages/1_❄️_Escopo_Dutos.py")

    # ------------------------------------------------------------
    # 4. RAIA: CONCLUÍDOS
    # ------------------------------------------------------------
    with col_fim:
        st.subheader("✅ Concluídos")
        st.markdown("---")
        
        filtro_fim = df[df["Status"] == "Contratação Finalizada"]
        
        for index, row in filtro_fim.iterrows():
            with st.container(border=True):
                st.markdown(f"**{row['Cliente']}**")
                st.caption(f"📍 {row['Obra']}")
                st.success(f"🤝 {row.get('Fornecedor', 'Fechado')}")
                
                val = row.get('Valor', '')
                if val: st.caption(f"Valor: {val}")
                
                # Botão apenas visualização
                if st.button(f"👁️ Ver Detalhes", key=f"btn_fim_{row['_id_linha']}"):
                    st.session_state['dados_projeto'] = row.to_dict()
                    st.session_state['modo_edicao'] = True
                    st.switch_page("pages/1_❄️_Escopo_Dutos.py")

else:
    st.info("📭 Nenhum projeto encontrado no banco de dados.")
