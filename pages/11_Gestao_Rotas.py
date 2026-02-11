import streamlit as st
import pandas as pd
from datetime import date, datetime, timedelta
import utils_db
import time

# Mapa
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

# ============================================================================
# 1. CADASTRO
# ============================================================================
with st.expander("➕ Adicionar Ponto ao Roteiro", expanded=False):
    with st.form("form_rota", clear_on_submit=True):
        c1, c2, c3 = st.columns([1, 2, 3])
        ordem = c1.number_input("Ordem", min_value=1, value=1)
        tipo = c2.selectbox("Tipo", ["Entrega", "Coleta", "Serviço"])
        cliente = c3.text_input("Cliente / Local")
        
        c4, c5, c6 = st.columns([3, 1, 1])
        endereco = c4.text_input("Endereço", placeholder="Rua X, 123, Bairro, Cidade - UF")
        tempo_parada = c5.number_input("Tempo Parada (min)", min_value=5, value=30, step=5)
        motorista = c6.selectbox("Motorista", ["Almoxarife", "Motorista Extra"])
        
        obs = st.text_area("Observações")
        
        if st.form_submit_button("Salvar Parada"):
            # Tenta GPS na hora
            lat, lon = utils_db.obter_coordenadas(endereco)
            msg_gps = "📍 GPS OK" if lat != 0 else "⚠️ GPS não achou (será tentado novamente depois)"
            
            dados = {
                'data_rota': date.today().strftime("%d/%m/%Y"),
                'ordem': ordem, 'tipo': tipo, 'cliente': cliente,
                'endereco': endereco, 'status': 'Pendente',
                'obs': obs, 'motorista': motorista,
                'tempo_estimado_parada': tempo_parada,
                'lat': lat, 'lon': lon 
            }
            if utils_db.registrar_parada_rota(dados):
                st.success(f"Ponto salvo! {msg_gps}")
                time.sleep(1)
                st.rerun()
            else:
                st.error("Erro ao salvar.")

st.divider()

# ============================================================================
# 2. VISUALIZAÇÃO E CÁLCULO
# ============================================================================
c_top1, c_top2 = st.columns([3, 1])
c_top1.subheader(f"Roteiro de Hoje ({date.today().strftime('%d/%m/%Y')})")
if c_top2.button("🔄 Atualizar Dados"): st.rerun()

df = utils_db.listar_rotas_dia(date.today().strftime("%d/%m/%Y"))

if not df.empty:
    # --- SANITIZAÇÃO DOS DADOS ---
    # Garante que as colunas existem e converte lat/lon para float
    cols_check = ['lat', 'lon', 'tempo_estimado_parada', 'hora_conclusao']
    for c in cols_check:
        if c not in df.columns: df[c] = 0
    
    # Converte strings de lat/lon (ex: "-22,564") para float (-22.564)
    df['lat'] = df['lat'].astype(str).str.replace(',', '.').apply(lambda x: float(x) if x.replace('.','',1).replace('-','').isdigit() else 0.0)
    df['lon'] = df['lon'].astype(str).str.replace(',', '.').apply(lambda x: float(x) if x.replace('.','',1).replace('-','').isdigit() else 0.0)
    
    # --- VERIFICAÇÃO DE COORDENADAS FALTANTES ---
    # Se tiver endereço mas lat for 0, precisamos buscar
    itens_sem_gps = df[(df['endereco'] != "") & (df['lat'] == 0)]
    
    if not itens_sem_gps.empty:
        st.warning(f"⚠️ Existem {len(itens_sem_gps)} endereços sem coordenadas. O roteiro não pode ser calculado.")
        if st.button("🔎 Tentar Localizar Endereços no GPS Agora"):
            bar = st.progress(0, "Buscando coordenadas...")
            for i, (idx, row) in enumerate(itens_sem_gps.iterrows()):
                lat_n, lon_n = utils_db.obter_coordenadas(row['endereco'])
                if lat_n != 0:
                    utils_db.atualizar_coordenadas_rota(row['id'], lat_n, lon_n)
                bar.progress((i+1)/len(itens_sem_gps))
            st.success("Busca concluída! Recarregando...")
            time.sleep(1)
            st.rerun()

    # --- CÁLCULO DA ROTA ---
    # Ponto de Partida: SIARCON (Limeira - Exemplo)
    # Substitua pelas coordenadas reais da sua empresa se quiser precisão máxima
    SIARCON_LAT, SIARCON_LON = -22.5646, -47.4009 
    
    coords = [(SIARCON_LAT, SIARCON_LON)]
    tem_caminho = False
    
    # Adiciona pontos válidos na ordem
    for _, row in df.iterrows():
        if row['lat'] != 0 and row['lon'] != 0:
            coords.append((row['lat'], row['lon']))
            tem_caminho = True
            
    # Chama API OSRM
    km_total, tempo_direcao_min, geometria_rota = 0, 0, None
    if len(coords) > 1:
        km_total, tempo_direcao_min, geometria_rota = utils_db.calcular_rota_osrm(coords)

    # Soma tempo de paradas
    tempo_paradas = pd.to_numeric(df['tempo_estimado_parada'], errors='coerce').fillna(0).sum()
    
    tempo_total_geral = tempo_paradas + tempo_direcao_min
    h = int(tempo_total_geral // 60)
    m = int(tempo_total_geral % 60)

    # --- DASHBOARD ---
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Total Paradas", len(df))
    k2.metric("Distância Rota", f"{km_total} km")
    k3.metric("Tempo Volante", f"{int(tempo_direcao_min)} min")
    k4.metric("Tempo Total (Estimado)", f"{h}h {m}min")
    
    st.markdown("---")

    # --- TABELA ---
    st.dataframe(
        df[['ordem', 'tipo', 'cliente', 'endereco', 'tempo_estimado_parada', 'status']],
        use_container_width=True, hide_index=True
    )
    
    # --- MAPA ---
    if TEM_MAPA:
        # Centraliza média dos pontos ou Siarcon
        m = folium.Map(location=[SIARCON_LAT, SIARCON_LON], zoom_start=12)
        
        # Desenha Rota (Se houver geometria do OSRM)
        if geometria_rota:
            folium.GeoJson(geometria_rota, name="Rota", style_function=lambda x: {'color': 'blue', 'weight': 4}).add_to(m)
        elif len(coords) > 1:
            # Fallback: Linha reta se OSRM não devolver geometria
            folium.PolyLine(coords, color="red", weight=2, dash_array="5, 5").add_to(m)

        # Marcadores
        # 1. Siarcon
        folium.Marker([SIARCON_LAT, SIARCON_LON], popup="SIARCON (Base)", icon=folium.Icon(color="green", icon="home")).add_to(m)
        
        # 2. Clientes
        for _, row in df.iterrows():
            if row['lat'] != 0:
                cor = "gray" if row['status'] == 'Concluído' else "blue"
                icone = "info-sign"
                folium.Marker(
                    [row['lat'], row['lon']], 
                    popup=f"{row['ordem']} - {row['cliente']}", 
                    icon=folium.Icon(color=cor, icon=icone)
                ).add_to(m)

        st_folium(m, width=None, height=500)
    
else:
    st.info("Nenhuma rota cadastrada para hoje.")
