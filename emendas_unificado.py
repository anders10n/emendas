import requests
from bs4 import BeautifulSoup
import pandas as pd
from io import BytesIO
from PyPDF2 import PdfReader
import re


# Função para extrair texto de um PDF a partir de uma URL
def extract_text_from_pdf(url):
    try:
        print(f"Baixando e extraindo texto do PDF: {url}")
        response = requests.get(url)
        response.raise_for_status()
        pdf_file = BytesIO(response.content)
        pdf_reader = PdfReader(pdf_file)
        text = ""
        for page in pdf_reader.pages:
            text += page.extract_text() + "\n"
        print("Texto extraído com sucesso.")
        return text.strip()
    except Exception as e:
        print(f"Erro ao processar {url}: {e}")
        return ""

# Função para capturar emendas da Câmara dos Deputados
def captura_emendas_cd(url):
    print("Iniciando captura de emendas da Câmara dos Deputados...")
    
    emendas_url = url.replace('/fichadetramitacao', '/prop_emendas')
    response = requests.get(emendas_url)
    response.raise_for_status()

    soup = BeautifulSoup(response.content, 'html.parser')
    emendas_table = soup.find('table', summary="Emendas apresentadas")

    if emendas_table:
        emendas = emendas_table.find_all('tr')
        print(f"Encontradas {len(emendas) - 1} emendas na página.")
        
        emendas_data = []

        for emenda in emendas[1:]:
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
                
                texto_pdf = extract_text_from_pdf(url_emenda) if url_emenda else ''
                
                emendas_data.append({
                    "Emenda": emenda_num,
                    "Tipo de Emenda": tipo_emenda,
                    "Data de Apresentação": data_apresentacao,
                    "Autor": autor,
                    "Ementa": ementa,
                    "URL": url_emenda,
                    "Texto": texto_pdf
                })

        df = pd.DataFrame(emendas_data)
        planilha_nome = get_project_title_cd(url)
        save_excel(df, planilha_nome)
    else:
        print("A tabela de emendas não foi encontrada na página.")

# Função para capturar emendas do Senado Federal
def captura_emendas_sf(url):
    print("Iniciando captura de emendas do Senado Federal...")

    response = requests.get(url)
    response.raise_for_status()

    soup = BeautifulSoup(response.content, 'html.parser')
    emendas_div = soup.find('div', id='emendas')

    if emendas_div:
        emendas = emendas_div.find_all('tr')
        print(f"Encontradas {len(emendas) - 1} emendas na página.")
        
        emendas_data = []

        for emenda in emendas[1:]:
            cols = emenda.find_all('td')
            
            if len(cols) >= 5:
                identificacao = cols[0].get_text(strip=True)
                autor = cols[1].get_text(strip=True)
                data_apresentacao = cols[2].get_text(strip=True)
                turno = cols[3].get_text(strip=True)
                historico_deliberacao = cols[4].get_text(strip=True)
                
                url_emenda = cols[0].find('a', href=True)['href'] if cols[0].find('a', href=True) else ''
                texto_pdf = extract_text_from_pdf(url_emenda) if url_emenda else ''

                emendas_data.append({
                    "Identificação": identificacao,
                    "Autor": autor,
                    "Data de apresentação": data_apresentacao,
                    "Turno": turno,
                    "Histórico de deliberação": historico_deliberacao,
                    "URL": url_emenda,
                    "Texto": texto_pdf
                })

        df = pd.DataFrame(emendas_data)
        planilha_nome = get_project_title_sf(url)
        save_excel(df, planilha_nome)
    else:
        print("A div 'emendas' não foi encontrada na página.")

# Função para capturar emendas de Medida Provisória
def captura_emendas_mp(url):
    print("Iniciando captura de emendas da Medida Provisória...")

    response = requests.get(url)
    response.raise_for_status()

    soup = BeautifulSoup(response.content, 'html.parser')
    emendas_div = soup.find('div', id='emendas')

    if emendas_div:
        emendas = emendas_div.find_all('tr')
        print(f"Encontradas {len(emendas) - 1} emendas na página.")
        
        emendas_data = []

        for emenda in emendas[1:]:
            cols = emenda.find_all('td')

            if len(cols) >= 5:
                identificacao = cols[0].get_text(strip=True)
                autor = cols[1].get_text(strip=True)
                data_apresentacao = cols[2].get_text(strip=True)
                turno = cols[3].get_text(strip=True)
                historico_deliberacao = cols[4].get_text(strip=True)

                url_emenda = cols[0].find('a', href=True)['href'] if cols[0].find('a', href=True) else ''
                texto_pdf = extract_text_from_pdf(url_emenda) if url_emenda else ''

                emendas_data.append({
                    "Identificação": identificacao,
                    "Autor": autor,
                    "Data de apresentação": data_apresentacao,
                    "Turno": turno,
                    "Histórico de deliberação": historico_deliberacao,
                    "URL": url_emenda,
                    "Texto": texto_pdf
                })

        df = pd.DataFrame(emendas_data)
        planilha_nome = get_project_title_mp(url)
        save_excel(df, planilha_nome)
    else:
        print("A div 'emendas' não foi encontrada na página.")

# Função para salvar a planilha em Excel
def save_excel(df, planilha_nome):
    try:
        # Substitui espaços por sublinhados, "/" por "-", e remove outros caracteres inválidos
        planilha_nome = re.sub(r'\s+', '_', planilha_nome)
        planilha_nome = re.sub(r'[/]', '-', planilha_nome)
        planilha_nome = re.sub(r'[\\:*?"<>|]', '', planilha_nome)
        file_path = f"{planilha_nome}.xlsx"
        
        print(f"Salvando a planilha como {file_path}...")
        df.to_excel(file_path, index=False)
        print(f"Planilha {file_path} criada com sucesso.")
    except Exception as e:
        print(f"Erro ao salvar a planilha: {e}")

# Função para obter o título do projeto a partir da URL (Câmara dos Deputados)
def get_project_title_cd(url):
    print(f"Verificando o título do projeto na URL: {url}")
    response = requests.get(url)
    response.raise_for_status()

    soup = BeautifulSoup(response.content, 'html.parser')
    title_element = soup.find('span', class_='nomeProposicao')
    
    if title_element:
        title = title_element.get_text(strip=True)
        title = re.sub(r'[\/:*?"<>|]', '', title)
        return title
    else:
        raise ValueError("Não foi possível encontrar o título do projeto.")

# Função para obter o título do projeto a partir da URL (Senado Federal)
def get_project_title_sf(url):
    print(f"Verificando o título do projeto na URL: {url}")
    response = requests.get(url)
    response.raise_for_status()

    soup = BeautifulSoup(response.content, 'html.parser')
    title_element = soup.find('title')
    
    if title_element:
        title = title_element.get_text(strip=True)
        title = re.sub(r'[\/:*?"<>|]', '', title)
        return title
    else:
        raise ValueError("Não foi possível encontrar o título do projeto.")

# Função para obter o título do projeto a partir da URL (Medida Provisória)
def get_project_title_mp(url):
    print(f"Verificando o título do projeto na URL: {url}")
    response = requests.get(url)
    response.raise_for_status()

    soup = BeautifulSoup(response.content, 'html.parser')
    title_element = soup.find('title')
    
    if title_element:
        title = title_element.get_text(strip=True)
        title = re.sub(r'[\/:*?"<>|]', '', title)
        return title
    else:
        raise ValueError("Não foi possível encontrar o título do projeto.")

def main():
    try:
        print("Escolha uma das opções abaixo:")
        print("1 - Câmara dos Deputados")
        print("2 - Senado Federal")
        print("3 - Medida Provisória")
        
        choice = input("Digite o número correspondente à sua escolha: ").strip()

        if choice == '1':
            user_url = input("Por favor, insira o link da Câmara dos Deputados a ser pesquisado: ")
            project_title = get_project_title_cd(user_url)
            confirmation = input(f"O título do projeto é '{project_title}'. Você confirma? (S/N): ").strip().upper()
            if confirmation == 'S':
                captura_emendas_cd(user_url)
            else:
                print("Por favor, insira o link correto.")
        elif choice == '2':
            user_url = input("Por favor, insira o link do Senado Federal a ser pesquisado: ")
            project_title = get_project_title_sf(user_url)
            confirmation = input(f"O título do projeto é '{project_title}'. Você confirma? (S/N): ").strip().upper()
            if confirmation == 'S':
                captura_emendas_sf(user_url)
            else:
                print("Por favor, insira o link correto.")
        elif choice == '3':
            user_url = input("Por favor, insira o link da Medida Provisória ser pesquisada: ")
            project_title = get_project_title_sf(user_url)
            confirmation = input(f"O título da MPV é '{project_title}'. Você confirma? (S/N): ").strip().upper()
            if confirmation == 'S':
                captura_emendas_sf(user_url)
            else:
                print("Por favor, insira o link correto.")
        else:
            print("Opção inválida. Por favor, tente novamente.")
            main()
    except Exception as e:
        print(f"Ocorreu um erro: {e}")
    finally:
        input("Pressione Enter para sair...")

if __name__ == "__main__":
    main()
