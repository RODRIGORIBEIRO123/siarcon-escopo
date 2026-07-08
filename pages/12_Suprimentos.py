import streamlit as st
import pandas as pd
from datetime import datetime
import utils_db
import time

st.set_page_config(page_title="Suprimentos | SIARCON", page_icon="📦", layout="wide")

if not st.session_state.get('logado', False):
    st.error("Por favor, faça login na página inicial.")
    st.stop()

# ============================================================================
# MENU LATERAL - CADASTRO RÁPIDO DE OBRA
# ============================================================================
with st.sidebar:
    st.markdown("### 🏗️ Cadastrar Nova Obra")
    st.caption("Adicione uma obra rapidamente para iniciar as cotações.")
    with st.form("cad_obra_rapido", clear_on_submit=True):
        novo_cliente = st.text_input("Cliente")
        nova_obra = st.text_input("Nome da Obra")
        if st.form_submit_button("Cadastrar Obra"):
            if novo_cliente and nova_obra:
                projeto_base = {
                    "cliente": novo_cliente,
                    "obra": nova_obra,
                    "disciplina": "Suprimentos", 
                    "status": "Não Iniciado",
                    "prazo": datetime.now().strftime("%Y-%m-%d"),
                    "criado_por": st.session_state.get('usuario_atual', 'Sistema')
                }
                utils_db.salvar_projeto(projeto_base)
                st.success("Obra cadastrada com sucesso!")
                time.sleep(1)
                st.rerun()
            else:
                st.error("Preencha Cliente e Obra.")

# ============================================================================
# CORPO PRINCIPAL DA PÁGINA
# ============================================================================
st.title("📦 Controle de Aquisições - Suprimentos")

# 1. CARREGAMENTO DOS DADOS
df_suprimentos = utils_db.listar_todos_suprimentos()

# Rede de segurança: Garante a existência das novas colunas se não existirem no Sheets
for col_nova in ['previsao_finalizacao', 'previsao_entrega']:
    if col_nova not in df_suprimentos.columns:
        df_suprimentos[col_nova] = ""

# Obter lista de obras únicas cadastradas no sistema
df_projetos = utils_db.listar_todos_projetos()
lista_obras = sorted(df_projetos['obra'].unique().tolist()) if not df_projetos.empty else []

if not lista_obras:
    st.warning("Nenhuma obra cadastrada. Utilize o menu lateral esquerdo para cadastrar a primeira obra.")
    st.stop()

# 2. FILTRO POR OBRA
obra_selecionada = st.selectbox("Selecione a Obra para Visualização", lista_obras)

# Filtra os dados da obra escolhida
df_obra = df_suprimentos[df_suprimentos['obra'] == obra_selecionada].copy()

# 3. PAINEL DE METRICAS
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

# ============================================================================
# 4. MATRIZ INTERATIVA WITH NEW COLUMNS
# ============================================================================
st.markdown("### 📝 Planilha de Acompanhamento (Clique duas vezes para editar)")

lista_status = [
    "Aguardando", "Iniciou a compra", "Orçando", 
    "Negociando", "Comprado", "Emitindo pedido", 
    "Em fabricação", "Transporte", "Entregue à obra"
]

if not df_obra.empty:
    df_obra = df_obra.reset_index(drop=True)
    df_obra['id_item'] = df_obra['id_item'].astype(str)
    
    # Configuração das colunas incluindo as duas novas colunas solicitadas
    config_colunas = {
        "id_item": None,  
        "obra": None,     
        "item": st.column_config.TextColumn("Item / Material", width="medium", required=True),
        "data_solicitada": st.column_config.TextColumn("Data Solicitada", width="small"),
        "status": st.column_config.SelectboxColumn("Status Atual", options=lista_status, width="medium", required=True),
        "previsao_finalizacao": st.column_config.TextColumn("Previsão Finalização", width="small", help="Data prevista de término da fabricação ou faturamento"),
        "previsao_entrega": st.column_config.TextColumn("Previsão Entrega", width="small", help="Data prevista de chegada na obra"),
        "fornecedor": st.column_config.TextColumn("Fornecedor Parceiro", width="medium"),
        "outros": st.column_config.TextColumn("Observações / Detalhes", width="large"),
        "ultima_alteracao": st.column_config.TextColumn("Última Modificação", width="medium", disabled=True) 
    }
    
    # Define a ordem visual exata das colunas para melhor leitura
    ordem_colunas = [
        "item", "data_solicitada", "status", "previsao_finalizacao", 
        "previsao_entrega", "fornecedor", "outros", "ultima_alteracao"
    ]
    
    dados_editados = st.data_editor(
        df_obra,
        column_config=config_colunas,
        column_order=ordem_colunas,
        use_container_width=True,
        num_rows="programmatic", 
        key="editor_suprimentos"
    )
    
    # LÓGICA DE CAPTURA DE ALTERAÇÕES
    state_editor = st.session_state.get("editor_suprimentos", {})
    
    if state_editor.get("edited_rows") or state_editor.get("deleted_rows"):
        col_salvar, col_reset = st.columns([1, 8])
        
        if col_salvar.button("💾 Salvar Alterações", type="primary", use_container_width=True):
            for idx_linha, alteracoes in state_editor["edited_rows"].items():
                id_modificado = df_obra.loc[int(idx_linha), 'id_item']
                
                for col, novo_valor in alteracoes.items():
                    df_obra.loc[int(idx_linha), col] = novo_valor
                
                df_obra.loc[int(idx_linha), 'ultima_alteracao'] = datetime.now().strftime("%d/%m/%Y %H:%M")
                
                idx_master = df_suprimentos[df_suprimentos['id_item'] == str(id_modificado)].index
                if not idx_master.empty:
                    df_suprimentos.loc[idx_master[0], df_obra.columns] = df_obra.loc[int(idx_linha)].values

            if state_editor["deleted_rows"]:
                for idx_linha in state_editor["deleted_rows"]:
                    id_deletado = df_obra.loc[int(idx_linha), 'id_item']
                    df_suprimentos = df_suprimentos[df_suprimentos['id_item'] != str(id_deletado)]

            if utils_db.salvar_lote_suprimentos(df_suprimentos):
                st.success("Planilha de suprimentos atualizada com sucesso!")
                time.sleep(1)
                st.rerun()
            else:
                st.error("Erro crítico ao salvar as alterações no Google Sheets.")
else:
    st.info("Utilize a seção abaixo para adicionar a primeira solicitação desta obra.")

st.divider()

# ============================================================================
# 5. FORMULÁRIO RÁPIDO PARA ADICIONAR NOVO ITEM
# ============================================================================
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
                    "id_item": f"SUP-{datetime.now().strftime('%Y%m%d%H%M%S')}", 
                    "obra": obra_selecionada,
                    "item": nome_item,
                    "data_solicitada": data_sol.strftime("%d/%m/%Y"),
                    "status": "Aguardando",
                    "previsao_finalizacao": "", # Inicia vazio para preenchimento posterior na tabela
                    "previsao_entrega": "",       # Inicia vazio para preenchimento posterior na tabela
                    "fornecedor": fornecedor_sug,
                    "outros": obs_suprimentos,
                    "ultima_alteracao": datetime.now().strftime("%d/%m/%Y %H:%M")
                }
                df_suprimentos = pd.concat([df_suprimentos, pd.DataFrame([novo_reg])], ignore_index=True)
                if utils_db.salvar_lote_suprimentos(df_suprimentos):
                    st.success("Item adicionado com sucesso!")
                    time.sleep(0.5)
                    st.rerun()
                else:
                    st.error("Erro ao salvar no banco de dados.")
            else:
                st.error("A descrição do item é obrigatória.")
