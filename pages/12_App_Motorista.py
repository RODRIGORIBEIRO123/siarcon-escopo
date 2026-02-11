import streamlit as st
import pandas as pd
from datetime import date
import urllib.parse
import utils_db
import time

# Configuração para parecer App Mobile
st.set_page_config(page_title="App Almoxarife", page_icon="🚚")

# Login Simplificado (Opcional, pode usar o login geral)
if 'logado' not in st.session_state or not st.session_state['logado']:
    st.warning("🔒 Faça login primeiro.")
    st.stop()

st.title("🚚 Minha Rota")

# Filtro de Data (Padrão Hoje)
data_hoje = date.today().strftime("%Y-%m-%d")

# Carrega as rotas
df = utils_db.listar_rotas_dia(data_hoje)

if df.empty:
    st.info("🌴 Nenhuma tarefa para hoje.")
    st.stop()

# Filtra apenas Pendentes no topo, Concluídas embaixo
df_pendente = df[df['status'] != 'Concluído']
df_concluido = df[df['status'] == 'Concluído']

# BARRA DE PROGRESSO
total = len(df)
feitos = len(df_concluido)
progresso = feitos / total if total > 0 else 0
st.progress(progresso, text=f"Progresso: {feitos}/{total}")

st.markdown("---")

# --- LISTA DE TAREFAS (PENDENTES) ---
if not df_pendente.empty:
    st.subheader("📍 Próximas Paradas")
    
    for idx, row in df_pendente.iterrows():
        # Card Visual
        with st.container(border=True):
            c1, c2 = st.columns([3, 1])
            
            # Ícone baseado no tipo
            icone = "📦" if row['tipo'] == "Entrega" else "inbox_tray" if row['tipo'] == "Coleta" else "🛠️"
            if row['tipo'] == "Coleta": icone = "📥"
            
            c1.markdown(f"**{row['ordem']}º - {row['cliente']}**")
            c1.caption(f"{icone} {row['tipo']}")
            c1.write(f"📍 {row['endereco']}")
            if row['obs']:
                c1.info(f"Obs: {row['obs']}")
            
            # Link para Waze/Google Maps
            endereco_encoded = urllib.parse.quote(row['endereco'])
            link_waze = f"https://waze.com/ul?q={endereco_encoded}"
            link_gmaps = f"https://www.google.com/maps/dir/?api=1&destination={endereco_encoded}"
            
            # Botões de Ação
            col_b1, col_b2 = st.columns(2)
            
            # Botão Navegar (Abre nova aba)
            col_b1.link_button("🗺️ Navegar (Maps)", link_gmaps, use_container_width=True)
            
            # Botão Concluir
            if col_b2.button("✅ Concluir", key=f"btn_{row['_id']}"):
                if utils_db.concluir_parada(row['_id']):
                    st.toast(f"Parada {row['ordem']} concluída!")
                    time.sleep(1)
                    st.rerun()
                else:
                    st.error("Erro ao atualizar.")

else:
    st.success("🎉 Todas as tarefas de hoje foram concluídas!")

# --- HISTÓRICO (CONCLUÍDAS) ---
if not df_concluido.empty:
    with st.expander("📜 Ver Tarefas Concluídas"):
        for idx, row in df_concluido.iterrows():
            st.markdown(f"~~{row['ordem']}º - {row['cliente']}~~ (Às {row.get('hora_conclusao', '-')})")
