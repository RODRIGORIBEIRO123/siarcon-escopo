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

# 1. CARREGAMENTO DOS DADOS E TRATAMENTO DE COLUNAS NOVAS
df_suprimentos = utils_db.listar_todos_suprimentos()

# Garante a existência de todas as colunas necessárias, incluindo a flag de arquivamento
for col_nova in ['previsao_finalizacao', 'previsao_entrega', 'prioridade', 'arquivado']:
    if col_nova not in df_suprimentos.columns:
        df_suprimentos[col_nova] = "False" if col_nova == 'arquivado' else ""

df_projetos = utils_db.listar_todos_projetos()
lista_obras = sorted(df_projetos['obra'].unique().tolist()) if not df_projetos.empty else []

if not lista_obras:
    st.warning("Nenhuma obra cadastrada. Utilize o menu lateral esquerdo para cadastrar a primeira obra.")
    st.stop()

# 2. FILTRO POR OBRA
obra_selecionada = st.selectbox("Selecione a Obra para Visualização", lista_obras)

# Filtra os dados da obra escolhida
df_obra = df_suprimentos[df_suprimentos['obra'] == obra_selecionada].copy()

# ============================================================================
# 3. PAINEL DE MÉTRICAS EVOLUÍDO (CONFORME PRINT 1)
# ============================================================================
st.markdown("### 📊 Status Geral da Obra")
if not df_obra.empty:
    total_itens = len(df_obra)
    
    # Agrupamentos exatos solicitados para alimentar os indicadores
    status_aguardando = ["Aguardando liberação - Financeiro", "Aguardando liberação - Cliente", "Aguardando liberação - Engenharia", "Não iniciado"]
    status_aquisicao = ["Orçando", "Negociando", "Emitindo pedido SIARCON", "Emitindo pedido CLIENTE"]
    status_fabricacao = ["Em fabricação"]
    status_transito = ["Em transporte"]
    status_entregue = ["Entregue à obra", "Recebido na SIARCON"]
    
    aguardando = len(df_obra[df_obra['status'].isin(status_aguardando)])
    aquisicao = len(df_obra[df_obra['status'].isin(status_aquisicao)])
    fabricacao = len(df_obra[df_obra['status'].isin(status_fabricacao)])
    transito = len(df_obra[df_obra['status'].isin(status_transito)])
    entregues = len(df_obra[df_obra['status'].isin(status_entregue)])
    
    pct_entregues = f"{round((entregues/total_itens)*100)}%" if total_itens > 0 else "0%"
    
    # Exibição em 6 colunas perfeitamente distribuídas
    m1, m2, m3, m4, m5, m6 = st.columns(6)
    m1.metric("Total Solicitado", total_itens)
    m2.metric("Aguardando", aguardando)
    m3.metric("Em Aquisição", aquisicao)
    m4.metric("Fabricação/Prep.", fabricacao)
    m5.metric("Em Trânsito", transito)
    m6.metric("Entregue (% Obra)", f"{entregues} ({pct_entregues})")
else:
    st.info("Nenhum item solicitado para esta obra ainda.")

st.divider()

# Listas Oficiais de Validação para as tabelas
lista_status = [
    "Não iniciado",
    "Aguardando liberação - Cliente",
    "Aguardando liberação - Engenharia",
    "Aguardando liberação - Financeiro",
    "Orçando",
    "Negociando",
    "Emitindo pedido SIARCON",
    "Emitindo pedido CLIENTE",
    "Em fabricação",
    "Em transporte",
    "Entregue à obra",
    "Recebido na SIARCON",
    "Outros - Ver Observações"
]

lista_prioridades = ["🔴 Urgente", "🟠 Alta", "🟡 Média", "🟢 Baixa"]

# Configuração compartilhada de visualização das colunas
config_colunas = {
    "id_item": None,  
    "obra": None,
    "arquivado": st.column_config.CheckboxColumn("Arquivar", width="small", help="Marque para mover este item concluído para a tabela de histórico abaixo"),
    "prioridade": st.column_config.SelectboxColumn("Prioridade", options=lista_prioridades, width="small", required=True),
    "item": st.column_config.TextColumn("Item / Material", width="large", required=True),
    "data_solicitada": st.column_config.TextColumn("Data Solicitada", width="small"),
    "status": st.column_config.SelectboxColumn("Status Atual", options=lista_status, width="medium", required=True),
    "previsao_finalizacao": st.column_config.TextColumn("Prev. Fabrica", width="small"),
    "previsao_entrega": st.column_config.TextColumn("Prev. Entrega", width="small"),
    "fornecedor": st.column_config.TextColumn("Fornecedor Parceiro", width="medium"),
    "outros": st.column_config.TextColumn("Observações / Detalhes", width="large"),
    "ultima_alteracao": st.column_config.TextColumn("Última Modificação", width="medium", disabled=True) 
}

ordem_colunas = [
    "arquivado", "prioridade", "item", "data_solicitada", "status", 
    "previsao_finalizacao", "previsao_entrega", "fornecedor", "outros", "ultima_alteracao"
]

# Segrega os dados em Ativos e Arquivados baseado na Flag
df_obra['arquivado'] = df_obra['arquivado'].astype(str)
df_ativa = df_obra[df_obra['arquivado'] != "True"].reset_index(drop=True)
df_arquivada = df_obra[df_obra['arquivado'] == "True"].reset_index(drop=True)

# ============================================================================
# 4. PLANILHA DE ACOMPANHAMENTO (ATIVOS) - 10 LINHAS MÍNIMAS
# ============================================================================
st.markdown("### 📝 Planilha de Acompanhamento Ativo")

if not df_ativa.empty:
    df_ativa['id_item'] = df_ativa['id_item'].astype(str)
    
    # height=420 garante espaço nativo para o header + 10 linhas visíveis antes do scroll
    dados_ativos_editados = st.data_editor(
        df_ativa,
        column_config=config_colunas,
        column_order=ordem_colunas,
        use_container_width=True,
        num_rows="programmatic", 
        height=420,
        key="editor_suprimentos_ativos"
    )
else:
    st.info("Não há itens ativos pendentes para esta obra.")

# ============================================================================
# BOTÃO DE SALVAMENTO (SEMPRE VISÍVEL LOGO ABAIXO DA TABELA PRINCIPAL)
# ============================================================================
state_ativos = st.session_state.get("editor_suprimentos_ativos", {})
state_arquivados = st.session_state.get("editor_suprimentos_arquivados", {})

# O botão avalia edições em ambas as tabelas para liberar o clique
tem_alteracao = bool(
    state_ativos.get("edited_rows") or state_ativos.get("deleted_rows") or
    state_arquivados.get("edited_rows") or state_arquivados.get("deleted_rows")
)

col_salvar, _ = st.columns([3, 7])
# SEMPRE VISÍVEL: Fica desativado (cinza) se não houver edição, prevenindo cliques nulos
if col_salvar.button("💾 Salvar Todas as Alterações na Planilha", type="primary", use_container_width=True, disabled=not tem_alteracao):
    
    # Processa alterações da tabela Ativa
    if state_ativos.get("edited_rows"):
        for idx_linha, alteracoes in state_ativos["edited_rows"].items():
            id_modificado = df_ativa.loc[int(idx_linha), 'id_item']
            for col, novo_valor in alteracoes.items():
                df_ativa.loc[int(idx_linha), col] = novo_valor
            df_ativa.loc[int(idx_linha), 'ultima_alteracao'] = datetime.now().strftime("%d/%m/%Y %H:%M")
            
            idx_master = df_suprimentos[df_suprimentos['id_item'] == str(id_modificado)].index
            if not idx_master.empty:
                df_suprimentos.loc[idx_master[0], df_ativa.columns] = df_ativa.loc[int(idx_linha)].values

    # Processa alterações da tabela do Histórico
    if state_arquivados.get("edited_rows"):
        for idx_linha, alteracoes in state_arquivados["edited_rows"].items():
            id_modificado = df_arquivada.loc[int(idx_linha), 'id_item']
            for col, novo_valor in alteracoes.items():
                df_arquivada.loc[int(idx_linha), col] = novo_valor
            df_arquivada.loc[int(idx_linha), 'ultima_alteracao'] = datetime.now().strftime("%d/%m/%Y %H:%M")
            
            idx_master = df_suprimentos[df_suprimentos['id_item'] == str(id_modificado)].index
            if not idx_master.empty:
                df_suprimentos.loc[idx_master[0], df_arquivada.columns] = df_arquivada.loc[int(idx_linha)].values

    # Processa exclusões
    for state, df_ref in [(state_ativos, df_ativa), (state_arquivados, df_arquivada)]:
        if state.get("deleted_rows"):
            for idx_linha in state["deleted_rows"]:
                id_deletado = df_ref.loc[int(idx_linha), 'id_item']
                df_suprimentos = df_suprimentos[df_suprimentos['id_item'] != str(id_deletado)]

    if utils_db.salvar_lote_suprimentos(df_suprimentos):
        st.success("Banco de dados sincronizado com sucesso!")
        time.sleep(0.8)
        st.rerun()
    else:
        st.error("Erro crítico ao salvar no Google Sheets.")

st.divider()

# ============================================================================
# 5. FORMULÁRIO RÁPIDO PARA ADICIONAR NOVO ITEM (COM PADRÕES ATUALIZADOS)
# ============================================================================
with st.expander("➕ Solicitar Novo Item para esta Obra", expanded=False):
    with st.form("novo_item_form", clear_on_submit=True):
        c1, c2 = st.columns([3, 1])
        nome_item = c1.text_area("Descrição do Item / Material / Equipamento (2 linhas de exibição)", height=70)
        
        # Padrões aplicados: Prioridade Baixa (índice 3) e Status inicial "Não iniciado"
        nova_prioridade = c2.selectbox("Nível de Prioridade", lista_prioridades, index=3) 
        data_sol = c2.date_input("Data da Solicitação", value=datetime.today())
        
        c3, c4 = st.columns([1, 2])
        fornecedor_sug = c3.text_input("Fornecedor Sugerido / Alvo")
        obs_suprimentos = c4.text_area("Observações / Detalhes Adicionais", height=70)
        
        if st.form_submit_button("Adicionar Item à Lista"):
            if nome_item:
                novo_reg = {
                    "id_item": f"SUP-{datetime.now().strftime('%Y%m%d%H%M%S')}", 
                    "obra": obra_selecionada,
                    "prioridade": nova_prioridade,
                    "item": nome_item,
                    "data_solicitada": data_sol.strftime("%d/%m/%Y"),
                    "status": "Não iniciado", # Definição padrão solicitada
                    "previsao_finalizacao": "", 
                    "previsao_entrega": "",       
                    "fornecedor": fornecedor_sug,
                    "outros": obs_suprimentos,
                    "arquivado": "False",
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

st.divider()

# ============================================================================
# 6. HISTÓRICO DE ITENS CONCLUÍDOS / ARQUIVADOS (TABELA DE BAIXO)
# ============================================================================
st.markdown("### 🗃️ Histórico de Itens Concluídos / Arquivados")
st.caption("Esta tabela exibe os itens que foram finalizados e movidos usando a flag 'Arquivar'.")

if not df_arquivada.empty:
    df_arquivada['id_item'] = df_arquivada['id_item'].astype(str)
    
    st.data_editor(
        df_arquivada,
        column_config=config_colunas,
        column_order=ordem_colunas,
        use_container_width=True,
        num_rows="programmatic",
        height=250, # Altura menor por ser um histórico secundário
        key="editor_suprimentos_arquivados"
    )
else:
    st.caption("Nenhum item arquivado nesta obra por enquanto.")
