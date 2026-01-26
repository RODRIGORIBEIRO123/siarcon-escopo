import streamlit as st
import pandas as pd
import utils_db
import os

st.set_page_config(page_title="Dashboard SIARCON", page_icon="📊", layout="wide")

# ==================================================
# 🕵️‍♂️ ÁREA DE DIAGNÓSTICO (TEMPORÁRIA)
# ==================================================
st.warning("🕵️‍♂️ MODO DE DIAGNÓSTICO ATIVADO")
st.write("O sistema encontrou estes arquivos na pasta 'pages':")

arquivos_reais = []
try:
    arquivos_reais = sorted([f for f in os.listdir("pages") if f.endswith(".py")])
    st.code(arquivos_reais)
except Exception as e:
    st.error(f"Erro ao ler pasta pages: {e}")

st.divider()
# ==================================================

# --- MAPA DE ARQUIVOS (TENTATIVA PADRÃO) ---
# Tentei adivinhar que seus arquivos estão como '1_Dutos.py', etc.
# Se a lista azul acima mostrar algo diferente, vamos ajustar AQUI.
MAPA_PAGINAS = {
    # Dutos
    "Geral": "pages/1_Dutos.py",
    "Dutos": "pages/1_Dutos.py",
    
    # Demais (Nomes no Banco -> Nome do Arquivo)
    "Hidráulica": "pages/2_Hidraulica.py",
    "Elétrica": "pages/3_Eletrica.py",
    "Automação": "pages/4_Automacao.py",
    "TAB": "pages/5_TAB.py",
    "Movimentações": "pages/6_Movimentacoes.py",
    "Linha de Cobre": "pages/7_Cobre.py"
}

# --- FUNÇÃO DE NAVEGAÇÃO ---
def ir_para_edicao(row):
    disciplina = row['Disciplina']
    
    if disciplina in MAPA_PAGINAS:
        arquivo_destino = MAPA_PAGINAS[disciplina]
        
        # Verifica se existe
        if os.path.exists(arquivo_destino):
            st.session_state['dados_projeto'] = row.to_dict()
            st.session_state['modo_edicao'] = True
            st.switch_page(arquivo_destino)
        else:
            # ERRO DETALHADO
            st.error(f"🚨 O sistema tentou abrir: '{arquivo_destino}'")
            st.error("Mas esse arquivo NÃO existe.")
            st.info(f"Compare o nome acima com a lista azul no topo da página.")
    else:
        st.error(f"❌ A disciplina '{disciplina}' não está no MAPA_PAGINAS.")

# --- INTERFACE ---
st.title("📊 Dashboard de Contratos")

df = utils_db.listar_todos_projetos()

# Criar Nova Obra
with st.expander("➕ Criar Novo Pacote de Obra"):
    with st.form("form_nova_obra"):
        c1, c2 = st.columns(2)
        novo_cliente = c1.text_input("Cliente")
        nova_obra = c2.text_input("Nome da Obra")
        
        opcoes_disciplinas = [
            "Dutos", "Hidráulica", "Elétrica", "Automação", 
            "TAB", "Movimentações", "Linha de Cobre"
        ]
        disciplinas_selecionadas = st.multiselect("Quais escopos farão parte?", options=opcoes_disciplinas)
        
        if st.form_submit_button("🚀 Criar Pacote"):
            if utils_db.criar_pacote_obra(novo_cliente, nova_obra, disciplinas_selecionadas):
                st.success("Criado! Atualize a página."); st.rerun()
            else: st.error("Erro ao criar.")

st.divider()

# Kanban
if not df.empty:
    c_filt1, c_filt2 = st.columns(2)
    lista_clientes = sorted(list(df['Cliente'].unique())) if 'Cliente' in df.columns else []
    filtro_cliente = c_filt1.selectbox("Filtrar Cliente:", ["Todos"] + lista_clientes)
    
    if filtro_cliente != "Todos": df = df[df['Cliente'] == filtro_cliente]

    colunas_status = st.columns(3)
    grupos = {
        "🔴 A Fazer": ["Não Iniciado", "Aguardando Obras"],
        "🟡 Em Andamento": ["Em Elaboração (Engenharia)", "Recebido (Suprimentos)", "Enviado para Cotação", "Em Negociação"],
        "🟢 Concluído": ["Contratação Finalizada"]
    }

    for i, (grupo_nome, status_grupo) in enumerate(grupos.items()):
        with colunas_status[i]:
            st.markdown(f"### {grupo_nome}")
            df_grupo = df[df['Status'].isin(status_grupo)]
            
            for index, row in df_grupo.iterrows():
                with st.container(border=True):
                    d_nome = "Dutos (Antigo)" if row['Disciplina'] == "Geral" else row['Disciplina']
                    
                    st.markdown(f"**{row['Obra']}**")
                    st.caption(f"{row['Cliente']} | {d_nome}")
                    
                    if row['Fornecedor']: st.text(f"🏢 {row['Fornecedor']}")
                    
                    if st.button(f"✏️ Editar", key=f"btn_{row['_id_linha']}"):
                        ir_para_edicao(row)
else:
    st.info("Nenhum projeto encontrado.")
