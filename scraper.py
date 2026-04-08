import os
import re
import requests
from bs4 import BeautifulSoup
import pandas as pd
from io import BytesIO
from PyPDF2 import PdfReader
import uuid
import threading

# Dicionário global para armazenar o estado das tarefas
# jobs = { 'job_id': {'status': 'processing', 'progress_percent': 0, 'info': '...', 'result_bytes': None, 'filename': '...'} }
jobs = {}

def get_job(job_id):
    return jobs.get(job_id, None)

def update_job(job_id, status=None, progress_percent=None, info=None, result_bytes=None, filename=None):
    if job_id not in jobs:
        jobs[job_id] = {'status': 'starting', 'progress_percent': 0, 'info': '', 'result_bytes': None, 'filename': 'emendas.xlsx'}
    
    if status is not None:
        jobs[job_id]['status'] = status
    if progress_percent is not None:
        jobs[job_id]['progress_percent'] = progress_percent
    if info is not None:
        jobs[job_id]['info'] = info
    if result_bytes is not None:
        jobs[job_id]['result_bytes'] = result_bytes
    if filename is not None:
        jobs[job_id]['filename'] = filename

# =======================================================
# LÓGICAS DE FORMATAÇÃO E ENGENHARIA DE DADOS
# =======================================================
def format_project_title(raw_title):
    match = re.search(r'([A-Za-z]+)\s*(\d+)[\/\-](\d{4})', raw_title)
    if match:
        sigla = match.group(1).upper()
        numero = match.group(2)
        ano = match.group(3)
        return f"{sigla} {numero}/{ano}", f"Emendas_{sigla}_{numero}_{ano}"
    
    clean_title = re.sub(r'[\/:*?"<>|]', '', raw_title)
    return clean_title, f"Emendas_{clean_title}".replace(" ", "_")

def extract_text_from_pdf(url):
    try:
        if not url: return ""
        response = requests.get(url, timeout=10) # Timeout para evitar travamento
        response.raise_for_status()
        pdf_file = BytesIO(response.content)
        pdf_reader = PdfReader(pdf_file)
        text = "".join([page.extract_text() + "\n" for page in pdf_reader.pages])
        return text.strip()
    except Exception as e:
        print(f"Erro ao extrair PDF {url}: {e}")
        return "Erro ao extrair texto do PDF."

def get_project_title_cd(url):
    response = requests.get(url)
    response.raise_for_status()
    soup = BeautifulSoup(response.content, 'html.parser')
    title_element = soup.find('span', class_='nomeProposicao')
    if title_element:
        title = title_element.get_text(strip=True)
        return format_project_title(title)
    raise ValueError("Não foi possível encontrar o título do projeto da Câmara.")

def get_project_title_sf_mp(url):
    response = requests.get(url)
    response.raise_for_status()
    soup = BeautifulSoup(response.content, 'html.parser')
    title_element = soup.find('title')
    if title_element:
        title = title_element.get_text(strip=True)
        return format_project_title(title)
    raise ValueError("Não foi possível encontrar o título do projeto.")

def recursiva_encontra_codigo(d):
    if isinstance(d, dict):
        for k, v in d.items():
            if str(k).lower() == 'codigomateria':
                return v
        for v in d.values():
            res = recursiva_encontra_codigo(v)
            if res: return res
    elif isinstance(d, list):
        for i in d:
            res = recursiva_encontra_codigo(i)
            if res: return res
    return None

def find_url_by_api(modo, user_input):
    match = re.search(r'([A-Za-z]+)\s*(\d+)[\/\-](\d{4})', user_input)
    if not match:
        raise ValueError("Formato inválido. Por favor certifique-se de digitar Ex: PL 1234/2026.")

    sigla = match.group(1).upper()
    numero = match.group(2)
    ano = match.group(3)
    url_gerada = None

    if modo == "CD":
        call_url = f"https://dadosabertos.camara.leg.br/api/v2/proposicoes?siglaTipo={sigla}&numero={numero}&ano={ano}&ordem=ASC&ordenarPor=id"
        resp = requests.get(call_url)
        resp.raise_for_status()
        itens = resp.json().get('dados', [])
        if itens:
            id_prop = itens[0]['id']
            url_gerada = f"https://www.camara.leg.br/proposicoesWeb/fichadetramitacao?idProposicao={id_prop}"
        
    elif modo in ("SF", "MP"):
        call_url = f"https://legis.senado.leg.br/dadosabertos/processo?sigla={sigla}&numero={numero}&ano={ano}&v=1"
        resp = requests.get(call_url, headers={'Accept': 'application/json'})
        resp.raise_for_status()
        try: j = resp.json() 
        except: j = {}
            
        codigo_materia = recursiva_encontra_codigo(j)
        if codigo_materia:
            if modo == "SF":
                url_gerada = f"https://www25.senado.leg.br/web/atividade/materias/-/materia/{codigo_materia}"
            else:
                url_gerada = f"https://www.congressonacional.leg.br/materias/medidas-provisorias/-/mpv/{codigo_materia}"

    if not url_gerada:
        raise ValueError("A API não retornou resultados para a matéria pesquisada. Verifique se o órgão é o correto.")
    return url_gerada


def preview_project(modo, user_input):
    match = re.search(r'([A-Za-z]+)\s*(\d+)[\/\-](\d{4})', user_input)
    if not match:
        raise ValueError("Formato inválido. Exemplo correto: PL 123/2024")

    sigla = match.group(1).upper()
    numero = match.group(2)
    ano = match.group(3)
    
    preview_data = {
        'identificacao': f"{sigla} {numero}/{ano}",
        'ementa': 'Ementa não encontrada',
        'autor': 'Desconhecido'
    }

    if modo == "CD":
        call_url = f"https://dadosabertos.camara.leg.br/api/v2/proposicoes?siglaTipo={sigla}&numero={numero}&ano={ano}&ordem=ASC&ordenarPor=id"
        resp = requests.get(call_url)
        resp.raise_for_status()
        itens = resp.json().get('dados', [])
        if itens:
            prop = itens[0]
            preview_data['ementa'] = prop.get('ementa', 'Ementa não encontrada')
            try:
                autor_url = f"https://dadosabertos.camara.leg.br/api/v2/proposicoes/{prop['id']}/autores"
                autores_resp = requests.get(autor_url).json().get('dados', [])
                if autores_resp:
                    if len(autores_resp) > 1:
                        preview_data['autor'] = f"{autores_resp[0].get('nome')} (e outros)"
                    else:
                        preview_data['autor'] = autores_resp[0].get('nome')
            except:
                pass
        else:
            raise ValueError("Matéria não encontrada na base da Câmara.")
            
    elif modo in ("SF", "MP"):
        call_url = f"https://legis.senado.leg.br/dadosabertos/processo?sigla={sigla}&numero={numero}&ano={ano}&v=1"
        resp = requests.get(call_url, headers={'Accept': 'application/json'})
        resp.raise_for_status()
        try:
            dados = resp.json()
            if isinstance(dados, list) and len(dados) > 0:
                prop = dados[0]
                preview_data['ementa'] = prop.get('ementa', 'Ementa não encontrada')
                preview_data['autor'] = prop.get('autoria', 'Desconhecido')
        except:
            pass

    if preview_data['autor'] and ',' in preview_data['autor']:
        primeiro_autor = preview_data['autor'].split(',')[0].strip()
        preview_data['autor'] = f"{primeiro_autor} (e outros)"

    if preview_data['ementa'] and len(preview_data['ementa']) > 1000:
        preview_data['ementa'] = preview_data['ementa'][:1000] + "..."

    return preview_data


# =======================================================
# WORKERS DE EXTRAÇÃO
# =======================================================

def run_extraction_cd(job_id, url):
    try:
        update_job(job_id, info="Identificando título do projeto...")
        display_title, file_name = get_project_title_cd(url)
        
        update_job(job_id, info=f"Iniciando coleta para: {display_title}")
        emendas_url = url.replace('/fichadetramitacao', '/prop_emendas')
        response = requests.get(emendas_url)
        response.raise_for_status()

        soup = BeautifulSoup(response.content, 'html.parser')
        emendas_table = soup.find('table', summary="Emendas apresentadas")

        if not emendas_table:
            raise Exception("Tabela de emendas não encontrada.")

        emendas = emendas_table.find_all('tr')[1:]
        total_emendas = len(emendas)
        
        if total_emendas == 0:
            update_job(job_id, status='no_emendas', progress_percent=100, info="Proposição sem emendas apresentadas")
            return
            
        update_job(job_id, info=f"Encontradas {total_emendas} emendas. Extraindo dados e PDFs...")

        emendas_data = []

        for i, emenda in enumerate(emendas):
            cols = emenda.find_all('td')
            if len(cols) >= 5:
                emenda_num = cols[0].get_text(strip=True)
                tipo_emenda = cols[1].get_text(strip=True)
                data_apresentacao = cols[2].get_text(strip=True)
                autor = cols[3].get_text(strip=True)
                ementa = cols[4].get_text(strip=True)
                
                texto_justificado_td = emenda.find('td', class_='textoJustificado')
                url_emenda = ''
                if texto_justificado_td:
                    link = texto_justificado_td.find('a', href=True)
                    if link:
                        url_emenda = "https://www.camara.leg.br/proposicoesWeb/" + link['href']
                
                # BUG CORRIGIDO: Agora a coleta do texto do PDF está ativada.
                update_job(job_id, info=f"Baixando PDF e processando emenda {emenda_num}")
                texto_pdf = extract_text_from_pdf(url_emenda) if url_emenda else ''
                
                emendas_data.append({
                    "Emenda": emenda_num,
                    "Tipo de Emenda": tipo_emenda,
                    "Data de Apresentação": data_apresentacao,
                    "Autor": autor,
                    "Ementa": ementa,
                    "URL": url_emenda,
                    "Texto PDF": texto_pdf
                })
                
            percent = int(((i + 1) / total_emendas) * 100)
            update_job(job_id, progress_percent=percent)

        df = pd.DataFrame(emendas_data)
        finish_job(job_id, df, file_name)

    except Exception as e:
        update_job(job_id, status='error', info=str(e), progress_percent=100)

def run_extraction_sf_mp(job_id, url):
    try:
        update_job(job_id, info="Identificando título do projeto...")
        display_title, file_name = get_project_title_sf_mp(url)
        
        update_job(job_id, info=f"Iniciando coleta para: {display_title}")

        response = requests.get(url)
        response.raise_for_status()

        soup = BeautifulSoup(response.content, 'html.parser')
        emendas_div = soup.find('div', id='emendas')

        if not emendas_div:
            raise Exception("Divisão 'emendas' não foi encontrada na página.")

        emendas = emendas_div.find_all('tr')[1:]
        total_emendas = len(emendas)

        if total_emendas == 0:
            update_job(job_id, status='no_emendas', progress_percent=100, info="Proposição sem emendas apresentadas")
            return

        update_job(job_id, info=f"Encontradas {total_emendas} emendas. Extraindo dados e PDFs...")

        emendas_data = []

        for i, emenda in enumerate(emendas):
            cols = emenda.find_all('td')
            if len(cols) >= 5:
                identificacao = cols[0].get_text(strip=True)
                autor = cols[1].get_text(strip=True)
                data_apresentacao = cols[2].get_text(strip=True)
                turno = cols[3].get_text(strip=True)
                historico_deliberacao = cols[4].get_text(strip=True)

                url_emenda = cols[0].find('a', href=True)['href'] if cols[0].find('a', href=True) else ''
                
                # BUG CORRIGIDO
                update_job(job_id, info=f"Baixando PDF e processando emenda {identificacao}")
                texto_pdf = extract_text_from_pdf(url_emenda) if url_emenda else ''
                
                emendas_data.append({
                    "Identificação": identificacao,
                    "Autor": autor,
                    "Data de apresentação": data_apresentacao,
                    "Turno": turno,
                    "Histórico de deliberação": historico_deliberacao,
                    "URL": url_emenda,
                    "Texto PDF": texto_pdf
                })

            percent = int(((i + 1) / total_emendas) * 100)
            update_job(job_id, progress_percent=percent)

        df = pd.DataFrame(emendas_data)
        finish_job(job_id, df, file_name)

    except Exception as e:
        update_job(job_id, status='error', info=str(e), progress_percent=100)

def finish_job(job_id, df, file_name):
    # Transforma o dataframe de forma alocada em memoria com BytesIO para poder baixar via web
    excel_buffer = BytesIO()
    with pd.ExcelWriter(excel_buffer, engine='openpyxl') as writer:
        df.to_excel(writer, index=False)
    
    excel_data = excel_buffer.getvalue()
    
    update_job(job_id, status='completed', progress_percent=100, info="Extração finalizada com sucesso!", result_bytes=excel_data, filename=f"{file_name}.xlsx")

def start_extraction(modo, user_input, is_link):
    job_id = str(uuid.uuid4())
    update_job(job_id, status='processing', info='Iniciando processamento...')
    
    def background_task():
        try:
            url = user_input
            if not is_link:
                update_job(job_id, info='Buscando matéria na API governamental...')
                url = find_url_by_api(modo, user_input)
            
            if modo == "CD":
                run_extraction_cd(job_id, url)
            elif modo in ("SF", "MP"):
                run_extraction_sf_mp(job_id, url)
            else:
                update_job(job_id, status='error', info="Modo inválido selecionado.")
        except Exception as e:
            update_job(job_id, status='error', info=str(e), progress_percent=100)

    threading.Thread(target=background_task, daemon=True).start()
    return job_id
