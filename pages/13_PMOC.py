import streamlit as st
from docx import Document
from docx.shared import Pt, Inches
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
import io
import ast
from datetime import date, datetime
import utils_db

# ==============================================================================
# CONTROLE DE ACESSO E SEGURANÇA
# ==============================================================================
if 'logado' not in st.session_state or not st.session_state['logado']:
    st.warning("🔒 Acesso negado."); st.stop()

DISCIPLINA_ATUAL = "PMOC"

# ==============================================================================
# BASE NORMATIVA SIARCON (SEÇÃO 3 - ABNT NBR 13.971 / LEI 13.589) [source: 1]
# ==============================================================================
MATRIZ_PMOC_SIARCON = {
    "3.1. Ventiladores": [
        {"item": "Verificar a existência de danos e limpar conjunto.", "frequencia": "M", "tipo": "P"},
        {"item": "Verificar e eliminar focos de corrosão.", "frequencia": "S", "tipo": "P"},
        {"item": "Verificar fixação, vibrações e ruídos anormais.", "frequencia": "T", "tipo": "P"},
        {"item": "Verificar aquecimento anormal dos mancais.", "frequencia": "S", "tipo": "P"},
        {"item": "Lubrificar os mancais, se aplicável", "frequencia": "T", "tipo": "P"},
        {"item": "Verificar vazamentos nas junções flexíveis", "frequencia": "T", "tipo": "P"},
        {"item": "Verificar o estado dos amortecedores de vibração.", "frequencia": "T", "tipo": "P"},
        {"item": "Verificar a operação dos controles de vazão.", "frequencia": "S", "tipo": "P"},
        {"item": "Verificar o estado e a instalação dos dispositivos de proteção.", "frequencia": "M", "tipo": "P"},
        {"item": "Limpar sistema de drenagem.", "frequencia": "T", "tipo": "P"},
        {"item": "Verificar conjunto mecânico observar itens da seção 3.13", "frequencia": "Periodicidade indicada na seção", "tipo": "P"}
    ],
    "3.2. Aquecedor de ar (liquido ou gás)": [
        {"item": "Verificar a existência de agentes que possam prejudicar a troca térmica", "frequencia": "M", "tipo": "P"},
        {"item": "Limpar as superfícies do lado de ar", "frequencia": "M", "tipo": "P"},
        {"item": "Verificar os fluxos de ar/liquido, vapor ou gás", "frequencia": "M", "tipo": "P"},
        {"item": "Medir e registrar as temperaturas e pressões, na condição de plena vazão de ambos os fluidos e nos pontos de entrada e saída", "frequencia": "S", "tipo": "NP"},
        {"item": "Verificar isolamento térmico do componente (inspeção visual)", "frequencia": "T", "tipo": "P"}
    ],
    "3.3. Aquecedor de ar elétrico (resistências)": [
        {"item": "Verificar a existência de agentes que possam prejudicar a troca térmica", "frequencia": "M", "tipo": "P"},
        {"item": "Limpar as resistências elétricas do lado de ar", "frequencia": "M", "tipo": "P"},
        {"item": "Verificar funcionamento dos dispositivos de segurança", "frequencia": "T", "tipo": "P"},
        {"item": "Medir e registrar os valores de tensão, corrente e isolação elétrica", "frequencia": "S", "tipo": "P"},
        {"item": "Verificar a existência de aterramento do componente", "frequencia": "M", "tipo": "P"},
        {"item": "Verificar isolamento térmico do componente (inspeção visual)", "frequencia": "T", "tipo": "P"}
    ],
    "3.4. Resfriadores de ar (liquido)": [
        {"item": "Verificar a existência de agentes que possam prejudicar a troca térmica.", "frequencia": "M", "tipo": "P"},
        {"item": "Limpar as superfícies do lado de ar", "frequencia": "M", "tipo": "P"},
        {"item": "Verificar os fluxos de ar/liquido", "frequencia": "M", "tipo": "P"},
        {"item": "Verificar e eliminar a existência de ar do lado de liquido", "frequencia": "M", "tipo": "P"},
        {"item": "Medir e registrar as temperaturas e pressões, na condição de plena vazão de ambos os fluidos e nos pontos de entrada e saída", "frequencia": "S", "tipo": "P"},
        {"item": "Limpar o sistema de drenagem", "frequencia": "T", "tipo": "P"},
        {"item": "Verificar a existência de sujeira, danos, corrosão e fixação do eliminador de gotas", "frequencia": "M", "tipo": "P"}
    ],
    "3.5. Condicionadores de ar “Expansão direta”": [
        {"item": "Verificar a existência de agentes que possam prejudicar a troca térmica.", "frequencia": "M", "tipo": "P"},
        {"item": "Verificar e eliminar sujeira, danos e corrosão no gabinete, na moldura da serpentina e na bandeja;", "frequencia": "M", "tipo": "P"},
        {"item": "Limpar as serpentinas e bandejas", "frequencia": "M", "tipo": "P"},
        {"item": "Verificar a operação dos controles de vazão", "frequencia": "M", "tipo": "P"},
        {"item": "Limpar sistema de drenagem", "frequencia": "T", "tipo": "P"},
        {"item": "Verificar isolamento térmico e acústico do componente (inspeção visual)", "frequencia": "M", "tipo": "P"},
        {"item": "Verificar a vedação dos painéis de fechamento do gabinete", "frequencia": "T", "tipo": "P"},
        {"item": "Verificar os filtros (observar itens da seção 3.9)", "frequencia": "Periodicidade indicada na seção", "tipo": "P"},
        {"item": "Medir e registrar os valores de tensão, corrente e isolação elétrica", "frequencia": "T", "tipo": "P"},
        {"item": "Verificar ventiladores (observar item 3.1)", "frequencia": "Periodicidade indicada na seção", "tipo": "P"},
        {"item": "Verificar conjunto mecânico observar itens da seção 3.13", "frequencia": "Periodicidade indicada na seção", "tipo": "P"}
    ],
    "3.6. Condicionadores de ar tipo “Expansão indireta” (Chillers)": [
        {"item": "Verificar a existência de agentes que possam prejudicar a troca térmica.", "frequencia": "M", "tipo": "P"},
        {"item": "Verificar a eventual perda de refrigerante e a presença de umidade", "frequencia": "M", "tipo": "P"},
        {"item": "Verificar e corrigir a carga refrigerante", "frequencia": "M", "tipo": "P"},
        {"item": "Verificar suportes, amortecedores de vibração e fixação", "frequencia": "T", "tipo": "P"},
        {"item": "Limpar as serpentinas e bandejas", "frequencia": "M", "tipo": "P"},
        {"item": "Verificar presença de vazamentos em juntas e válvulas de refrigerantes", "frequencia": "T", "tipo": "P"},
        {"item": "Reparar e corrigir os vazamentos eventuais", "frequencia": "T", "tipo": "NP"},
        {"item": "Verificar a operação dos controles de vazão", "frequencia": "T", "tipo": "P"},
        {"item": "Limpar sistema de drenagem", "frequencia": "M", "tipo": "P"},
        {"item": "Verificar isolamento térmico e acústico do componente (inspeção visual)", "frequencia": "M", "tipo": "P"},
        {"item": "Verificar funcionamento dos dispositivos de segurança", "frequencia": "T", "tipo": "P"},
        {"item": "Verificar a vedação dos painéis de fechamento do gabinete", "frequencia": "T", "tipo": "P"},
        {"item": "Verificar os filtros (observar itens da seção 3.9)", "frequencia": "Periodicidade indicada na seção", "tipo": "P"},
        {"item": "Medir e registrar os valores de tensão, corrente e isolação elétrica", "frequencia": "A", "tipo": "P"},
        {"item": "Verificar a operação da chave de fluxo de água gelada e bomba", "frequencia": "T", "tipo": "P"},
        {"item": "Verificar e medir a queda de pressão no filtro de óleo", "frequencia": "T", "tipo": "P"},
        {"item": "Inspecionar a vedação da bomba de água", "frequencia": "T", "tipo": "P"},
        {"item": "Verificar e reapertar as conexões elétricas", "frequencia": "A", "tipo": "P"},
        {"item": "Inspecione todos os contatores e relés substituindo os necessários", "frequencia": "A", "tipo": "P"},
        {"item": "Verificar e precisão dos termistores e transdutores por meio de instrumentos calibrados", "frequencia": "A", "tipo": "P"},
        {"item": "Certificar-se de que exista a concentração adequada de anticongelante no circuito de água gelada", "frequencia": "A", "tipo": "P"},
        {"item": "Verificar se o circuito de água possui tratamento adequado", "frequencia": "A", "tipo": "P"},
        {"item": "Verificar filtros em acordo com a seção 3.9", "frequencia": "A", "tipo": "P"},
        {"item": "Verificar a condição e fixação das pás do ventilador no eixo do motor", "frequencia": "A", "tipo": "P"},
        {"item": "Executar o teste de serviço do devido equipamento para confirmar a operação de todos os componentes", "frequencia": "A", "tipo": "P"},
        {"item": "Verificar se existe uma aproximação excessiva da temperatura de saída de água gelada, caso haja realizar limpeza completa da carcaça pois pode indicar incrustação", "frequencia": "A", "tipo": "P"},
        {"item": "Realizar análise do óleo, realizar troca se necessário", "frequencia": "A", "tipo": "P"},
        {"item": "Verificar ventiladores (observar item 3.1)", "frequencia": "Periodicidade indicada na seção", "tipo": "P"},
        {"item": "Verificar conjunto mecânico observar itens da seção 3.13", "frequencia": "Periodicidade indicada na seção", "tipo": "P"}
    ],
    "3.7. Evaporadores (fluído frigorífico ou líquido)": [
        {"item": "Verificar a existência de agentes que possam prejudicar a troca térmica.", "frequencia": "M", "tipo": "P"},
        {"item": "Limpar as superfícies do lado de ar ou de liquido refrigerado", "frequencia": "T", "tipo": "P"},
        {"item": "Verificar os fluxos de fluidos frigoríficos e refrigerados", "frequencia": "S", "tipo": "P"},
        {"item": "Eliminar a existência de ar do lado do líquido refrigerado", "frequencia": "A", "tipo": "NP"},
        {"item": "Medir e registrar as temperaturas e pressões, na condição de plena vazão de ambos os fluidos e nos pontos de entrada e saída", "frequencia": "T", "tipo": "P"},
        {"item": "Verificar isolamento térmico do componente (inspeção visual)", "frequencia": "M", "tipo": "P"},
        {"item": "Verificar funcionamento do sistema anticongelamento (fluido frigorífico refrigerado a ar)", "frequencia": "Quando necessário", "tipo": "NP"},
        {"item": "Em casos de soluções aquosas, verificar a concentração do anticongelante", "frequencia": "T", "tipo": "P"},
        {"item": "Corrigir a concentração de anticongelantena", "frequencia": "Quando necessário", "tipo": "NP"},
        {"item": "Limpar sistema de drenagem", "frequencia": "T", "tipo": "P"},
        {"item": "Verificar a existência de vazamentos de fluídos refrigerantes, liquido ou ar", "frequencia": "T", "tipo": "P"},
        {"item": "Para evaporador fluído frigorífico, efetuar análise de água quanto a característica", "frequencia": "S", "tipo": "P"},
        {"item": "Efetuar correção da característica da água", "frequencia": "Quando necessário", "tipo": "NP"},
        {"item": "Verificar os filtros (observar item 3.9)", "frequencia": "Periodicidade indicada na seção", "tipo": "P"},
        {"item": "Medir e registrar os valores de tensão, corrente e isolação elétrica", "frequencia": "M", "tipo": "P"},
        {"item": "Verificar ventiladores (observar item 3.1)", "frequencia": "Periodicidade indicada na seção", "tipo": "P"},
        {"item": "Verificar conjunto mecânico observar itens da seção 3.13", "frequencia": "Periodicidade indicada na seção", "tipo": "P"}
    ],
    "3.8. Trocador de calor de contracorrente ou corrente cruzada": [
        {"item": "Verificar o funcionamento do sistema de purga de ar (no caso de liquido/liquido)", "frequencia": "M", "tipo": "P"},
        {"item": "Medir e registrar as temperaturas e pressões, na condição de plena vazão de ambos os fluidos e nos pontos de entrada e saída", "frequencia": "T", "tipo": "P"},
        {"item": "Verificar isolamento térmico do componente (inspeção visual)", "frequencia": "M", "tipo": "P"},
        {"item": "Verificar a operação dos sistemas de segurança", "frequencia": "M", "tipo": "P"}
    ],
    "3.9. Filtros": [
        {"item": "Filtro rotativo: Verificar a existência de danos, limpar e vedar frestas na moldura", "frequencia": "M", "tipo": "P"},
        {"item": "Filtro rotativo: Verificar a operação da alimentação do elemento filtrante", "frequencia": "M", "tipo": "P"},
        {"item": "Filtro rotativo: Substituir o elemento filtrante", "frequencia": "Quando necessário", "tipo": "NP"},
        {"item": "Filtro seco: Verificar a existência de danos, limpar e vedar frestas na moldura", "frequencia": "M", "tipo": "P"},
        {"item": "Filtro seco: Medir e registrar o diferencial de pressão", "frequencia": "T", "tipo": "P"},
        {"item": "Filtro seco: Substituir o elemento filtrante", "frequencia": "Quando necessário", "tipo": "NP"},
        {"item": "Filtro eletrostático: Verificar a existência de danos, sujeira e corrosão", "frequencia": "M", "tipo": "P"},
        {"item": "Filtro eletrostático: Verificar e limpar o módulo eletrostático", "frequencia": "M", "tipo": "P"},
        {"item": "Filtros absorventes/adsorventes: Verificar a existência de sujeira, danos e corrosão", "frequencia": "M", "tipo": "P"},
        {"item": "Filtros absorventes/adsorventes: Verificar saturação e substituir elemento", "frequencia": "T", "tipo": "P"},
        {"item": "Filtros embebidos em óleo: Limpar filtro e aplicar óleo no elemento filtrante", "frequencia": "M", "tipo": "P"}
    ],
    "3.10. Umidificadores de ar e eliminadores de gotas": [
        {"item": "Umidificadores com lavador: Verificar existência de sujeira, sedimentos e limpar elementos", "frequencia": "M", "tipo": "P"},
        {"item": "Umidificadores com lavador: Verificar funcionamento dos bicos pulverizadores de água", "frequencia": "T", "tipo": "P"},
        {"item": "Umidificador vapor elétrico: Verificar sistema de alimentação e nível de água", "frequencia": "T", "tipo": "P"},
        {"item": "Umidificador vapor rede externa: Verificar funcionamento das linhas de distribuição de vapor e condensado", "frequencia": "M", "tipo": "P"},
        {"item": "Geradores de vapor: Verificar o funcionamento de todas as válvulas e sistemas de alimentação", "frequencia": "T", "tipo": "P"},
        {"item": "Eliminadores de gotas: Verificar existência de sujeira, danos, corrosão e fixação", "frequencia": "M", "tipo": "P"}
    ],
    "3.11. Componentes de distribuição e difusão de ar": [
        {"item": "Venezianas, grelhas e difusores: Verificar existência de sujeira, danos e corrosão", "frequencia": "M", "tipo": "P"},
        {"item": "Damper corta-fogo: Verificar sujeira nos elementos de fechamento, trava e abertura", "frequencia": "M", "tipo": "P"},
        {"item": "Damper corta-fogo: Verificar funcionamento mecânico e posicionamento do indicador", "frequencia": "S", "tipo": "P"},
        {"item": "Damper (Registro de ar): Verificar atuadores e lubrificar mancais de acionamento", "frequencia": "S", "tipo": "P"},
        {"item": "Dutos e câmara plenum: Verificar sujeira interna/externa mediante portas de inspeção e isolação térmica", "frequencia": "M", "tipo": "P"},
        {"item": "Unidades de indução: Verificar funcionamento e ajustar os injetores de indução", "frequencia": "T", "tipo": "P"},
        {"item": "Dispositivos expansão/mistura: Verificar o funcionamento dos controles de vazão", "frequencia": "M", "tipo": "P"}
    ],
    "3.12. Sistemas e quadros elétricos": [
        {"item": "Elétricos e eletrônicos: Verificar instalações, condições locais, sujeira e corrosão", "frequencia": "M", "tipo": "P"},
        {"item": "Elétricos e eletrônicos: Reapertar terminais, barramentos e elementos de fixação", "frequencia": "S", "tipo": "P"},
        {"item": "Elétricos e eletrônicos: Medir e registrar tensão e corrente elétrica dos equipamentos", "frequencia": "S", "tipo": "P"},
        {"item": "Comando pneumático: Verificar sistema de geração/alimentação de ar comprimido", "frequencia": "M", "tipo": "P"},
        {"item": "Comando pneumático: Drenar reservatório de ar comprimido e verificar filtros", "frequencia": "S", "tipo": "P"}
    ],
    "3.13. Elementos de transmissão e acionamento mecânico": [
        {"item": "Motores elétricos: Verificar sentido de rotação, vibração e ruídos anormais", "frequencia": "M", "tipo": "P"},
        {"item": "Motores elétricos: Lubrificar mancais/rolamentos e medir isolamento elétrico", "frequencia": "T", "tipo": "P"},
        {"item": "Polias e correias: Verificar tensão de esticamento, alinhamento e fixação", "frequencia": "T", "tipo": "P"},
        {"item": "Acoplamentos: Verificar alinhamento, ruídos e substituir lubrificante", "frequencia": "T", "tipo": "P"},
        {"item": "Correias e engrenagens: Verificar condição dos eixos, engrenagens e trocar óleo", "frequencia": "T", "tipo": "P"},
        {"item": "Redutores: Verificar vibração, ruído anormal, vazamentos e substituir óleo", "frequencia": "T", "tipo": "P"}
    ],
    "3.14. Sistemas hidráulicos": [
        {"item": "Bombas: Verificar vibração, ruído anormal, vedação do selo mecânico e nível de óleo", "frequencia": "M", "tipo": "P"},
        {"item": "Válvulas de controle/bloqueio: Verificar vazamentos, fiação e conexões dos atuadores", "frequencia": "M", "tipo": "P"},
        {"item": "Filtros: Verificar danos no elemento filtrante e medir diferencial de pressão", "frequencia": "T", "tipo": "P"},
        {"item": "Tubulações, tanques e acessórios: Verificar vazamentos, isolamento, juntas de expansão e purgar ar", "frequencia": "M", "tipo": "P"},
        {"item": "Compressores: Medir e registrar pressões/temperaturas de sucção e descarga e nível de óleo", "frequencia": "S", "tipo": "P"}
    ],
    "3.15. Circuitos de fluido frigorífico": [
        {"item": "Tubulações e Válvulas: Verificar existência de danos, corrosão, isolamento e reapertar conexões", "frequencia": "M", "tipo": "P"},
        {"item": "Tubulações e Válvulas: Verificar vazamentos com detector eletrônico ou outro processo externo", "frequencia": "A", "tipo": "P"},
        {"item": "Torre de resfriamento: Limpar externamente/internamente, verificar nível da bacia e sistema de purga", "frequencia": "M", "tipo": "P"},
        {"item": "Torre de resfriamento: Efetuar análise da água e corrigir características da água", "frequencia": "S", "tipo": "P"},
        {"item": "Instrumentação: Verificar se o instrumento está fornecendo a informação correta e validade da calibração", "frequencia": "A", "tipo": "P"}
    ]
}

# ==============================================================================
# FUNÇÕES DE APOIO
# ==============================================================================
def converter_para_estrutura(valor, tipo_esperado=list):
    """Garante conversão segura de listas/dicionários vindos do banco SQLite"""
    if isinstance(valor, tipo_esperado):
        return valor
    if isinstance(valor, str) and valor.strip():
        try:
            res = ast.literal_eval(valor)
            if isinstance(res, tipo_esperado):
                return res
        except:
            pass
    return [] if tipo_esperado == list else {}

# ==============================================================================
# GERADOR DE DOCX (MODELO INSTITUCIONAL SIARCON - PMOC) [source: 1]
# ==============================================================================
def gerar_docx_pmoc(dados):
    doc = Document()
    style = doc.styles['Normal']
    style.font.name = 'Calibri'
    style.font.size = Pt(10.5)
    
    # Capa / Título Oficial [source: 1]
    head = doc.add_heading('PMOC\nPLANO DE MANUTENÇÃO, OPERAÇÃO E CONTROLE', 0)
    head.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_capa = doc.add_paragraph(
        f"Cliente: {dados.get('nome_proprietario', '-')}\n"
        f"Endereço: {dados.get('end_ambiente', '-')}, {dados.get('num_ambiente', '')} - {dados.get('cidade_ambiente', '')}/{dados.get('uf_ambiente', '')}\n"
        f"Contato: {dados.get('tel_proprietario', '-')}\n"
        f"{datetime.now().year}"
    )
    p_capa.alignment = WD_ALIGN_PARAGRAPH.CENTER
    doc.add_page_break()
    
    # RESUMO [source: 1]
    doc.add_heading('RESUMO', level=1)
    doc.add_paragraph(
        "Visando o perfeito estado de conservação e funcionamento de todo o sistema, equipamentos e acessórios, conforme as normas vigentes: "
        "NBR 13.971 (Sistema de Refrigeração, Condicionamento de Ar e Ventilação – Manutenção Programada) da ABNT e Portaria 3.523 do Ministério da Saúde "
        "e Resolução – RE N° 9 de 16 de Janeiro de 2003, (“Orientação Técnica de padrões e referências de Qualidade do Ar Interior, em ambientes climatizados "
        "artificialmente, de uso público e coletivo”) – da Diretoria Colegiada da Agência Nacional de Vigilância Sanitária – ANVISA e Lei Federal 13.589.\n\n"
        "Torna-se necessário utilizar Planos de Manutenção Operação e Controle, para gerenciar a rotina de verificação e inspeção dentro dos prazos estipulados, "
        "ou para a identificação e solução de problemas relacionados ao sistema de AVAC – Aquecimento, Ventilação e Ar-Condicionado. Além disso em acordo com as normas: "
        "Utilizar na limpeza dos componentes do sistema de climatização, produtos biodegradáveis e devidamente registrados no Ministério da Saúde para esse fim. "
        "Preservar a captação de ar externo livre de possíveis fontes de poluentes externas que apresentam riscos à saúde humana."
    )
    
    # 1. DADOS GERAIS [source: 1]
    doc.add_heading('1. DADOS GERAIS', level=1)
    
    doc.add_heading('1.1 Identificação do Ambiente ou Conjunto de Ambientes:', level=2)
    t1_1 = doc.add_table(rows=3, cols=2)
    t1_1.style = 'Table Grid'
    t1_1.rows[0].cells[0].text = f"Nome: {dados.get('nome_ambiente', '-')}"
    t1_1.rows[1].cells[0].text = f"Endereço completo: {dados.get('end_ambiente', '-')}"
    t1_1.rows[1].cells[1].text = f"N.º: {dados.get('num_ambiente', '-')}"
    t1_1.rows[2].cells[0].text = f"Complemento: {dados.get('comp_ambiente', '-')} | Bairro: {dados.get('bairro_ambiente', '-')}"
    t1_1.rows[2].cells[1].text = f"Cidade: {dados.get('cidade_ambiente', '-')} | UF: {dados.get('uf_ambiente', '-')}"
    
    doc.add_heading('1.2 Identificação do Proprietário:', level=2)
    t1_2 = doc.add_table(rows=4, cols=2)
    t1_2.style = 'Table Grid'
    t1_2.rows[0].cells[0].text = f"Nome/Razão Social: {dados.get('nome_proprietario', '-')}"
    t1_2.rows[1].cells[0].text = f"CNPJ N°: {dados.get('cnpj_proprietario', '-')}"
    t1_2.rows[2].cells[0].text = f"Endereço completo: {dados.get('end_proprietario', '-')}"
    t1_2.rows[2].cells[1].text = f"N.º: {dados.get('num_proprietario', '-')}"
    t1_2.rows[3].cells[0].text = f"Telefone: {dados.get('tel_proprietario', '-')}"
    t1_2.rows[3].cells[1].text = f"Email: {dados.get('email_proprietario', '-')}"
    
    doc.add_heading('1.3 Identificação do Responsável Técnico:', level=2)
    t1_3 = doc.add_table(rows=4, cols=2)
    t1_3.style = 'Table Grid'
    t1_3.rows[0].cells[0].text = "Nome / Razão Social: SIARCON ENGENHARIA EIRELI - EPP"
    t1_3.rows[1].cells[0].text = "CNPJ N°: 02.541.727/0001-01"
    t1_3.rows[2].cells[0].text = "Endereço completo: Rua Professor Estevan Lange Adrien | N.º: 450"
    t1_2.rows[2].cells[1].text = "Bairro: Jd. Ns. Sra. Do Amparo | Cidade: Limeira | UF: SP"
    t1_3.rows[3].cells[0].text = "Telefone: (19) 3701-7300"
    t1_3.rows[3].cells[1].text = "Email: contato@siarcon.com.br"
    
    # 2. MAPEAMENTO DO SISTEMA HVAC [source: 1]
    doc.add_heading('2. MAPEAMENTO DO SISTEMA HVAC', level=1)
    doc.add_heading('2.1 Relação de ambientes climatizados:', level=2)
    
    t_amb = doc.add_table(rows=1, cols=6)
    t_amb.style = 'Table Grid'
    hdr_amb = t_amb.rows[0].cells
    hdr_amb[0].text = "Tipo de Atividade"
    hdr_amb[1].text = "Fixos"
    hdr_amb[2].text = "Flutuantes"
    hdr_amb[3].text = "Identificação do Ambiente"
    hdr_amb[4].text = "Área m²"
    hdr_amb[5].text = "Carga Térmica (BTU/h)"
    
    for amb in dados.get('lista_ambientes', []):
        r_amb = t_amb.add_row().cells
        r_amb[0].text = amb.get('atividade', '')
        r_amb[1].text = str(amb.get('fixos', ''))
        r_amb[2].text = str(amb.get('flutuantes', ''))
        r_amb[3].text = amb.get('identificacao', '')
        r_amb[4].text = str(amb.get('area', ''))
        r_amb[5].text = str(amb.get('carga', ''))
        
    doc.add_heading('2.2 Relação de equipamentos presentes no sistema:', level=2)
    t_eq = doc.add_table(rows=1, cols=4)
    t_eq.style = 'Table Grid'
    hdr_eq = t_eq.rows[0].cells
    hdr_eq[0].text = "Equipamento"
    hdr_eq[1].text = "Localização"
    hdr_eq[2].text = "KW"
    hdr_eq[3].text = "TAG"
    
    for eq in dados.get('lista_equipamentos', []):
        r_eq = t_eq.add_row().cells
        r_eq[0].text = eq.get('equipamento', '')
        r_eq[1].text = eq.get('localizacao', '')
        r_eq[2].text = str(eq.get('kw', ''))
        r_eq[3].text = eq.get('tag', '')
        
    # 3. PLANO DE MANUTENÇÃO, OPERAÇÃO E CONTROLE [source: 1]
    doc.add_heading('3. PLANO DE MANUTENÇÃO, OPERAÇÃO E CONTROLE', level=1)
    doc.add_paragraph(
        "Nesta seção encontram-se os itens que devem ser verificados periodicamente de cada equipamento, a nível de componente, "
        "conforme indicados em ABNT NBR 13.971.\n"
        "Legenda: M = Mensal | T = Trimestral | S = Semestral | A = Anual\n"
        "P = Atividades periódicas | NP = Atividades a serem executadas se necessário"
    )
    
    sistemas_selecionados = dados.get('sistemas_selecionados', [])
    for sys_name in sistemas_selecionados:
        doc.add_heading(sys_name, level=2)
        t_sys = doc.add_table(rows=1, cols=3)
        t_sys.style = 'Table Grid'
        h_sys = t_sys.rows[0].cells
        h_sys[0].text = "Descrição da atividade"
        h_sys[1].text = "Periodicidade"
        h_sys[2].text = "Prevista (P/NP)"
        
        for rt in MATRIZ_PMOC_SIARCON.get(sys_name, []):
            row_sys = t_sys.add_row().cells
            row_sys[0].text = rt['item']
            row_sys[1].text = rt['frequencia']
            row_sys[2].text = rt['tipo']
            
    # 4. OBSERVAÇÕES COMPLEMENTARES [source: 1]
    doc.add_heading('4. OBSERVAÇÕES COMPLEMENTARES', level=1)
    doc.add_paragraph(
        "As práticas de manutenção acima devem ser aplicadas em conjunto com as recomendações de manutenção mecânica da NBR 13.971 - "
        "Sistemas de Refrigeração, Condicionamento de Ar e Ventilação - Manutenção Programada da ABNT, assim como aos edifícios da Administração "
        "Pública Federal o disposto no capítulo Práticas de Manutenção, Anexo 3, itens 2.6.3 e 2.6.4 da Portaria n.º 2296/97, de 23 de julho de 1997, "
        "Práticas de Projeto, Construção e Manutenção dos Edifícios Públicos Federais, do Ministério da Administração Federal e Reforma do Estado – MARE. "
        "Todos os produtos utilizados na limpeza dos componentes dos sistemas de climatização devem ser biodegradáveis e estarem devidamente registrados "
        "no Ministério da Saúde para esse fim."
    )
    
    # ANEXO A – PLANILHA DE ACOMPANHAMENTO – PMOC [source: 1]
    doc.add_page_break()
    doc.add_heading('ANEXO A – PLANILHA DE ACOMPANHAMENTO – PMOC', level=1)
    
    for eq in dados.get('lista_equipamentos', [])[:3]: # Exemplo para os primeiros equipamentos cadastrados
        p_anexo = doc.add_paragraph(
            f"Descrição do equipamento: {eq.get('equipamento', '-')}\n"
            f"Setor / Local: {eq.get('localizacao', '-')} | TAG: {eq.get('tag', '-')}"
        )
        t_anx = doc.add_table(rows=1, cols=13)
        t_anx.style = 'Table Grid'
        cols = t_anx.rows[0].cells
        cols[0].text = "Ano / Mês"
        meses = ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun", "Jul", "Ago", "Set", "Out", "Nov", "Dez"]
        for idx_m, nome_m in enumerate(meses):
            cols[idx_m + 1].text = nome_m
            
        r1 = t_anx.add_row().cells; r1[0].text = "Dia do mês"
        r2 = t_anx.add_row().cells; r2[0].text = "Técnico Responsável"
        r3 = t_anx.add_row().cells; r3[0].text = "Assinatura"
        doc.add_paragraph()
        
    b = io.BytesIO()
    doc.save(b)
    b.seek(0)
    return b

# ==============================================================================
# INTERFACE DA APLICAÇÃO STREAMLIT (ABA DE DADOS E MAPEAMENTO SIARCON)
# ==============================================================================
st.set_page_config(page_title=f"SIARCON | {DISCIPLINA_ATUAL}", page_icon="📑", layout="wide")
st.title("📑 PMOC — Plano de Manutenção, Operação e Controle (SIARCON)")
st.caption("Padrão NBR 13.971, Portaria 3.523 MS, RE Nº 9/03 ANVISA e Lei 13.589 [source: 1]")

id_projeto = st.session_state.get('id_projeto_editar')
dados_edit = utils_db.buscar_projeto_por_id(id_projeto) if id_projeto else {}

tab1, tab2, tab3, tab4 = st.tabs([
    "1. Dados Gerais (1.1 a 1.3)",
    "2. Mapeamento HVAC (2.1 e 2.2)",
    "3. Seleção da Matriz PMOC",
    "4. Emissão DOCX (com Anexo A)"
])

with tab1:
    st.subheader("1.1 Identificação do Ambiente ou Conjunto de Ambientes [source: 1]")
    col_a1, col_a2 = st.columns(2)
    nome_ambiente = col_a1.text_input("Nome do Empreendimento / Ambiente:", value=dados_edit.get('nome_ambiente', ''))
    end_ambiente = col_a1.text_input("Endereço COMPLETO:", value=dados_edit.get('end_ambiente', ''))
    num_ambiente = col_a2.text_input("Número:", value=dados_edit.get('num_ambiente', ''))
    bairro_ambiente = col_a2.text_input("Bairro / Cidade / UF:", value=dados_edit.get('bairro_ambiente', ''))

    st.divider()
    st.subheader("1.2 Identificação do Proprietário [source: 1]")
    col_p1, col_p2 = st.columns(2)
    nome_prop = col_p1.text_input("Nome / Razão Social do Cliente:", value=dados_edit.get('nome_prop', ''))
    cnpj_prop = col_p1.text_input("CNPJ Nº:", value=dados_edit.get('cnpj_prop', ''))
    tel_prop = col_p2.text_input("Telefone do Contato:", value=dados_edit.get('tel_prop', ''))
    email_prop = col_p2.text_input("E-mail de Contato:", value=dados_edit.get('email_prop', ''))

    st.info("ℹ️ **1.3 Identificação do Responsável Técnico:** Fixo como **SIARCON ENGENHARIA EIRELI - EPP** (CNPJ: 02.541.727/0001-01 / Limeira-SP) [source: 1].")

with tab2:
    st.subheader("2.1 Relação de Ambientes Climatizados [source: 1]")
    st.caption("Insira os ambientes que fazem parte da cobertura do PMOC.")
    
    lista_ambientes = converter_para_estrutura(dados_edit.get('lista_ambientes', []), list)
    if not lista_ambientes:
        lista_ambientes = [{"atividade": "Escritório / Administrativo", "fixos": 20, "flutuantes": 5, "identificacao": "Salas 01 a 04", "area": 120, "carga": "60.000 BTU/h"}]
        
    for i, amb in enumerate(lista_ambientes):
        c1, c2, c3, c4, c5 = st.columns([3, 1, 1, 3, 2])
        amb['atividade'] = c1.text_input("Atividade", value=amb.get('atividade', ''), key=f"at_{i}")
        amb['fixos'] = c2.number_input("Fixos", value=int(amb.get('fixos', 0)), key=f"fix_{i}")
        amb['flutuantes'] = c3.number_input("Flutuantes", value=int(amb.get('flutuantes', 0)), key=f"flut_{i}")
        amb['identificacao'] = c4.text_input("Identificação do Ambiente", value=amb.get('identificacao', ''), key=f"id_{i}")
        amb['carga'] = c5.text_input("Carga Térmica (BTU/h)", value=amb.get('carga', ''), key=f"cg_{i}")

    st.divider()
    st.subheader("2.2 Relação de Equipamentos Presentes no Sistema [source: 1]")
    lista_eq = converter_para_estrutura(dados_edit.get('lista_equipamentos', []), list)
    if not lista_eq:
        lista_eq = [{"equipamento": "Chiller Parafuso / Fancoil", "localizacao": "Casa de Máquinas / Cobertura", "kw": 45, "tag": "CH-01"}]
        
    for j, eq in enumerate(lista_eq):
        c_eq1, c_eq2, c_eq3, c_eq4 = st.columns([3, 3, 1, 2])
        eq['equipamento'] = c_eq1.text_input("Equipamento", value=eq.get('equipamento', ''), key=f"eq_{j}")
        eq['localizacao'] = c_eq2.text_input("Localização", value=eq.get('localizacao', ''), key=f"loc_{j}")
        eq['kw'] = c_eq3.number_input("KW", value=int(eq.get('kw', 0)), key=f"kw_{j}")
        eq['tag'] = c_eq4.text_input("TAG", value=eq.get('tag', ''), key=f"tag_{j}")

with tab3:
    st.subheader("3. Categorias e Rotinas Técnicas da Obra [source: 1]")
    st.write("Selecione os grupos técnicos da ABNT NBR 13.971 aplicáveis aos equipamentos instalados [source: 1]:")
    
    opcoes_cat = list(MATRIZ_PMOC_SIARCON.keys())
    sistemas_salvos = converter_para_estrutura(dados_edit.get('sistemas_selecionados', []), list)
    sistemas_default = [s for s in sistemas_salvos if s in opcoes_cat] or opcoes_cat[:4]
    
    sistemas_selecionados = st.multiselect(
        "Selecione as seções que comporão o PMOC:",
        options=opcoes_cat,
        default=sistemas_default
    )
    
    st.caption("✔️ As rotinas mensais (M), trimestrais (T), semestrais (S) e anuais (A) com indicação Periódica (P) ou Não Periódica (NP) serão automaticamente inseridas nas tabelas do relatório Word [source: 1].")

with tab4:
    st.subheader("4. Geração do Documento PMOC SIARCON (Word DOCX)")
    st.write("O documento será exportado contendo o Resumo Normativo, Identificação Completa, Mapeamento HVAC, Matriz Preventiva e o Anexo A (Planilha de Controle Mês a Mês) [source: 1].")
    
    dados_pmoc = {
        '_id': dados_edit.get('_id'),
        'disciplina': DISCIPLINA_ATUAL,
        'nome_ambiente': nome_ambiente,
        'end_ambiente': end_ambiente,
        'num_ambiente': num_ambiente,
        'bairro_ambiente': bairro_ambiente,
        'cidade_ambiente': '',
        'uf_ambiente': 'SP',
        'nome_proprietario': nome_prop,
        'cnpj_proprietario': cnpj_prop,
        'tel_proprietario': tel_prop,
        'email_proprietario': email_prop,
        'lista_ambientes': lista_ambientes,
        'lista_equipamentos': lista_eq,
        'sistemas_selecionados': sistemas_selecionados,
        'data_inicio': dados_edit.get('data_inicio', date.today().strftime("%Y-%m-%d"))
    }
    
    col_b1, col_b2 = st.columns(2)
    with col_b1:
        if st.button("☁️ SALVAR REGISTRO NO DB SIARCON"):
            if utils_db.registrar_projeto(dados_pmoc):
                st.success("✅ PMOC salvo com sucesso no banco de dados!")
    with col_b2:
        if st.button("💾 SALVAR E GERAR DOCX PMOC OFICIAL", type="primary"):
            if utils_db.registrar_projeto(dados_pmoc):
                st.success("✅ Documento gerado conforme padrão SIARCON [source: 1]! Baixe no botão abaixo:")
                st.session_state['btn_docx_pmoc_oficial'] = True
                
        if st.session_state.get('btn_docx_pmoc_oficial', False):
            b_docx = gerar_docx_pmoc(dados_pmoc)
            st.download_button(
                label="📥 BAIXAR PMOC (FORMATO OFICIAL SIARCON .DOCX)",
                data=b_docx,
                file_name=f"PMOC_SIARCON_{nome_ambiente.replace(' ', '_') or 'Obra'}.docx",
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            )
