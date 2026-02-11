import streamlit as st
import pandas as pd
from datetime import date, datetime
import utils_db

# Tenta importar folium (mapas)
try:
    import folium
    from streamlit_folium import st_folium
    TEM_MAPA = True
except:
    TEM_MAPA = False

if 'logado' not in st.session_state or not st.session_state['logado']:
    st.warning("🔒 Acesso negado."); st.stop()

st.set_page_config(page_title="Gestão de Rotas", page_icon="🗺️", layout="wide")

st.title("🗺️ Gestão de Rotas e Logística")

# 1. CADASTRO DE ROTEIRO
with st.expander("➕ Adicionar Ponto ao Roteiro", expanded=True):
    with st.form("form_rota", clear_on_submit=True):
        c1, c2, c3 = st.columns([1, 2, 3])
        ordem = c1.number_input("Ordem", min_value=1, value=1)
        tipo = c2.selectbox("Tipo", ["Entrega", "Coleta", "Serviço"])
        cliente = c3.text_input("Cliente / Local")
        
        c4, c5 = st.columns([3, 1])
        endereco = c4.text_input("Endereço (Rua, Número, Cidade)", placeholder="Ex: Av. Paulista, 1000, São Paulo")
        motorista = c5.selectbox("Motorista", ["Almoxarife", "Motorista Extra"])
        
        obs = st.text_area("Observações")
        
        if st.form_submit_button("Salvar Parada"):
            dados = {
                'data_rota': date.today().strftime("%d/%m/%Y"), # Formato BR
                'ordem': ordem, 'tipo': tipo, 'cliente': cliente,
                'endereco': endereco, 'status': 'Pendente',
                'obs': obs, 'motorista': motorista
            }
            if utils_db.registrar_parada_rota(dados):
                st.success(f"Ponto {ordem} adicionado para {motorista}!")
            else:
                st.error("Erro ao salvar.")

st.divider()

# 2. ACOMPANHAMENTO
st.subheader(f"Roteiro de Hoje ({date.today().strftime('%d/%m/%Y')})")

if st.button("🔄 Atualizar Status"):
    st.rerun()

df = utils_db.listar_rotas_dia(date.today().strftime("%d/%m/%Y"))

if not df.empty:
    # Métricas
    total = len(df)
    concluidos = len(df[df['status'] == 'Concluído'])
    pendentes = total - concluidos
    progresso = concluidos / total if total > 0 else 0
    
    k1, k2, k3 = st.columns(3)
    k1.metric("Total de Paradas", total)
    k2.metric("Concluídas", concluidos)
    k3.metric("Pendentes", pendentes)
    
    st.progress(progresso, text=f"Progresso: {int(progresso*100)}%")
    
    # Tabela Visual
    st.dataframe(
        df[['ordem', 'status', 'hora_conclusao', 'tipo', 'cliente', 'endereco', 'motorista']],
        use_container_width=True,
        hide_index=True
    )
    
    # Mapa (Visualização Geral)
    if TEM_MAPA:
        st.write("### 📍 Mapa da Região")
        # Coordenadas aproximadas de Limeira-SP (Centralizar)
        m = folium.Map(location=[-22.564, -47.400], zoom_start=12)
        st_folium(m, width=None, height=300)
        st.caption("*Para ver os pinos exatos dos endereços, seria necessária uma integração com API de Geocoding do Google ($).*")
    else:
        st.warning("Instale 'folium' e 'streamlit-folium' no requirements.txt para ver o mapa.")

else:
    st.info("Nenhuma rota cadastrada para hoje.")
