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
# 3. PAINEL DE MÉTRICAS
# ============================================================================
st.markdown("### 📊 Status Geral da Obra")
if not df_obra.empty:
    total_itens = len(df_obra)
    
    status_aguardando = [
        "Aguardando liberação - Financeiro", 
        "Aguardando liberação - Cliente", 
        "Aguardando liberação - Engenharia", 
        "Não iniciado",
        "Outros - Ver Observações" 
    ]
    status_aquisicao = ["Orçando", "Negociando", "Emitindo pedido SIARCON", "Emitindo pedido CLIENTE"]
    status_fabricacao = ["Em fabricação"]
    status_transito = ["Em transporte"]
    status_entregue = ["Entregue à obra", "Recebido na SIARCON"]
    
    df_obra['status_limpo'] = df_obra['status'].astype(str).str.strip().str.lower()
    
    aguardando = len(df_obra[df_obra['status_limpo'].isin([s.lower() for s in status_aguardando])])
    aquisicao = len(df_obra[df_obra['status_limpo'].isin([s.lower() for s in status_aquisicao])])
    fabricacao = len(df_obra[df_obra['status_limpo'].isin([s.lower() for s in status_fabricacao])])
    transito = len(df_obra[df_obra['status_limpo'].isin([s.lower() for s in status_transito])])
    entregues = len(df_obra[df_obra['status_limpo'].isin([s.lower() for s in status_entregue])])
    
    pct_entregues = f"{round((entregues/total_itens)*100)}%" if total_itens > 0 else "0%"
    
    m1, m2, m3, m4, m5, m6 = st.columns(6)
    m1.metric("Total Solicitado", total_itens)
    m2.metric("Aguardando", aguardando, delta="Pendentes / Outros", delta_color="off")
    m3.metric("Em Aquisição", aquisicao, delta="Orçamento / Negociação", delta_color="normal")
    m4.metric("Fabricação/Prep.", fabricacao, delta="Produção", delta_color="normal")
    m5.metric("Em Trânsito", transito, delta="A caminho", delta_color="normal")
    m6.metric("Entregue (% Obra)", f"{entregues} ({pct_entregues})", delta="Concluídos", delta_color="normal")
else:
    st.info("Nenhum item solicitado para esta obra ainda.")

st.divider()

# ============================================================================
# CONFIGURAÇÕES DAS TABELAS
# ============================================================================
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

# Configuração de colunas: Larguras maximizadas (width="large") para melhorar a leitura em 1 linha
config_colunas = {
    "id_item": None,  
    "obra": None,
    "status_limpo": None, 
    "excluir": st.column_config.CheckboxColumn("🗑️ Excluir", width="small", help="Marque para apagar este item do sistema"),
    "arquivado": st.column_config.CheckboxColumn("📁 Arquivar", width="small", help="Mover para o histórico de concluídos"),
    "prioridade": st.column_config.SelectboxColumn("Prioridade", options=lista_prioridades, width="small", required=True),
    "item": st.column_config.TextColumn("Item / Material", width="large", required=True),
    "data_solicitada": st.column_config.TextColumn("Data", width="small"),
    "status": st.column_config.SelectboxColumn("Status Atual", options=lista_status, width="large", required=True),
    "previsao_finalizacao": st.column_config.TextColumn("Prev. Fab", width="small"),
    "previsao_entrega": st.column_config.TextColumn("Prev. Ent", width="small"),
    "fornecedor": st.column_config.TextColumn("Fornecedor", width="medium"),
    "outros": st.column_config.TextColumn("Observações", width="large"),
    "ultima_alteracao": st.column_config.TextColumn("Última Modif.", width="small", disabled=True) 
}

ordem_colunas = [
    "excluir", "arquivado", "prioridade", "item", "data_solicitada", "status", 
    "previsao_finalizacao", "previsao_entrega", "fornecedor", "outros", "ultima_alteracao"
]

df_obra['arquivado'] = df_obra['arquivado'].astype(str)
# Coluna virtual de exclusão interativa
df_obra['excluir'] = False 

df_ativa = df_obra[df_obra['arquivado'] != "True"].reset_index(drop=True)
df_arquivada = df_obra[df_obra['arquivado'] == "True"].reset_index(drop=True)

# ============================================================================
# 4. PLANILHA DE ACOMPANHAMENTO (ATIVOS)
# ============================================================================
st.markdown("### 📝 Planilha de Acompanhamento Ativo")

if not df_ativa.empty:
    df_ativa['id_item'] = df_ativa['id_item'].astype(str)
    
    dados_ativos_editados = st.data_editor(
        df_ativa,
        column_config=config_colunas,
        column_order=ordem_colunas,
        use_container_width=True,
        num_rows="dynamic", # Permite ações nativas do Streamlit se necessário
        height=420,
        key="editor_suprimentos_ativos"
    )
else:
    st.info("Não há itens ativos pendentes para esta obra.")

# ============================================================================
# LÓGICA DE SALVAMENTO E EXCLUSÃO (BOTÃO)
# ============================================================================
state_ativos = st.session_state.get("editor_suprimentos_ativos", {})
state_arquivados = st.session_state.get("editor_suprimentos_arquivados", {})

tem_alteracao = bool(
    state_ativos.get("edited_rows") or state_ativos.get("deleted_rows") or state_ativos.get("added_rows") or
    state_arquivados.get("edited_rows") or state_arquivados.get("deleted_rows") or state_arquivados.get("added_rows")
)

col_salvar, _ = st.columns([3, 7])
if col_salvar.button("💾 Salvar Todas as Alterações", type="primary", use_container_width=True, disabled=not tem_alteracao):
    
    # Aplica alterações feitas na tabela Ativa
    if state_ativos.get("edited_rows"):
        for idx_linha, alteracoes in state_ativos["edited_rows"].items():
            id_modificado = df_ativa.loc[int(idx_linha), 'id_item']
            for col, novo_valor in alteracoes.items():
                df_ativa.loc[int(idx_linha), col] = novo_valor
            df_ativa.loc[int(idx_linha), 'ultima_alteracao'] = datetime.now().strftime("%d/%m/%Y %H:%M")
            
            idx_master = df_suprimentos[df_suprimentos['id_item'] == str(id_modificado)].index
            if not idx_master.empty:
                # Salva apenas colunas reais no master (ignora status_limpo e excluir temporários)
                colunas_reais = [c for c in df_ativa.columns if c not in ['status_limpo', 'excluir']]
                df_suprimentos.loc[idx_master[0], colunas_reais] = df_ativa.loc[int(idx_linha), colunas_reais].values

    # Aplica alterações feitas na tabela Arquivada
    if state_arquivados.get("edited_rows"):
        for idx_linha, alteracoes in state_arquivados["edited_rows"].items():
            id_modificado = df_arquivada.loc[int(idx_linha), 'id_item']
            for col, novo_valor in alteracoes.items():
                df_arquivada.loc[int(idx_linha), col] = novo_valor
            df_arquivada.loc[int(idx_linha), 'ultima_alteracao'] = datetime.now().strftime("%d/%m/%Y %H:%M")
            
            idx_master = df_suprimentos[df_suprimentos['id_item'] == str(id_modificado)].index
            if not idx_master.empty:
                colunas_reais = [c for c in df_arquivada.columns if c not in ['status_limpo', 'excluir']]
                df_suprimentos.loc[idx_master[0], colunas_reais] = df_arquivada.loc[int(idx_linha), colunas_reais].values

    # Lógica de EXCLUSÃO através do Checkbox
    ids_para_excluir = []
    
    # Captura os IDs que foram marcados com True na coluna 'excluir'
    if not df_ativa.empty:
        ids_para_excluir.extend(df_ativa[df_ativa['excluir'] == True]['id_item'].tolist())
    if not df_arquivada.empty:
        ids_para_excluir.extend(df_arquivada[df_arquivada['excluir'] == True]['id_item'].tolist())
        
    if ids_para_excluir:
        df_suprimentos = df_suprimentos[~df_suprimentos['id_item'].isin(ids_para_excluir)]

    # Limpeza final de colunas virtuais antes de ir pro Sheets
    colunas_para_remover = [c for c in ['status_limpo', 'excluir'] if c in df_suprimentos.columns]
    if colunas_para_remover:
        df_suprimentos = df_suprimentos.drop(columns=colunas_para_remover)

    if utils_db.salvar_lote_suprimentos(df_suprimentos):
        st.success("Banco de dados sincronizado! Itens marcados foram atualizados/excluídos.")
        time.sleep(1)
        st.rerun()
    else:
        st.error("Erro crítico ao salvar no Google Sheets.")

st.divider()

# ============================================================================
# 5. FORMULÁRIO RÁPIDO PARA ADICIONAR NOVO ITEM
# ============================================================================
with st.expander("➕ Solicitar Novo Item para esta Obra", expanded=False):
    with st.form("novo_item_form", clear_on_submit=True):
        c1, c2 = st.columns([3, 1])
        # Revertido para 1 linha (text_input) conforme solicitado
        nome_item = c1.text_input("Descrição do Item / Material / Equipamento")
        
        nova_prioridade = c2.selectbox("Nível de Prioridade", lista_prioridades, index=3) 
        data_sol = c2.date_input("Data da Solicitação", value=datetime.today())
        
        c3, c4 = st.columns([1, 2])
        fornecedor_sug = c3.text_input("Fornecedor Sugerido / Alvo")
        # Revertido para 1 linha (text_input) conforme solicitado
        obs_suprimentos = c4.text_input("Observações / Detalhes Adicionais")
        
        if st.form_submit_button("Adicionar Item à Lista"):
            if nome_item:
                novo_reg = {
                    "id_item": f"SUP-{datetime.now().strftime('%Y%m%d%H%M%S')}", 
                    "obra": obra_selecionada,
                    "prioridade": nova_prioridade,
                    "item": nome_item,
                    "data_solicitada": data_sol.strftime("%d/%m/%Y"),
                    "status": "Não iniciado", 
                    "previsao_finalizacao": "", 
                    "previsao_entrega": "",       
                    "fornecedor": fornecedor_sug,
                    "outros": obs_suprimentos,
                    "arquivado": "False",
                    "ultima_alteracao": datetime.now().strftime("%d/%m/%Y %H:%M")
                }
                df_suprimentos = pd.concat([df_suprimentos, pd.DataFrame([novo_reg])], ignore_index=True)
                
                col_remov = [c for c in ['status_limpo', 'excluir'] if c in df_suprimentos.columns]
                if col_remov:
                    df_suprimentos = df_suprimentos.drop(columns=col_remov)
                
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
# 6. HISTÓRICO DE ITENS CONCLUÍDOS / ARQUIVADOS
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
        num_rows="dynamic",
        height=250, 
        key="editor_suprimentos_arquivados"
    )
else:
    st.caption("Nenhum item arquivado nesta obra por enquanto.")
