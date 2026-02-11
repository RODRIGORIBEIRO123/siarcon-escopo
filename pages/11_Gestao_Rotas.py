import streamlit as st
import pandas as pd
from datetime import date, datetime, timedelta
import utils_db
import time

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
with st.expander("➕ Adicionar Ponto ao Roteiro", expanded=False):
    with st.form("form_rota", clear_on_submit=True):
        c1, c2, c3 = st.columns([1, 2, 3])
        ordem = c1.number_input("Ordem", min_value=1, value=1)
        tipo = c2.selectbox("Tipo", ["Entrega", "Coleta", "Serviço"])
        cliente = c3.text_input("Cliente / Local")
        
        c4, c5, c6 = st.columns([3, 1, 1])
        endereco = c4.text_input("Endereço Completo", placeholder="Rua, Número, Cidade - UF")
        tempo_parada = c5.number_input("Tempo Parada (min)", min_value=5, value=30, step=5)
        motorista = c6.selectbox("Motorista", ["Almoxarife", "Motorista Extra"])
        
        obs = st.text_area("Observações")
        
        if st.form_submit_button("Salvar Parada"):
            # Tenta pegar coordenadas lat/lon automaticamente (Geocoding Grátis)
            lat, lon = utils_db.obter_coordenadas(endereco)
            
            dados = {
                'data_rota': date.today().strftime("%d/%m/%Y"),
                'ordem': ordem, 'tipo': tipo, 'cliente': cliente,
                'endereco': endereco, 'status': 'Pendente',
                'obs': obs, 'motorista': motorista,
                'tempo_estimado_parada': tempo_parada,
                'lat': lat, 'lon': lon # Salva coordenadas se achou
            }
            if utils_db.registrar_parada_rota(dados):
                st.success(f"Ponto adicionado! (Coord: {lat}, {lon})")
            else:
                st.error("Erro ao salvar.")

st.divider()

# 2. ACOMPANHAMENTO
c_top1, c_top2 = st.columns([3, 1])
c_top1.subheader(f"Roteiro de Hoje ({date.today().strftime('%d/%m/%Y')})")
if c_top2.button("🔄 Recalcular Rota"): st.rerun()

df = utils_db.listar_rotas_dia(date.today().strftime("%d/%m/%Y"))

if not df.empty:
    # --- CORREÇÃO DO ERRO KEYERROR (AUTO-REPARO) ---
    # Garante que as colunas novas existam, mesmo se a planilha for antiga
    colunas_novas = ['tempo_estimado_parada', 'lat', 'lon', 'hora_conclusao', 'status']
    for col in colunas_novas:
        if col not in df.columns:
            df[col] = 0 if col == 'tempo_estimado_parada' else None

    # --- CÁLCULO DA ROTA TOTAL ---
    # 1. Soma tempos de parada (Converte para float seguro)
    total_paradas_min = pd.to_numeric(df['tempo_estimado_parada'], errors='coerce').fillna(0).sum()
    
    # 2. Calcula trajeto OSRM (se tiver coordenadas)
    coords = []
    # Ponto de Partida (Siarcon - Exemplo Limeira)
    coords.append((-22.564, -47.400)) 
    
    tem_coords = False
    # Verifica se lat/lon existem e são válidos
    for _, row in df.iterrows():
        try:
            l = float(row['lat'])
            lo = float(row['lon'])
            if l != 0 and lo != 0: 
                coords.append((l, lo))
                tem_coords = True
        except: pass
            
    km_total = 0
    tempo_direcao_min = 0
    
    if tem_coords and len(coords) > 1:
        km_total, tempo_direcao_min = utils_db.calcular_rota_osrm(coords)

    tempo_total_min = total_paradas_min + tempo_direcao_min
    horas = int(tempo_total_min // 60)
    minutos = int(tempo_total_min % 60)

    # --- DASHBOARD DE MÉTRICAS ---
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Paradas", len(df))
    k2.metric("Distância Est.", f"{km_total} km")
    k3.metric("Tempo Direção", f"{int(tempo_direcao_min)} min")
    k4.metric("Tempo Total (c/ Paradas)", f"{horas}h {minutos}m")
    
    st.markdown("---")

    # Tabela
    # Agora é seguro chamar as colunas pois garantimos que elas existem acima
    colunas_visiveis = ['ordem', 'tipo', 'cliente', 'endereco', 'tempo_estimado_parada', 'status']
    # Filtra apenas as que realmente existem no DF final (segurança dupla)
    cols_to_show = [c for c in colunas_visiveis if c in df.columns]
    
    st.dataframe(
        df[cols_to_show],
        use_container_width=True,
        hide_index=True
    )
    
    # Mapa
    if TEM_MAPA:
        m = folium.Map(location=[-22.564, -47.400], zoom_start=12)
        
        # Plota os pontos que têm coordenada
        if tem_coords:
            # Linha da rota
            folium.PolyLine(coords, color="blue", weight=2.5, opacity=1).add_to(m)
            
            # Marcadores
            for i, coord in enumerate(coords):
                if i == 0:
                    folium.Marker(coord, popup="Siarcon (Saída)", icon=folium.Icon(color="green", icon="home")).add_to(m)
                else:
                    # Tenta pegar dados do DF (i-1 pois coords[0] é a saída)
                    try:
                        nome = df.iloc[i-1]['cliente']
                        folium.Marker(coord, popup=f"{i}º - {nome}", icon=folium.Icon(color="red", icon="info-sign")).add_to(m)
                    except: pass

        st_folium(m, width=None, height=400)
    
else:
    st.info("Nenhuma rota cadastrada para hoje.")
