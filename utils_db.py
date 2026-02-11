import streamlit as st
import pandas as pd
import gspread
from datetime import datetime

# ==================================================
# 1. CONEXÃO E CACHE
# ==================================================
@st.cache_resource(ttl=600)
def _conectar_gsheets():
    try:
        if "gcp_service_account" not in st.secrets: 
            return None
        
        creds_dict = dict(st.secrets["gcp_service_account"])
        if "private_key" in creds_dict:
            chave = creds_dict["private_key"]
            if "\n" not in chave: creds_dict["private_key"] = chave.replace("\\n", "\n")
        
        gc = gspread.service_account_from_dict(creds_dict)
        return gc.open("DB_SIARCON") 
    except Exception as e:
        print(f"Erro Conexão: {e}")
        return None

def _ler_aba_como_df(nome_aba):
    sh = _conectar_gsheets()
    if not sh: return pd.DataFrame()
    try:
        try: ws = sh.worksheet(nome_aba)
        except: 
            try: ws = sh.add_worksheet(nome_aba, 100, 20)
            except: return pd.DataFrame()
        
        data = ws.get_all_records()
        return pd.DataFrame(data)
    except: return pd.DataFrame()

# ==================================================
# 2. AUTENTICAÇÃO
# ==================================================
def verificar_login_db(usuario, senha):
    df = _ler_aba_como_df("Usuarios")
    if df.empty:
        if usuario == "admin" and senha == "1234": return True
        return False
    
    df['Usuario'] = df['Usuario'].astype(str)
    df['Senha'] = df['Senha'].astype(str)
    
    user_encontrado = df[(df['Usuario'] == str(usuario)) & (df['Senha'] == str(senha))]
    return not user_encontrado.empty

# ==================================================
# 3. FUNÇÕES DE PROJETO (COM AUTO-CORREÇÃO DE COLUNAS)
# ==================================================
def listar_todos_projetos():
    df = _ler_aba_como_df("Projetos")
    # Garante colunas mínimas para o dashboard não quebrar
    cols_minimas = ['_id', 'status', 'disciplina', 'cliente', 'obra', 'prazo']
    if df.empty: return pd.DataFrame(columns=cols_minimas)
    
    for c in cols_minimas: 
        if c not in df.columns: df[c] = ""
        
    if '_id' in df.columns: df['_id'] = df['_id'].astype(str)
    return df

def buscar_projeto_por_id(id_projeto):
    df = listar_todos_projetos()
    if df.empty: return None
    projeto = df[df['_id'] == str(id_projeto)]
    if not projeto.empty:
        # Preenche vazios com string vazia para não travar os campos de texto
        return projeto.fillna("").iloc[0].to_dict()
    return None

def salvar_projeto(dados):
    return registrar_projeto(dados)

def registrar_projeto(dados):
    sh = _conectar_gsheets()
    if not sh: return False
    try:
        # 1. Tenta pegar a aba ou criar
        try: ws = sh.worksheet("Projetos")
        except: 
            ws = sh.add_worksheet("Projetos", 100, 20)
        
        # 2. Pega os headers atuais (cabeçalho)
        headers_atuais = ws.row_values(1)
        if not headers_atuais:
            headers_atuais = ['_id', 'status', 'disciplina', 'cliente', 'obra']
            ws.append_row(headers_atuais)

        # --- A MÁGICA ACONTECE AQUI ---
        # 3. Verifica se tem alguma chave nova (ex: itens_tecnicos) que não tem coluna ainda
        novas_colunas = []
        for chave in dados.keys():
            if chave not in headers_atuais:
                novas_colunas.append(chave)
        
        # Se tiver coluna nova faltando, cria ela na planilha
        if novas_colunas:
            # Adiciona colunas extras
            ws.add_cols(len(novas_colunas))
            # Atualiza a lista local de headers e escreve na linha 1
            headers_atuais.extend(novas_colunas)
            ws.update(range_name="A1", values=[headers_atuais])

        # 4. Gera ID se não tiver
        if '_id' not in dados or not dados['_id']: 
            dados['_id'] = datetime.now().strftime("%Y%m%d%H%M%S")

        # 5. Prepara a linha de dados na ordem correta dos headers
        row_data = []
        for h in headers_atuais:
            valor = str(dados.get(h, "")) # Converte tudo para string para evitar erro
            row_data.append(valor)

        # 6. Busca se já existe para atualizar
        cell = None
        try: cell = ws.find(str(dados['_id']), in_column=1)
        except: pass

        if cell: 
            # Atualiza linha existente
            ws.update(range_name=f"A{cell.row}", values=[row_data])
        else: 
            # Cria nova linha
            ws.append_row(row_data)
            
        return True
    except Exception as e:
        print(f"ERRO CRÍTICO AO SALVAR: {e}")
        return False

def excluir_projeto(id_projeto):
    sh = _conectar_gsheets()
    if not sh: return False
    try:
        ws = sh.worksheet("Projetos")
        cell = ws.find(str(id_projeto), in_column=1)
        if cell:
            ws.delete_rows(cell.row)
            return True
    except: pass
    return False

# ==================================================
# 4. AUXILIARES
# ==================================================
def listar_fornecedores():
    sh = _conectar_gsheets()
    if not sh: return []
    try:
        ws = sh.worksheet("FORNECEDORES")
        vals = ws.get_all_values()
        if len(vals) > 1:
            lista = []
            for row in vals[1:]:
                if row and row[0]: 
                    cnpj = row[1] if len(row) > 1 else ""
                    lista.append({'Fornecedor': row[0], 'CNPJ': cnpj})
            return lista
    except: pass
    
    # Fallback para aprender da aba Dados se não tiver aba fornecedores
    df = _ler_aba_como_df("Dados")
    if not df.empty and 'Fornecedor' in df.columns:
        return df[['Fornecedor', 'CNPJ']].dropna(subset=['Fornecedor']).drop_duplicates().to_dict('records')
    return []

def carregar_opcoes():
    df = _ler_aba_como_df("Dados")
    opcoes = {'sms': []}
    if not df.empty and 'Categoria' in df.columns and 'Item' in df.columns:
        df['Categoria'] = df['Categoria'].astype(str).str.lower().str.strip()
        for cat in df['Categoria'].unique():
            itens = sorted(df[df['Categoria'] == cat]['Item'].unique().tolist())
            opcoes[cat] = itens
    return opcoes

def aprender_novo_item(categoria, novo_item):
    sh = _conectar_gsheets()
    if not sh: return False
    try:
        try: ws = sh.worksheet("Dados")
        except: ws = sh.add_worksheet("Dados", 100, 10)
        
        if not ws.row_values(1): ws.append_row(["Categoria", "Item"])
        
        ws.append_row([categoria.lower(), novo_item])
        return True
    except: return False

# ... (Mantenha o resto do arquivo igual) ...

def registrar_romaneio(dados):
    sh = _conectar_gsheets()
    if not sh: return False
    try:
        try: ws = sh.worksheet("Romaneios")
        except: ws = sh.add_worksheet("Romaneios", 100, 20)
        
        # Adicionado 'destino' no cabeçalho
        headers = ['id', 'data', 'obra', 'destino', 'materiais_json', 'responsavel_envio', 'responsavel_recebimento']
        
        if not ws.row_values(1): ws.append_row(headers)

        if 'id' not in dados or not dados['id']: 
            dados['id'] = datetime.now().strftime("%Y%m%d%H%M%S")

        row_data = [
            str(dados.get('id', '')),
            str(dados.get('data', '')),
            str(dados.get('obra', '')),
            str(dados.get('destino', '')), # Novo Campo
            str(dados.get('materiais_json', '')),
            str(dados.get('responsavel_envio', '')),
            str(dados.get('responsavel_recebimento', ''))
        ]
        
        ws.append_row(row_data)
        return True
    except Exception as e:
        print(f"Erro ao salvar romaneio: {e}")
        return False

# --- ADICIONE AO FINAL DE utils_db.py ---

# --- ADICIONE ISTO NO FINAL DO ARQUIVO utils_db.py ---

def registrar_parada_rota(dados):
    sh = _conectar_gsheets()
    if not sh: return False
    try:
        try: ws = sh.worksheet("Rotas")
        except: ws = sh.add_worksheet("Rotas", 100, 20)
        
        headers = ['id', 'data_rota', 'ordem', 'tipo', 'cliente', 'endereco', 'motorista', 'status', 'obs', 'hora_conclusao']
        if not ws.row_values(1): ws.append_row(headers)

        if 'id' not in dados or not dados['id']: 
            dados['id'] = datetime.now().strftime("%Y%m%d%H%M%S")

        row_data = [
            str(dados.get('id', '')),
            str(dados.get('data_rota', '')),
            str(dados.get('ordem', '')),
            str(dados.get('tipo', 'Entrega')),
            str(dados.get('cliente', '')),
            str(dados.get('endereco', '')),
            str(dados.get('motorista', '')),
            str(dados.get('status', 'Pendente')),
            str(dados.get('obs', '')),
            str(dados.get('hora_conclusao', ''))
        ]
        
        ws.append_row(row_data)
        return True
    except Exception as e:
        print(f"Erro rota: {e}")
        return False

def listar_rotas_dia(data_filtro=None):
    df = _ler_aba_como_df("Rotas")
    if df.empty: return df
    
    if data_filtro:
        # Filtra pela data
        df = df[df['data_rota'] == str(data_filtro)]
    
    # Ordena por Ordem (se possível converter)
    try:
        df['ordem'] = pd.to_numeric(df['ordem'])
        df = df.sort_values('ordem')
    except: pass
    
    return df

def concluir_parada(id_parada):
    sh = _conectar_gsheets()
    if not sh: return False
    try:
        ws = sh.worksheet("Rotas")
        cell = ws.find(str(id_parada), in_column=1)
        if cell:
            # Coluna 8 (H) é Status, Coluna 10 (J) é Hora Conclusão
            hora_agora = datetime.now().strftime("%H:%M")
            ws.update_cell(cell.row, 8, "Concluído")
            ws.update_cell(cell.row, 10, hora_agora)
            return True
    except: pass
    return False

# --- ADICIONE AO FINAL DE utils_db.py ---
import requests

def obter_coordenadas(endereco):
    """Converte endereço em Lat/Lon usando Nominatim (Grátis)"""
    try:
        url = "https://nominatim.openstreetmap.org/search"
        headers = {'User-Agent': 'SiarconLogistica/1.0'}
        params = {'q': endereco, 'format': 'json', 'limit': 1}
        response = requests.get(url, headers=headers, params=params).json()
        if response:
            return float(response[0]['lat']), float(response[0]['lon'])
    except:
        pass
    return None, None

def calcular_rota_osrm(pontos):
    """
    Calcula distância e tempo total passando por vários pontos.
    pontos: lista de tuplas [(lat, lon), (lat, lon), ...]
    """
    if len(pontos) < 2:
        return 0, 0, [] # Sem rota

    # Formata coordenadas para OSRM: lon,lat;lon,lat
    coords_str = ";".join([f"{p[1]},{p[0]}" for p in pontos])
    url = f"http://router.project-osrm.org/route/v1/driving/{coords_str}?overview=false"
    
    try:
        r = requests.get(url).json()
        if 'routes' in r:
            distancia_m = r['routes'][0]['distance']
            tempo_s = r['routes'][0]['duration']
            
            km = round(distancia_m / 1000, 1)
            minutos = round(tempo_s / 60)
            return km, minutos
    except:
        pass
    
    return 0, 0

# --- ATUALIZAÇÃO NO FINAL DE utils_db.py ---
import requests
import time

def obter_coordenadas(endereco):
    """
    Converte endereço em Lat/Lon usando Nominatim (Grátis).
    Adiciona 'Brasil' para melhorar precisão se não tiver.
    """
    if not endereco: return 0, 0
    
    # Melhora a busca adicionando contexto se for muito curta
    termo_busca = endereco
    if "brasil" not in termo_busca.lower():
        termo_busca += ", Brasil"
        
    try:
        url = "https://nominatim.openstreetmap.org/search"
        # User-Agent é obrigatório pelas regras do Nominatim
        headers = {'User-Agent': 'SiarconApp/1.0 (contato@siarcon.com)'}
        params = {'q': termo_busca, 'format': 'json', 'limit': 1}
        
        r = requests.get(url, headers=headers, params=params, timeout=5)
        dados = r.json()
        
        if dados:
            return float(dados[0]['lat']), float(dados[0]['lon'])
    except Exception as e:
        print(f"Erro GPS: {e}")
    
    return 0, 0

def calcular_rota_osrm(pontos):
    """
    Calcula rota entre lista de coordenadas [(lat, lon), ...].
    Retorna: km (float), minutos (float), geometria (str/encoded)
    """
    if len(pontos) < 2:
        return 0, 0, None

    # Formata para OSRM: lon,lat;lon,lat (Atenção: OSRM usa Longitude,Latitude)
    coords_str = ";".join([f"{p[1]},{p[0]}" for p in pontos])
    
    # overview=full retorna a geometria para desenhar no mapa
    url = f"http://router.project-osrm.org/route/v1/driving/{coords_str}?overview=full&geometries=geojson"
    
    try:
        r = requests.get(url, timeout=5).json()
        if 'routes' in r and len(r['routes']) > 0:
            rota = r['routes'][0]
            distancia_m = rota['distance']
            tempo_s = rota['duration']
            geometry = rota['geometry'] # Linha para desenhar no mapa
            
            km = round(distancia_m / 1000, 1)
            minutos = round(tempo_s / 60)
            return km, minutos, geometry
    except Exception as e:
        print(f"Erro OSRM: {e}")
        
    return 0, 0, None

def atualizar_coordenadas_rota(id_rota, lat, lon):
    """Salva a coordenada descoberta no banco para não buscar de novo"""
    sh = _conectar_gsheets()
    if not sh: return False
    try:
        ws = sh.worksheet("Rotas")
        cell = ws.find(str(id_rota), in_column=1)
        if cell:
            # Colunas de Lat/Lon (K e L -> indices 11 e 12)
            # Se sua planilha tiver ordem diferente, isso ajusta
            # Headers: id, data, ordem, tipo, cliente, endereco, motorista, status, obs, hora, tempo_est, lat, lon
            # Lat é col 12, Lon é col 13
            ws.update_cell(cell.row, 12, str(lat).replace('.', ','))
            ws.update_cell(cell.row, 13, str(lon).replace('.', ','))
            return True
    except: pass
    return False
