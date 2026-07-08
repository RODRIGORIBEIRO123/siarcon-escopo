import streamlit as st
import pandas as pd
from datetime import datetime
import utils_db
import time

st.set_page_config(page_title="Suprimentos | SIARCON", page_icon="📦", layout="wide")

if not st.session_state.get('logado', False):
    st.error("Por favor, faça login na página inicial.")
    st.stop()

st.title("📦 Controle de Aquisições - Suprimentos")

# 1. CARREGAMENTO DOS DADOS
df_suprimentos = utils_db.listar_todos_suprimentos()

# Obter lista de obras únicas cadastradas no sistema para os filtros/inserções
df_projetos = utils_db.listar_todos_projetos()
lista_obras = sorted(df_projetos['obra'].unique().tolist()) if not df_projetos.empty else []

if not lista_obras:
    st.warning("Nenhuma obra cadastrada no painel principal. Cadastre uma obra primeiro para gerenciar suprimentos.")
    st.stop()

# 2. FILTRO POR OBRA
obra_selecionada = st.selectbox("Selecione a Obra para Visualização", lista_obras)

# Filtra os dados da obra escolhida
df_obra = df_suprimentos[df_suprimentos['obra'] == obra_selecionada].copy()

# 3. PAINEL DE METRICAS (KPIs Modernos)
st.markdown("### 📊 Status Geral da Obra")
if not df_obra.empty:
    total_itens = len(df_obra)
    entregues = len(df_obra[df_obra['status'] == "Entregue à obra"])
    em_cotacao = len(df_obra[df_obra['status'].isin(["Orçando", "Negociando"])])
    comprados = len(df_obra[df_obra['status'].isin(["Comprado", "Emitindo pedido", "Em fabricação", "Transporte"])])
    
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Total de Itens Solicitados", total_itens)
    m2.metric("Em Processo de Cotação", em_cotacao, delta="Preço/Negociação", delta_color="normal")
    m3.metric("Comprados / Em Trânsito", comprados, delta="Aguardando entrega", delta_color="off")
    m4.metric("Entregues na Obra", f"{entregues} ({round((entregues/total_itens)*100)}%)" if total_itens > 0 else "0%")
else:
    st.info("Nenhum item solicitado para esta obra ainda.")

st.divider()

# 4. FORMULÁRIO RÁPIDO PARA ADICIONAR NOVO ITEM
with st.expander("➕ Solicitar Novo Item para esta Obra", expanded=False):
    with st.form("novo_item_form", clear_on_submit=True):
        c1, c2 = st.columns([3, 1])
        nome_item = c1.text_input("Descrição do Item / Material / Equipamento")
        data_sol = c2.date_input("Data da Solicitação", value=datetime.today())
        
        c3, c4 = st.columns(2)
        fornecedor_sug = c3.text_input("Fornecedor Sugerido / Alvo (Opcional)")
        obs_suprimentos = c4.text_input("Observações / Outros")
        
        if st.form_submit_button("Adicionar Item à Lista"):
            if nome_item:
                novo_reg = {
                    "id_item": datetime.now().strftime("%Y%m%d%H%M%S%f"),
                    "obra": obra_selecionada,
                    "item": nome_item,
                    "data_solicitada": data_sol.strftime("%d/%m/%Y"),
                    "status": "Aguardando",
                    "fornecedor": fornecedor_sug,
                    "outros": obs_suprimentos,
                    "ultima_alteracao": datetime.now().strftime("%d/%m/%Y %H:%M")
                }
                # Adiciona ao dataframe geral e salva
                df_suprimentos = pd.concat([df_suprimentos, pd.DataFrame([novo_reg])], ignore_index=True)
                if utils_db.salvar_lote_suprimentos(df_suprimentos):
                    st.success("Item adicionado com sucesso!")
                    time.sleep(0.5)
                    st.rerun()
                else:
                    st.error("Erro ao salvar no banco de dados.")
            else:
                st.error("A descrição do item é obrigatória.")

# 5. MATRIZ INTERATIVA (MÁGICA DO st.data_editor)
st.markdown("### 📝 Planilha de Acompanhamento (Clique duas vezes para editar)")

# Lista oficial de status solicitada
lista_status = [
    "Aguardando", "Iniciou a compra", "Orçando", 
    "Negociando", "Comprado", "Emitindo pedido", 
    "Em fabricação", "Transporte", "Entregue à obra"
]

if not df_obra.empty:
    # Reset do index para o data_editor rastrear corretamente as linhas editadas
    df_obra = df_obra.reset_index(drop=True)
    
    # Configuração customizada das colunas da planilha
    config_colunas = {
        "id_item": None,  # Oculta o ID para o usuário final
        "obra": None,     # Oculta a obra já que está filtrada no topo
        "item": st.column_config.TextColumn("Item / Material", width="medium", required=True),
        "data_solicitada": st.column_config.TextColumn("Data Solicitada", width="small"),
        "status": st.column_config.SelectColumn("Status Atual", options=lista_status, width="medium", required=True),
        "fornecedor": st.column_config.TextColumn("Fornecedor Parceiro", width="medium"),
        "outros": st.column_config.TextColumn("Observações / Detalhes", width="large"),
        "ultima_alteracao": st.column_config.TextColumn("Última Modificação", width="medium", disabled=True) # Travado para edição manual
    }
    
    # Renderiza a planilha editável
    dados_editados = st.data_editor(
        df_obra,
        column_config=config_colunas,
        use_container_width=True,
        num_rows="programmatic", # Permite deletar linhas se necessário selecionando a caixinha lateral
        key="editor_suprimentos"
    )
    
    # 6. LÓGICA DE CAPTURA DE ALTERAÇÕES E DATA AUTOMÁTICA
    # Verifica se houve modificação no state do componente
    state_editor = st.session_state.get("editor_suprimentos", {})
    
    if state_editor.get("edited_rows") or state_editor.get("deleted_rows"):
        col_salvar, col_reset = st.columns([1, 8])
        
        if col_salvar.button("💾 Salvar Alterações", type="primary", use_container_width=True):
            # Processa linhas editadas e injeta o carimbo de data/hora
            for idx_linha, alteracoes in state_editor["edited_rows"].items():
                id_modificado = df_obra.loc[int(idx_linha), 'id_item']
                
                # Atualiza as colunas modificadas na estrutura da tela
                for col, novo_valor in alteracoes.items():
                    df_obra.loc[int(idx_linha), col] = novo_valor
                
                # Injeta a data/hora atualizada automaticamente nesta linha
                df_obra.loc[int(idx_linha), 'ultima_alteracao'] = datetime.now().strftime("%d/%m/%Y %H:%M")
                
                # Sincroniza de volta no DataFrame master global
                idx_master = df_suprimentos[df_suprimentos['id_item'] == id_modificado].index
                df_suprimentos.loc[idx_master, df_obra.columns] = df_obra.loc[int(idx_linha)].values

            # Processa linhas deletadas (caso o usuário exclua algum item)
            if state_editor["deleted_rows"]:
                for idx_linha in state_editor["deleted_rows"]:
                    id_deletado = df_obra.loc[int(idx_linha), 'id_item']
                    df_suprimentos = df_suprimentos[df_suprimentos['id_item'] != id_deletado]

            # Grava o bloco final atualizado no Google Sheets de uma só vez
            if utils_db.salvar_lote_suprimentos(df_suprimentos):
                st.success("Planilha de suprimentos atualizada com sucesso!")
                time.sleep(1)
                st.rerun()
            else:
                st.error("Erro crítico ao salvar as alterações no Google Sheets.")
else:
    st.info("Utilize a seção acima para adicionar a primeira solicitação desta obra.")
