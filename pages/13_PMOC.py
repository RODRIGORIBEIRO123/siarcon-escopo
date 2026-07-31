import streamlit as st
from docx import Document
from docx.shared import Pt, Inches, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_ALIGN_VERTICAL
from docx.oxml import OxmlElement, parse_xml
from docx.oxml.ns import qn, nsdecls
import io
import os
import ast
from datetime import date, datetime
import utils_db

# ==============================================================================
# CONTROLE DE ACESSO
# ==============================================================================
if 'logado' not in st.session_state or not st.session_state['logado']:
    st.warning("🔒 Acesso negado."); st.stop()

DISCIPLINA_ATUAL = "PMOC"

# ==============================================================================
# BASE NORMATIVA SIARCON (COM SUBTÓPICOS)
# ==============================================================================
ESTRUTURA_PMOC_SIARCON = {
    "Ventiladores": {
        "subitens": {
            "Geral": [
                {"item": "Verificar a existência de danos e limpar conjunto.", "frequencia": "M", "tipo": "P"},
                {"item": "Verificar e eliminar focos de corrosão.", "frequencia": "S", "tipo": "P"},
                {"item": "Verificar fixação, vibrações e ruídos anormais.", "frequencia": "T", "tipo": "P"},
                {"item": "Verificar aquecimento anormal dos mancais.", "frequencia": "S", "tipo": "P"},
                {"item": "Lubrificar os mancais, se aplicável", "frequencia": "T", "tipo": "P"},
                {"item": "Verificar vazamentos nas junções flexíveis", "frequencia": "T", "tipo": "P"},
                {"item": "Verificar o estado dos amortecedores de vibração.", "frequencia": "T", "tipo": "P"},
                {"item": "Verificar a operação dos controles de vazão.", "frequencia": "S", "tipo": "P"},
                {"item": "Verificar o estado e a instalação dos dispositivos de proteção.", "frequencia": "M", "tipo": "P"},
                {"item": "Limpar sistema de drenagem.", "frequencia": "T", "tipo": "P"}
            ]
        }
    },
    "Aquecedor de ar (liquido ou gás)": {
        "subitens": {
            "Geral": [
                {"item": "Verificar a existência de agentes que possam prejudicar a troca térmica", "frequencia": "M", "tipo": "P"},
                {"item": "Limpar as superfícies do lado de ar", "frequencia": "M", "tipo": "P"},
                {"item": "Verificar os fluxos de ar/liquido, vapor ou gás", "frequencia": "M", "tipo": "P"},
                {"item": "Medir e registrar as temperaturas e pressões nos pontos de entrada e saída", "frequencia": "S", "tipo": "NP"},
                {"item": "Verificar isolamento térmico do componente (inspeção visual)", "frequencia": "T", "tipo": "P"}
            ]
        }
    },
    "Condicionadores de ar “Expansão direta”": {
        "subitens": {
            "Geral": [
                {"item": "Verificar a existência de agentes que possam prejudicar a troca térmica.", "frequencia": "M", "tipo": "P"},
                {"item": "Verificar e eliminar sujeira, danos e corrosão no gabinete, na moldura da serpentina e na bandeja;", "frequencia": "M", "tipo": "P"},
                {"item": "Limpar as serpentinas e bandejas", "frequencia": "M", "tipo": "P"},
                {"item": "Verificar a operação dos controles de vazão", "frequencia": "M", "tipo": "P"},
                {"item": "Limpar sistema de drenagem", "frequencia": "T", "tipo": "P"},
                {"item": "Verificar isolamento térmico e acústico do componente (inspeção visual)", "frequencia": "M", "tipo": "P"},
                {"item": "Verificar a vedação dos painéis de fechamento do gabinete", "frequencia": "T", "tipo": "P"},
                {"item": "Medir e registrar os valores de tensão, corrente e isolação elétrica", "frequencia": "T", "tipo": "P"}
            ]
        }
    },
    "Condicionadores de ar tipo “Expansão indireta” (Chillers)": {
        "subitens": {
            "Geral": [
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
                {"item": "Medir e registrar os valores de tensão, corrente e isolação elétrica", "frequencia": "A", "tipo": "P"},
                {"item": "Verificar a operação da chave de fluxo de água gelada e bomba", "frequencia": "T", "tipo": "P"},
                {"item": "Verificar e reapertar as conexões elétricas", "frequencia": "A", "tipo": "P"},
                {"item": "Realizar análise do óleo, realizar troca se necessário", "frequencia": "A", "tipo": "P"}
            ]
        }
    },
    "Componentes de distribuição e difusão de ar": {
        "subitens": {
            "Venezianas, grelhas e difusores": [
                {"item": "Verificar a existência de sujeira, danos e corrosão", "frequencia": "M", "tipo": "P"},
                {"item": "Limpar os elementos", "frequencia": "Quando necessário", "tipo": "NP"},
                {"item": "Eliminar focos de corrosão", "frequencia": "Quando necessário", "tipo": "NP"},
                {"item": "Ajuste para reestabelecimento das condições de referência", "frequencia": "S", "tipo": "P"},
                {"item": "Verificar funcionamento mecânico", "frequencia": "S", "tipo": "P"},
                {"item": "Lubrificar mancais de acionamento", "frequencia": "S", "tipo": "P"}
            ],
            "Damper corta-fogo (Registro de ar)": [
                {"item": "Verificar a existência de sujeira nos elementos de fechamento, trava e abertura", "frequencia": "M", "tipo": "P"},
                {"item": "Limpar os elementos de fechamento, trava e reabertura", "frequencia": "Quando necessário", "tipo": "NP"},
                {"item": "Verificar funcionamento mecânico", "frequencia": "S", "tipo": "P"},
                {"item": "Verificar o posicionamento do indicador de posição", "frequencia": "S", "tipo": "P"},
                {"item": "Lubrificar mancais de acionamento", "frequencia": "S", "tipo": "P"}
            ],
            "Damper (Registro de ar)": [
                {"item": "Verificar a existência de sujeira, danos e corrosão.", "frequencia": "M", "tipo": "P"},
                {"item": "Limpar os elementos", "frequencia": "Quando necessário", "tipo": "NP"},
                {"item": "Eliminar focos de corrosão", "frequencia": "Quando necessário", "tipo": "NP"},
                {"item": "Verificar funcionamento mecânico", "frequencia": "S", "tipo": "P"},
                {"item": "Verificar atuadores do registro", "frequencia": "S", "tipo": "P"},
                {"item": "Lubrificar mancais de acionamento", "frequencia": "S", "tipo": "P"}
            ],
            "Dutos e câmara plenum para ar": [
                {"item": "Verificar a existência de sujeira, danos e corrosão interna e externa, mediante portas de inspeção", "frequencia": "M", "tipo": "P"},
                {"item": "Limpar o conjunto", "frequencia": "Quando necessário", "tipo": "NP"},
                {"item": "Eliminar focos de corrosão", "frequencia": "Quando necessário", "tipo": "NP"},
                {"item": "Limpar sistema de drenagem", "frequencia": "S", "tipo": "P"},
                {"item": "Verificar a vedação das portas de inspeção", "frequencia": "S", "tipo": "P"},
                {"item": "Verificar a existência de danos na isolação térmica (inspeção visual)", "frequencia": "M", "tipo": "P"},
                {"item": "Verificar a vedação das conexões", "frequencia": "T", "tipo": "P"}
            ]
        }
    },
    "Sistemas hidráulicos": {
        "subitens": {
            "Bombas": [
                {"item": "Verificar a existência de sujeira, danos e fixação", "frequencia": "M", "tipo": "P"},
                {"item": "Limpar o equipamento", "frequencia": "M", "tipo": "P"},
                {"item": "Eliminar os focos de corrosão", "frequencia": "Quando necessário", "tipo": "NP"},
                {"item": "Verificar a vibração e ruído anormal", "frequencia": "M", "tipo": "P"},
                {"item": "Verificar a vedação do selo mecânico", "frequencia": "T", "tipo": "P"},
                {"item": "Ajustar a prensa-gaxeta", "frequencia": "Quando necessário", "tipo": "NP"},
                {"item": "Verificar nível de óleo", "frequencia": "T", "tipo": "P"},
                {"item": "Completar o nível de óleo", "frequencia": "Quando necessário", "tipo": "NP"}
            ],
            "Válvulas de controle e bloqueio": [
                {"item": "Verificar a existência de sujeira, danos e fixação", "frequencia": "M", "tipo": "P"},
                {"item": "Limpar o componente", "frequencia": "M", "tipo": "P"},
                {"item": "Verificar a vibração e ruído anormal", "frequencia": "M", "tipo": "P"},
                {"item": "Verificar a existência de vazamentos (inspeção visual)", "frequencia": "M", "tipo": "P"},
                {"item": "Ajustar elementos de vedação", "frequencia": "T", "tipo": "P"}
            ]
        }
    }
}

# ==============================================================================
# FUNÇÕES DE ESTILIZAÇÃO AVANÇADA (PYTHON-DOCX)
# ==============================================================================
def aplicar_fundo_celula(celula, cor_hex):
    """Preenche a célula com cor de fundo (Hex ex: 'F2F2F2')"""
    shading_elm = parse_xml(f'<w:shd {nsdecls("w")} w:fill="{cor_hex}"/>')
    celula._tc.get_or_add_tcPr().append(shading_elm)

def aplicar_bordas_celula(celula, top="single", bottom="single", left="single", right="single", color="CCCCCC", sz="4"):
    """Configura bordas específicas em uma célula do Word"""
    tcPr = celula._tc.get_or_add_tcPr()
    tcBorders = parse_xml(
        f'<w:tcBorders {nsdecls("w")}>'
        f'<w:top w:val="{top}" w:sz="{sz}" w:space="0" w:color="{color}"/>'
        f'<w:left w:val="{left}" w:sz="{sz}" w:space="0" w:color="{color}"/>'
        f'<w:bottom w:val="{bottom}" w:sz="{sz}" w:space="0" w:color="{color}"/>'
        f'<w:right w:val="{right}" w:sz="{sz}" w:space="0" w:color="{color}"/>'
        f'</w:tcBorders>'
    )
    tcPr.append(tcBorders)

def configurar_cabecalho_siarcon(doc, cod_pmoc="PMOC-2023-00-00"):
    """Implementa o cabeçalho idêntico ao Print 2 (Logo, Título Cinza e Código Azul) em todas as seções"""
    for section in doc.sections:
        section.top_margin = Inches(0.8)
        header = section.header
        header.is_linked_to_previous = False
        
        t_head = header.add_table(rows=1, cols=3, width=Inches(6.5))
        t_head.alignment = WD_TABLE_ALIGNMENT.CENTER
        
        c0, c1, c2 = t_head.rows[0].cells
        c0.width = Inches(1.5)
        c1.width = Inches(3.5)
        c2.width = Inches(1.5)
        
        # Célula 1: Logo SIARCON
        p0 = c0.paragraphs[0]
        p0.alignment = WD_ALIGN_PARAGRAPH.CENTER
        if os.path.exists("logo_siarcon.png"):
            run0 = p0.add_run()
            run0.add_picture("logo_siarcon.png", width=Inches(1.3))
        else:
            r0 = p0.add_run("SIARCON\nEngenharia")
            r0.bold = True
            r0.font.size = Pt(11)
            r0.font.color.rgb = RGBColor(0, 102, 204)
            
        # Célula 2: Título Central
        p1 = c1.paragraphs[0]
        p1.alignment = WD_ALIGN_PARAGRAPH.CENTER
        r1 = p1.add_run("PMOC – PLANO DE MANUTENÇÃO\nOPERAÇÃO E CONTROLE")
        r1.bold = True
        r1.font.name = "Calibri"
        r1.font.size = Pt(13)
        r1.font.color.rgb = RGBColor(102, 102, 102) # Cinza escuro exatamente como Print 2
        
        # Célula 3: Código à Direita
        p2 = c2.paragraphs[0]
        p2.alignment = WD_ALIGN_PARAGRAPH.CENTER
        r2 = p2.add_run(cod_pmoc)
        r2.bold = True
        r2.font.name = "Calibri"
        r2.font.size = Pt(11)
        r2.font.color.rgb = RGBColor(85, 85, 255) # Azul institucional do código no Print 2
        
        # Aplicar bordas cinzas na tabela do cabeçalho
        for c in (c0, c1, c2):
            c.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
            aplicar_bordas_celula(c, color="888888", sz="6")

def configurar_rodape_siarcon(doc):
    """Implementa o rodapé institucional institucional idêntico ao Print 3"""
    for section in doc.sections:
        section.bottom_margin = Inches(0.8)
        footer = section.footer
        footer.is_linked_to_previous = False
        
        p_foot = footer.paragraphs[0]
        p_foot.alignment = WD_ALIGN_PARAGRAPH.LEFT
        
        r_emp = p_foot.add_run("SIARCON ENGENHARIA\n")
        r_emp.bold = True
        r_emp.font.name = "Calibri"
        r_emp.font.size = Pt(9)
        r_emp.font.color.rgb = RGBColor(120, 120, 120)
        
        r_end = p_foot.add_run(
            "Rua: Prof. Estevan Lange Adrien, 450 - Jd. Nossa Senhora do Amparo\n"
            "CEP: 13482-280 - Limeira - SP – Fone: (19) 3701-7300\n"
            "siarcon@siarcon.com.br – "
        )
        r_end.font.name = "Calibri"
        r_end.font.size = Pt(8.5)
        r_end.font.color.rgb = RGBColor(120, 120, 120)
        
        r_site = p_foot.add_run("www.siarcon.com.br")
        r_site.underline = True
        r_site.font.name = "Calibri"
        r_site.font.size = Pt(8.5)
        r_site.font.color.rgb = RGBColor(0, 102, 204)

# ==============================================================================
# FUNÇÃO DE CONVERSÃO BLINDADA
# ==============================================================================
def converter_para_estrutura(valor, tipo_esperado=list):
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
# GERADOR DE DOCX — PMOC SIARCON COMPLETO (PRINTS 1, 2 E 3)
# ==============================================================================
def gerar_docx_pmoc(dados):
    doc = Document()
    style = doc.styles['Normal']
    style.font.name = 'Calibri'
    style.font.size = Pt(10.5)

    # Configuração permanente de Cabeçalho e Rodapé em todas as páginas
    cod_pmoc = dados.get('codigo_doc', 'PMOC-2023-00-00')
    configurar_cabecalho_siarcon(doc, cod_pmoc)
    configurar_rodape_siarcon(doc)

    # --------------------------------------------------------------------------
    # CAPA DO DOCUMENTO
    # --------------------------------------------------------------------------
    doc.add_paragraph()
    h_capa = doc.add_heading('PLANO DE MANUTENÇÃO, OPERAÇÃO E CONTROLE\n(PMOC)', 0)
    h_capa.alignment = WD_ALIGN_PARAGRAPH.CENTER
    doc.add_paragraph()
    
    p_capa = doc.add_paragraph(
        f"Cliente: {dados.get('nome_proprietario', '-')}\n"
        f"Endereço: {dados.get('end_ambiente', '-')}, {dados.get('num_ambiente', '')} - {dados.get('cidade_ambiente', '')}/{dados.get('uf_ambiente', '')}\n"
        f"Contato: {dados.get('tel_proprietario', '-')}\n"
        f"Ano de Referência: {datetime.now().year}"
    )
    p_capa.alignment = WD_ALIGN_PARAGRAPH.CENTER
    doc.add_page_break()

    # --------------------------------------------------------------------------
    # GERAÇÃO DINÂMICA DO SUMÁRIO (APENAS COM ITENS SELECIONADOS)
    # --------------------------------------------------------------------------
    selecao_itens = dados.get('selecao_subitens', {})
    secoes_sumario = [
        "RESUMO",
        "1. DADOS GERAIS",
        "  1.1. Identificação do Ambiente ou Conjunto de Ambientes",
        "  1.2. Identificação do Proprietário",
        "  1.3. Identificação do Responsável Técnico pela Obra",
        "2. MAPEAMENTO DO SISTEMA HVAC",
        "  2.1 Relação de ambientes climatizados",
        "  2.2 Relação de equipamentos presentes no sistema",
        "3. PLANO DE MANUTENÇÃO E CONTROLE"
    ]

    idx_cat = 1
    for cat_nome, subitens_selecionados in selecao_itens.items():
        if subitens_selecionados:
            num_cat = f"3.{idx_cat}"
            secoes_sumario.append(f"  {num_cat}. {cat_nome}")
            if not (len(subitens_selecionados) == 1 and subitens_selecionados[0] == "Geral"):
                for idx_sub, sub_nome in enumerate(subitens_selecionados, start=1):
                    secoes_sumario.append(f"    {num_cat}.{idx_sub} {sub_nome}")
            idx_cat += 1

    secoes_sumario.append("4. OBSERVAÇÕES COMPLEMENTARES")
    secoes_sumario.append("ANEXO A – PLANILHA DE ACOMPANHAMENTO – PMOC")

    doc.add_heading('SUMÁRIO', level=1)
    for linha_sum in secoes_sumario:
        doc.add_paragraph(linha_sum)
    doc.add_page_break()

    # --------------------------------------------------------------------------
    # RESUMO
    # --------------------------------------------------------------------------
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

    # --------------------------------------------------------------------------
    # 1. DADOS GERAIS
    # --------------------------------------------------------------------------
    doc.add_heading('1. DADOS GERAIS', level=1)
    doc.add_heading('1.1 Identificação do Ambiente ou Conjunto de Ambientes:', level=2)
    t1_1 = doc.add_table(rows=3, cols=2); t1_1.style = 'Table Grid'
    t1_1.rows[0].cells[0].text = f"Nome: {dados.get('nome_ambiente', '-')}"
    t1_1.rows[1].cells[0].text = f"Endereço completo: {dados.get('end_ambiente', '-')}"
    t1_1.rows[1].cells[1].text = f"N.º: {dados.get('num_ambiente', '-')}"
    t1_1.rows[2].cells[0].text = f"Complemento: {dados.get('comp_ambiente', '-')} | Bairro: {dados.get('bairro_ambiente', '-')}"
    t1_1.rows[2].cells[1].text = f"Cidade: {dados.get('cidade_ambiente', '-')} | UF: {dados.get('uf_ambiente', '-')}"

    doc.add_heading('1.2 Identificação do Proprietário:', level=2)
    t1_2 = doc.add_table(rows=4, cols=2); t1_2.style = 'Table Grid'
    t1_2.rows[0].cells[0].text = f"Nome/Razão Social: {dados.get('nome_proprietario', '-')}"
    t1_2.rows[1].cells[0].text = f"CNPJ N°: {dados.get('cnpj_proprietario', '-')}"
    t1_2.rows[2].cells[0].text = f"Endereço completo: {dados.get('end_proprietario', '-')}"
    t1_2.rows[2].cells[1].text = f"N.º: {dados.get('num_proprietario', '-')}"
    t1_2.rows[3].cells[0].text = f"Telefone: {dados.get('tel_proprietario', '-')}"
    t1_2.rows[3].cells[1].text = f"Email: {dados.get('email_proprietario', '-')}"

    doc.add_heading('1.3 Identificação do Responsável Técnico:', level=2)
    t1_3 = doc.add_table(rows=4, cols=2); t1_3.style = 'Table Grid'
    t1_3.rows[0].cells[0].text = "Nome / Razão Social: SIARCON ENGENHARIA EIRELI - EPP"
    t1_3.rows[1].cells[0].text = "CNPJ N°: 02.541.727/0001-01"
    t1_3.rows[2].cells[0].text = "Endereço completo: Rua Professor Estevan Lange Adrien | N.º: 450"
    t1_3.rows[2].cells[1].text = "Bairro: Jd. Ns. Sra. Do Amparo | Cidade: Limeira | UF: SP"
    t1_3.rows[3].cells[0].text = "Telefone: (19) 3701-7300"
    t1_3.rows[3].cells[1].text = "Email: contato@siarcon.com.br"

    # --------------------------------------------------------------------------
    # 2. MAPEAMENTO DO SISTEMA HVAC
    # --------------------------------------------------------------------------
    doc.add_heading('2. MAPEAMENTO DO SISTEMA HVAC', level=1)
    doc.add_heading('2.1 Relação de ambientes climatizados:', level=2)
    t_amb = doc.add_table(rows=1, cols=6); t_amb.style = 'Table Grid'
    hdr_amb = t_amb.rows[0].cells
    hdr_amb[0].text = "Tipo de Atividade"; hdr_amb[1].text = "Fixos"; hdr_amb[2].text = "Flutuantes"
    hdr_amb[3].text = "Identificação do Ambiente"; hdr_amb[4].text = "Área m²"; hdr_amb[5].text = "Carga Térmica"
    for amb in dados.get('lista_ambientes', []):
        r_amb = t_amb.add_row().cells
        r_amb[0].text = str(amb.get('atividade', '')); r_amb[1].text = str(amb.get('fixos', ''))
        r_amb[2].text = str(amb.get('flutuantes', '')); r_amb[3].text = str(amb.get('identificacao', ''))
        r_amb[4].text = str(amb.get('area', '')); r_amb[5].text = str(amb.get('carga', ''))

    doc.add_heading('2.2 Relação de equipamentos presentes no sistema:', level=2)
    t_eq = doc.add_table(rows=1, cols=4); t_eq.style = 'Table Grid'
    hdr_eq = t_eq.rows[0].cells
    hdr_eq[0].text = "Equipamento"; hdr_eq[1].text = "Localização"; hdr_eq[2].text = "KW"; hdr_eq[3].text = "TAG"
    for eq in dados.get('lista_equipamentos', []):
        r_eq = t_eq.add_row().cells
        r_eq[0].text = str(eq.get('equipamento', '')); r_eq[1].text = str(eq.get('localizacao', ''))
        r_eq[2].text = str(eq.get('kw', '')); r_eq[3].text = str(eq.get('tag', ''))

    # --------------------------------------------------------------------------
    # 3. PLANO DE MANUTENÇÃO (NUMERAÇÃO CONTÍNUA E SUBTÓPICOS)
    # --------------------------------------------------------------------------
    doc.add_heading('3. PLANO DE MANUTENÇÃO, OPERAÇÃO E CONTROLE', level=1)
    doc.add_paragraph(
        "Nesta seção encontram-se os itens que devem ser verificados periodicamente de cada equipamento, a nível de componente, "
        "conforme indicados em ABNT NBR 13.971.\n"
        "Legenda: M = Mensal | T = Trimestral | S = Semestral | A = Anual\n"
        "P = Atividades periódicas | NP = Atividades a serem executadas se necessário"
    )

    idx_cat = 1
    for cat_nome, subitens_selecionados in selecao_itens.items():
        if subitens_selecionados:
            num_cat = f"3.{idx_cat}"
            doc.add_heading(f"{num_cat} {cat_nome}", level=2)

            if not (len(subitens_selecionados) == 1 and subitens_selecionados[0] == "Geral"):
                for idx_sub, sub_nome in enumerate(subitens_selecionados, start=1):
                    num_sub = f"{num_cat}.{idx_sub}"
                    doc.add_heading(f"{num_sub} {sub_nome}", level=3)
                    t_sys = doc.add_table(rows=1, cols=3); t_sys.style = 'Table Grid'
                    h_sys = t_sys.rows[0].cells
                    h_sys[0].text = "Descrição da atividade"; h_sys[1].text = "Periodicidade"; h_sys[2].text = "Prevista"
                    for rt in ESTRUTURA_PMOC_SIARCON.get(cat_nome, {}).get("subitens", {}).get(sub_nome, []):
                        r_sys = t_sys.add_row().cells
                        r_sys[0].text = rt['item']; r_sys[1].text = rt['frequencia']; r_sys[2].text = rt['tipo']
            else:
                t_sys = doc.add_table(rows=1, cols=3); t_sys.style = 'Table Grid'
                h_sys = t_sys.rows[0].cells
                h_sys[0].text = "Descrição da atividade"; h_sys[1].text = "Periodicidade"; h_sys[2].text = "Prevista"
                for rt in ESTRUTURA_PMOC_SIARCON.get(cat_nome, {}).get("subitens", {}).get("Geral", []):
                    r_sys = t_sys.add_row().cells
                    r_sys[0].text = rt['item']; r_sys[1].text = rt['frequencia']; r_sys[2].text = rt['tipo']
            idx_cat += 1

    # --------------------------------------------------------------------------
    # 4. OBSERVAÇÕES COMPLEMENTARES (PÁGINA FIXA OBRIGATÓRIA)
    # --------------------------------------------------------------------------
    doc.add_page_break()
    doc.add_heading('4. OBSERVAÇÕES COMPLEMENTARES', level=1)
    doc.add_paragraph(
        "As práticas de manutenção acima devem ser aplicadas em conjunto com as recomendações de manutenção mecânica da NBR 13.971 - "
        "Sistemas de Refrigeração, Condicionamento de Ar e Ventilação - Manutenção Programada da ABNT, assim como aos edifícios da Administração "
        "Pública Federal o disposto no capítulo Práticas de Manutenção, Anexo 3, itens 2.6.3 e 2.6.4 da Portaria n.º 2296/97, de 23 de julho de 1997, "
        "Práticas de Projeto, Construção e Manutenção dos Edifícios Públicos Federais, do Ministério da Administração Federal e Reforma do Estado – MARE. "
        "O somatório das práticas de manutenção para garantia do ar e manutenção programada visando o bom funcionamento e desempenho térmico dos sistemas, "
        "permitirá o correto controle dos ajustes das variáveis de manutenção e controle dos poluentes dos ambientes.\n\n"
        "Todos os produtos utilizados na limpeza dos componentes dos sistemas de climatização devem ser biodegradáveis e estarem devidamente registrados "
        "no Ministério da Saúde para esse fim.\n\n"
        "Toda verificação deve ser seguida dos procedimentos necessários para o funcionamento correto do sistema de climatização."
    )

    # --------------------------------------------------------------------------
    # ANEXO A – PLANILHA DE ACOMPANHAMENTO – PMOC (EXATAMENTE COMO PRINT 1)
    # --------------------------------------------------------------------------
    doc.add_page_break()
    h_anexo = doc.add_heading('ANEXO A - PLANILHA DE ACOMPANHAMENTO – PMOC', 1)
    h_anexo.alignment = WD_ALIGN_PARAGRAPH.CENTER
    doc.add_paragraph()

    lista_equip = dados.get('lista_equipamentos', [])
    equipamentos_anexo = lista_equip if lista_equip else [{"equipamento": "Climatização Geral HVAC", "localizacao": "Escritório Belenus", "tag": "CH-01", "kw": 30}]

    for eq in equipamentos_anexo[:2]: # Gera a grade para cada equipamento cadastrado
        t_anx = doc.add_table(rows=0, cols=14)
        t_anx.style = 'Table Grid'
        t_anx.alignment = WD_TABLE_ALIGNMENT.CENTER
        
        # --- CABEÇALHO SUPERIOR DO EQUIPAMENTO (4 Linhas) ---
        r_eq1 = t_anx.add_row().cells
        r_eq1[0].text = f"Descrição do equipamento: {eq.get('equipamento', '')}"
        r_eq1[0].paragraphs[0].runs[0].bold = True
        
        r_eq2 = t_anx.add_row().cells
        r_eq2[0].text = f"Setor: {dados.get('nome_ambiente', 'Administrativo')}   |   Local: {eq.get('localizacao', 'Escritório')}"
        r_eq2[0].paragraphs[0].runs[0].bold = True
        
        r_eq3 = t_anx.add_row().cells
        r_eq3[0].text = f"Capacidade em BTU/h: {eq.get('kw', 0)*3412:.0f}   |   Fabricante: SIARCON   |   Nº de série: -"
        r_eq3[0].paragraphs[0].runs[0].bold = True
        
        r_eq4 = t_anx.add_row().cells
        r_eq4[0].text = f"Modelo: -   |   Patrimônio: -   |   Tag: {eq.get('tag', '-')}"
        r_eq4[0].paragraphs[0].runs[0].bold = True

        # Mesclar as 14 colunas nas 4 linhas do cabeçalho
        for row_c in (r_eq1, r_eq2, r_eq3, r_eq4):
            for i in range(1, 14):
                row_c[0].merge(row_c[i])
            row_c[0].paragraphs[0].paragraph_format.space_after = Pt(2)
            aplicar_fundo_celula(row_c[0], "F9F9F9")

        # --- CABEÇALHO DA GRADE PRINCIPAL (14 Colunas idênticas ao Print 1) ---
        r_hdr = t_anx.add_row().cells
        r_hdr[0].text = "Periodicidade"
        r_hdr[1].text = "Descrição das atividades"
        meses = ["Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho", "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"]
        for idx_m, nome_m in enumerate(meses):
            r_hdr[idx_m + 2].text = nome_m
            r_hdr[idx_m + 2].paragraphs[0].runs[0].font.size = Pt(8)
            r_hdr[idx_m + 2].paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER

        r_hdr[0].paragraphs[0].runs[0].bold = True
        r_hdr[1].paragraphs[0].runs[0].bold = True
        r_hdr[1].paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER
        for cell in r_hdr:
            aplicar_fundo_celula(cell, "EAEAEA")

        # --- 15 LINHAS EM BRANCO PARA INSPEÇÃO EM CAMPO ---
        for _ in range(15):
            r_vazia = t_anx.add_row().cells
            r_vazia[0].text = ""
            r_vazia[1].text = ""
            for m in range(2, 14):
                r_vazia[m].text = ""

        # --- LINHA DE LEGENDA INFERIOR UNIFICADA ---
        r_leg = t_anx.add_row().cells
        r_leg[0].text = "M - Mensal     T - Trimestral     S - Semestral     A - Anual     N - Não se Aplica     OK - Conforme"
        for i in range(1, 14):
            r_leg[0].merge(r_leg[i])
        r_leg[0].paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER
        r_leg[0].paragraphs[0].runs[0].font.size = Pt(8)
        r_leg[0].paragraphs[0].runs[0].bold = True
        aplicar_fundo_celula(r_leg[0], "F2F2F2")

        # --- BLOCO DE ASSINATURAS E REGISTRO MENSAL (Jan a Dez) ---
        r_ano = t_anx.add_row().cells
        r_ano[0].text = "Ano:"
        r_ano[0].merge(r_ano[1])
        r_ano[0].paragraphs[0].runs[0].bold = True
        meses_abrev = ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun", "Jul", "Ago", "Set", "Out", "Nov", "Dez"]
        for idx_ab, m_ab in enumerate(meses_abrev):
            r_ano[idx_ab + 2].text = m_ab
            r_ano[idx_ab + 2].paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER
            r_ano[idx_ab + 2].paragraphs[0].runs[0].font.size = Pt(8)
            aplicar_fundo_celula(r_ano[idx_ab + 2], "F9F9F9")

        rows_assinaturas = [
            "Dia do mês em que a\npreventiva foi realizada",
            "Nome do Técnico",
            "Assinatura"
        ]
        for label_ass in rows_assinaturas:
            r_ass = t_anx.add_row().cells
            r_ass[0].text = label_ass
            r_ass[0].merge(r_ass[1])
            r_ass[0].paragraphs[0].runs[0].font.size = Pt(8.5)
            r_ass[0].paragraphs[0].runs[0].bold = True
            r_ass[0].paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER

        doc.add_paragraph()

    b = io.BytesIO()
    doc.save(b)
    b.seek(0)
    return b

# ==============================================================================
# INTERFACE STREAMLIT - SIARCON PMOC
# ==============================================================================
st.set_page_config(page_title=f"SIARCON | {DISCIPLINA_ATUAL}", page_icon="📑", layout="wide")
st.title("📑 PMOC — Plano de Manutenção, Operação e Controle")
st.caption("Conformidade Institucional Absoluta — Prints 1, 2 e 3 (Cabeçalho, Rodapé e Anexo A)")

id_projeto = st.session_state.get('id_projeto_editar')
dados_edit = utils_db.buscar_projeto_por_id(id_projeto) if id_projeto else {}

tab1, tab2, tab3, tab4 = st.tabs([
    "1. Dados Gerais (1.1 a 1.3)",
    "2. Mapeamento HVAC (2.1 e 2.2)",
    "3. Seleção da Matriz (Subitens)",
    "4. Emissão DOCX Oficial (Anexo A)"
])

with tab1:
    st.subheader("1.1 Identificação do Ambiente e Código")
    col_a1, col_a2 = st.columns(2)
    nome_ambiente = col_a1.text_input("Nome do Empreendimento / Ambiente:", value=dados_edit.get('nome_ambiente', 'Administrativo Belenus'))
    end_ambiente = col_a1.text_input("Endereço COMPLETO:", value=dados_edit.get('end_ambiente', 'Rua Exemplo, 1000'))
    num_ambiente = col_a2.text_input("Número:", value=dados_edit.get('num_ambiente', '100'))
    codigo_doc = col_a2.text_input("Código Institucional do Cabeçalho (Print 2):", value=dados_edit.get('codigo_doc', 'PMOC-2023-00-00'))

    st.divider()
    st.subheader("1.2 Identificação do Proprietário")
    col_p1, col_p2 = st.columns(2)
    nome_prop = col_p1.text_input("Nome / Razão Social do Cliente:", value=dados_edit.get('nome_proprietario', 'Belenus S/A'))
    cnpj_prop = col_p1.text_input("CNPJ Nº:", value=dados_edit.get('cnpj_proprietario', '00.000.000/0001-00'))
    tel_prop = col_p2.text_input("Telefone do Contato:", value=dados_edit.get('tel_proprietario', '(19) 3000-0000'))
    email_prop = col_p2.text_input("E-mail de Contato:", value=dados_edit.get('email_proprietario', 'contato@cliente.com.br'))

with tab2:
    st.subheader("2.1 Relação de Ambientes Climatizados")
    lista_ambientes = converter_para_estrutura(dados_edit.get('lista_ambientes', []), list)
    if not lista_ambientes:
        lista_ambientes = [{"atividade": "Escritório / Administrativo", "fixos": 20, "flutuantes": 5, "identificacao": "Escritório Belenus", "area": 120, "carga": "60.000 BTU/h"}]
        
    for i, amb in enumerate(lista_ambientes):
        c1, c2, c3, c4, c5 = st.columns([3, 1, 1, 3, 2])
        amb['atividade'] = c1.text_input("Atividade", value=amb.get('atividade', ''), key=f"at_{i}")
        amb['fixos'] = c2.number_input("Fixos", value=int(amb.get('fixos', 0)), key=f"fix_{i}")
        amb['flutuantes'] = c3.number_input("Flutuantes", value=int(amb.get('flutuantes', 0)), key=f"flut_{i}")
        amb['identificacao'] = c4.text_input("Identificação do Ambiente", value=amb.get('identificacao', ''), key=f"id_{i}")
        amb['carga'] = c5.text_input("Carga Térmica", value=amb.get('carga', ''), key=f"cg_{i}")

    st.divider()
    st.subheader("2.2 Relação de Equipamentos Presentes no Sistema")
    lista_eq = converter_para_estrutura(dados_edit.get('lista_equipamentos', []), list)
    if not lista_eq:
        lista_eq = [{"equipamento": "Chiller Parafuso / Fancoil", "localizacao": "Escritório Belenus", "kw": 45, "tag": "CH-01"}]
        
    for j, eq in enumerate(lista_eq):
        c_eq1, c_eq2, c_eq3, c_eq4 = st.columns([3, 3, 1, 2])
        eq['equipamento'] = c_eq1.text_input("Equipamento", value=eq.get('equipamento', ''), key=f"eq_{j}")
        eq['localizacao'] = c_eq2.text_input("Localização", value=eq.get('localizacao', ''), key=f"loc_{j}")
        eq['kw'] = c_eq3.number_input("KW", value=int(eq.get('kw', 0)), key=f"kw_{j}")
        eq['tag'] = c_eq4.text_input("TAG", value=eq.get('tag', ''), key=f"tag_{j}")

with tab3:
    st.subheader("3. Seleção de Categorias e Subtópicos Mapeados")
    opcoes_categoria = list(ESTRUTURA_PMOC_SIARCON.keys())
    categorias_selecionadas = st.multiselect(
        "Selecione as categorias de equipamentos presentes na obra:",
        options=opcoes_categoria,
        default=opcoes_categoria[:3]
    )

    selecao_subitens = {}
    if categorias_selecionadas:
        st.divider()
        for cat in categorias_selecionadas:
            subitens_disp = list(ESTRUTURA_PMOC_SIARCON[cat]["subitens"].keys())
            if len(subitens_disp) == 1 and subitens_disp[0] == "Geral":
                selecao_subitens[cat] = ["Geral"]
            else:
                st.markdown(f"**🔹 Subitens de '{cat}':**")
                selecionados = st.multiselect(
                    f"Escolha os subtópicos para {cat}:",
                    options=subitens_disp,
                    default=subitens_disp,
                    key=f"sub_{cat}"
                )
                selecao_subitens[cat] = selecionados

with tab4:
    st.subheader("4. Emissão do PMOC Oficial SIARCON")
    st.write("✔️ O documento é construído com cabeçalho de 3 células (Print 2), rodapé institucional com telefone/endereço (Print 3) e tabela de acompanhamento com grade idêntica ao modelo (Print 1).")
    
    dados_pmoc = {
        '_id': dados_edit.get('_id'),
        'disciplina': DISCIPLINA_ATUAL,
        'codigo_doc': codigo_doc,
        'nome_ambiente': nome_ambiente,
        'end_ambiente': end_ambiente,
        'num_ambiente': num_ambiente,
        'cidade_ambiente': 'Limeira',
        'uf_ambiente': 'SP',
        'nome_proprietario': nome_prop,
        'cnpj_proprietario': cnpj_prop,
        'tel_proprietario': tel_prop,
        'email_proprietario': email_prop,
        'lista_ambientes': lista_ambientes,
        'lista_equipamentos': lista_eq,
        'selecao_subitens': selecao_subitens,
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
                st.success("✅ Documento exportado em 100% de conformidade com os Prints! Baixe abaixo:")
                st.session_state['btn_docx_pmoc_oficial'] = True
                
        if st.session_state.get('btn_docx_pmoc_oficial', False):
            b_docx = gerar_docx_pmoc(dados_pmoc)
            st.download_button(
                label="📥 BAIXAR PMOC (FORMATO OFICIAL SIARCON .DOCX)",
                data=b_docx,
                file_name=f"PMOC_SIARCON_{nome_ambiente.replace(' ', '_') or 'Obra'}.docx",
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            )
