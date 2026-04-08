import os
import sys
import threading
import tkinter as tk
from tkinter import messagebox, ttk
from PIL import Image, ImageTk
import requests
from bs4 import BeautifulSoup
import pandas as pd
from io import BytesIO
from PyPDF2 import PdfReader
import re

# =======================================================
# LÓGICA DE DIRETÓRIOS E COMPATIBILIDADE PYINSTALLER
# =======================================================
def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

def get_desktop_path():
    return os.path.join(os.path.join(os.environ['USERPROFILE']), 'Desktop')

# =======================================================
# LÓGICAS DE FORMATAÇÃO E ENGENHARIA DE DADOS
# =======================================================
def format_project_title(raw_title):
    match = re.search(r'([A-Za-z]+)\s*(\d+)[\/\-](\d{4})', raw_title)
    if match:
        sigla = match.group(1).upper()
        numero = match.group(2)
        ano = match.group(3)
        return f"{sigla} {numero}/{ano}", f"Emendas ao {sigla}_{numero}-{ano}"
    
    clean_title = re.sub(r'[\/:*?"<>|]', '', raw_title)
    return clean_title, f"Emendas ao {clean_title}"

def extract_text_from_pdf(url):
    try:
        response = requests.get(url)
        response.raise_for_status()
        pdf_file = BytesIO(response.content)
        pdf_reader = PdfReader(pdf_file)
        text = "".join([page.extract_text() + "\n" for page in pdf_reader.pages])
        return text.strip()
    except Exception:
        return ""

def save_excel(df, file_base_name):
    try:
        file_base_name = re.sub(r'[/\\:*?"<>|]', '-', file_base_name)
        desktop = get_desktop_path()
        file_path = os.path.join(desktop, f"{file_base_name}.xlsx")
        
        df.to_excel(file_path, index=False)
        return file_path, True
    except Exception as e:
        return str(e), False

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

def captura_emendas_cd(url, title_data, interface_funcs):
    display_title, file_name = title_data
    update_progress = interface_funcs.get('progress')
    update_info = interface_funcs.get('info')

    emendas_url = url.replace('/fichadetramitacao', '/prop_emendas')
    response = requests.get(emendas_url)
    response.raise_for_status()

    soup = BeautifulSoup(response.content, 'html.parser')
    emendas_table = soup.find('table', summary="Emendas apresentadas")

    if not emendas_table:
        return "Tabela de emendas não encontrada.", False

    emendas = emendas_table.find_all('tr')[1:]
    total_emendas = len(emendas)
    
    if update_info:
        update_info(f"Foram encontradas {total_emendas} emendas. Verificando resumos e gerando tabela...")

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
            
            # texto_pdf = extract_text_from_pdf(url_emenda) if url_emenda else ''
            # Vamos evitar baixar dezenas de PDFs pra não travar no Senado por enquanto.
            
            emendas_data.append({
                "Emenda": emenda_num,
                "Tipo de Emenda": tipo_emenda,
                "Data de Apresentação": data_apresentacao,
                "Autor": autor,
                "Ementa": ementa,
                "URL": url_emenda,
                #"Texto": texto_pdf
            })
            
        if update_progress:
            update_progress(i + 1, total_emendas)

    df = pd.DataFrame(emendas_data)
    return save_excel(df, file_name)

def captura_emendas_sf_mp(url, title_data, interface_funcs):
    display_title, file_name = title_data
    update_progress = interface_funcs.get('progress')
    update_info = interface_funcs.get('info')

    response = requests.get(url)
    response.raise_for_status()

    soup = BeautifulSoup(response.content, 'html.parser')
    emendas_div = soup.find('div', id='emendas')

    if not emendas_div:
        return "Divisão 'emendas' não foi encontrada na página.", False

    emendas = emendas_div.find_all('tr')[1:]
    total_emendas = len(emendas)

    if update_info:
        update_info(f"Foram encontradas {total_emendas} emendas. Gerando tabela...")

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
            
            emendas_data.append({
                "Identificação": identificacao,
                "Autor": autor,
                "Data de apresentação": data_apresentacao,
                "Turno": turno,
                "Histórico de deliberação": historico_deliberacao,
                "URL": url_emenda,
            })

        if update_progress:
            update_progress(i + 1, total_emendas)

    df = pd.DataFrame(emendas_data)
    return save_excel(df, file_name)

# =======================================================
# INTERFACE GRÁFICA (GUI)
# =======================================================
class EmendasApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Extrator de Emendas - Unificado")
        self.root.geometry("650x550")
        self.root.resizable(False, False)
        
        self.colors = {
            "main_bg": "#f5f5f5",
            "cd_bg": "#dff2e1",
            "sf_bg": "#e4edf5",
            "mp_bg": "#fffde7"
        }
        
        self.input_mode = tk.StringVar(value="LINK")
        self.current_modo = None
        
        self.root.configure(bg=self.colors["main_bg"])
        self.main_container = tk.Frame(self.root, bg=self.colors["main_bg"])
        self.main_container.pack(fill=tk.BOTH, expand=True)
        
        self.modos = {
            "CD": ("Câmara dos Deputados", self.colors["cd_bg"], "assets/cd_logo.png", get_project_title_cd, captura_emendas_cd),
            "SF": ("Senado Federal", self.colors["sf_bg"], "assets/sf_logo.png", get_project_title_sf_mp, captura_emendas_sf_mp),
            "MP": ("Medida Provisória", self.colors["mp_bg"], "assets/brasao.png", get_project_title_sf_mp, captura_emendas_sf_mp)
        }
        
        self.show_home()

    def show_home(self):
        for widget in self.main_container.winfo_children():
            widget.destroy()
            
        self.root.configure(bg=self.colors["main_bg"])
        self.main_container.configure(bg=self.colors["main_bg"])
        
        lbl_title = tk.Label(self.main_container, text="Selecione a Casa Legislativa da Matéria", 
                             font=("Segoe UI", 16, "bold"), bg=self.colors["main_bg"], fg="#333")
        lbl_title.pack(pady=40)

        buttons_frame = tk.Frame(self.main_container, bg=self.colors["main_bg"])
        buttons_frame.pack(pady=10)

        style = ttk.Style()
        style.configure("TButton", font=("Segoe UI", 11), padding=10)

        btn_cd = ttk.Button(buttons_frame, text="Câmara dos Deputados", width=30,
                            command=lambda: self.show_extract_view("CD"))
        btn_cd.pack(pady=10)

        btn_sf = ttk.Button(buttons_frame, text="Senado Federal", width=30,
                            command=lambda: self.show_extract_view("SF"))
        btn_sf.pack(pady=10)

        btn_mp = ttk.Button(buttons_frame, text="Medida Provisória", width=30,
                            command=lambda: self.show_extract_view("MP"))
        btn_mp.pack(pady=10)

    def show_extract_view(self, modo):
        self.current_modo = modo
        title, bg_color, logo_path, _, _ = self.modos[modo]
        
        self.root.configure(bg=bg_color)
        for widget in self.main_container.winfo_children():
            widget.destroy()
            
        self.main_container.configure(bg=bg_color)
        
        top_frame = tk.Frame(self.main_container, bg=bg_color)
        top_frame.pack(fill=tk.X, padx=10, pady=10)
        
        btn_back = ttk.Button(top_frame, text="← Voltar", command=self.show_home)
        btn_back.pack(side=tk.LEFT)
        
        center_frame = tk.Frame(self.main_container, bg=bg_color)
        center_frame.pack(expand=True, fill=tk.BOTH, pady=10)
        
        img_path = resource_path(logo_path)
        try:
            pil_image = Image.open(img_path)
            pil_image.thumbnail((150, 150), Image.Resampling.LANCZOS)
            logo_img = ImageTk.PhotoImage(pil_image)
            lbl_logo = tk.Label(center_frame, image=logo_img, bg=bg_color)
            lbl_logo.image = logo_img
            lbl_logo.pack(pady=5)
        except Exception:
            pass
        
        lbl_heading = tk.Label(center_frame, text=title, font=("Segoe UI", 16, "bold"), bg=bg_color)
        lbl_heading.pack(pady=10)
        
        self.lbl_instr = tk.Label(center_frame, text="Insira o link da matéria desejada:", font=("Segoe UI", 10), bg=bg_color)
        self.lbl_instr.pack(pady=5)
        
        self.url_entry = tk.Entry(center_frame, width=65, font=("Segoe UI", 11))
        self.url_entry.pack(pady=5)
        
        self.btn_toggle = tk.Button(center_frame, text="[ Não tenho o link ]", font=("Segoe UI", 9, "underline"), 
                              fg="#005599", bg=bg_color, bd=0, activebackground=bg_color, cursor="hand2",
                              command=self.toggle_input_mode)
        self.btn_toggle.pack(pady=2)
        
        self.btn_buscar = ttk.Button(center_frame, text="Buscar e Extrair Excel", command=self.iniciar_busca)
        self.btn_buscar.pack(pady=15)
        
        self.lbl_info = tk.Label(center_frame, text="", bg=bg_color, font=("Segoe UI", 10, "bold"), fg="#1c3b61")
        self.lbl_info.pack()

        # Input Inicial (Reseta State)
        self.input_mode.set("LINK")

        self.progress_frame = tk.Frame(center_frame, bg=bg_color)
        self.lbl_progresso_percent = tk.Label(self.progress_frame, text="0%", font=("Segoe UI", 10, "bold"), bg=bg_color)
        self.lbl_progresso_percent.pack(side=tk.RIGHT, padx=5)
        
        self.progress_bar = ttk.Progressbar(self.progress_frame, orient="horizontal", length=400, mode="determinate")
        self.progress_bar.pack(side=tk.LEFT, pady=10)
        self.progress_frame.pack_forget()

    # --- Funções do Placeholder e Toggle ---
    def toggle_input_mode(self):
        if self.input_mode.get() == "LINK":
            self.input_mode.set("SEARCH")
            self.lbl_instr.config(text="Digite a matéria:")
            self.btn_toggle.config(text="[ Inserir Link ]")
            self.url_entry.delete(0, tk.END)
            self.url_entry.insert(0, "Exemplo: PL 1234/2026")
            self.url_entry.config(fg="gray")
            
            self.url_entry.bind("<FocusIn>", self.clear_placeholder)
            self.url_entry.bind("<FocusOut>", self.add_placeholder)
            self.url_entry.bind("<Return>", lambda event: self.iniciar_busca())
            
            self.btn_buscar.config(text="Pesquisar e Extrair Excel")
        else:
            self.input_mode.set("LINK")
            self.lbl_instr.config(text="Insira o link da matéria desejada:")
            self.btn_toggle.config(text="[ Não tenho o link ]")
            self.url_entry.unbind("<FocusIn>")
            self.url_entry.unbind("<FocusOut>")
            self.url_entry.unbind("<Return>")
            self.url_entry.config(fg="black")
            
            if self.url_entry.get() == "Exemplo: PL 1234/2026":
                self.url_entry.delete(0, tk.END)
            self.btn_buscar.config(text="Buscar e Extrair Excel")

    def clear_placeholder(self, event):
        if self.url_entry.get() == "Exemplo: PL 1234/2026":
            self.url_entry.delete(0, tk.END)
            self.url_entry.config(fg="black")

    def add_placeholder(self, event):
        if not self.url_entry.get():
            self.url_entry.insert(0, "Exemplo: PL 1234/2026")
            self.url_entry.config(fg="gray")

    def recursiva_encontra_codigo(self, d):
        if isinstance(d, dict):
            # Procura chave com codigomateria (case insensitive)
            for k, v in d.items():
                if str(k).lower() == 'codigomateria':
                    return v
            for v in d.values():
                res = self.recursiva_encontra_codigo(v)
                if res: return res
        elif isinstance(d, list):
            for i in d:
                res = self.recursiva_encontra_codigo(i)
                if res: return res
        return None

    # --- API de Pesquisa de URL ---
    def pesquisar_id_api(self, modo, user_input):
        match = re.search(r'([A-Za-z]+)\s*(\d+)[\/\-](\d{4})', user_input)
        if not match:
            self.root.after(0, self.mostrar_erro, "Formato inválido. Por favor certifique-se de digitar Ex: PL 1234/2026.")
            return

        sigla = match.group(1).upper()
        numero = match.group(2)
        ano = match.group(3)

        try:
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
                
                try: 
                    j = resp.json() 
                except: 
                    j = {}
                    
                codigo_materia = self.recursiva_encontra_codigo(j)

                if codigo_materia:
                    if modo == "SF":
                        url_gerada = f"https://www25.senado.leg.br/web/atividade/materias/-/materia/{codigo_materia}"
                    else:
                        url_gerada = f"https://www.congressonacional.leg.br/materias/medidas-provisorias/-/mpv/{codigo_materia}"

            if not url_gerada:
                self.root.after(0, self.mostrar_erro, "A API não retornou resultados para a matéria pesquisada. Verifique se o órgão é o correto.")
                return

            self.root.after(0, self.lbl_info.config, {"text": "Matéria encontrada! Carregando dados do escopo..."})
            self.root.after(0, self.processar_extracao, modo, url_gerada)

        except Exception as e:
            self.root.after(0, self.mostrar_erro, f"Problemas ao comunicar-se com os Dados Abertos:\n{str(e)}")

    # --- Lógica de Extracao ---
    def iniciar_busca(self):
        user_input = self.url_entry.get().strip()
        
        if not user_input or user_input == "Exemplo: PL 1234/2026":
            messagebox.showwarning("Aviso", "Por favor, preencha o campo antes de continuar.")
            return
            
        self.btn_buscar.config(state=tk.DISABLED)
        self.progress_frame.pack_forget()
        
        if self.input_mode.get() == "SEARCH":
            self.lbl_info.config(text="Buscando código na base do órgão Governamental. Aguarde...", fg="#333")
            threading.Thread(target=self.pesquisar_id_api, args=(self.current_modo, user_input), daemon=True).start()
        else:
            self.lbl_info.config(text="Procurando Título da Matéria através do Link...", fg="#333")
            threading.Thread(target=self.processar_extracao, args=(self.current_modo, user_input), daemon=True).start()

    def processar_extracao(self, modo, url):
        fn_get_title = self.modos[modo][3]
        fn_extract = self.modos[modo][4]
        
        try:
            title_data = fn_get_title(url)
            self.root.after(0, self.pedir_confirmacao, modo, url, title_data, fn_extract)
        except Exception as e:
            self.root.after(0, self.mostrar_erro, f"Erro ao acessar URL gerada ou capturar título:\n{str(e)}")

    def pedir_confirmacao(self, modo, url, title_data, fn_extract):
        display_title = title_data[0]
        msg = f"A identificação da matéria é:\n\n'{display_title}'\n\nVocê confirma esta matéria e deseja buscar os dados agora?"
        resposta = messagebox.askyesno("Confirmar Matéria", msg)
        
        if resposta:
            self.lbl_info.config(text="Conectando. Aguarde a coleta inicial de emendas...")
            interface_callbacks = {
                'progress': lambda current, mmax: self.root.after(0, self.atualizar_barra, current, mmax),
                'info': lambda status_text: self.root.after(0, self.lbl_info.config, {"text": status_text})
            }
            threading.Thread(target=self.finalizar_extracao, args=(fn_extract, url, title_data, interface_callbacks), daemon=True).start()
        else:
            self.btn_buscar.config(state=tk.NORMAL)
            self.lbl_info.config(text="", fg="#333")

    def atualizar_barra(self, current, mmax):
        if not self.progress_frame.winfo_ismapped() and mmax > 0:
            self.progress_frame.pack(pady=10)
            self.progress_bar["maximum"] = mmax
            
        self.progress_bar["value"] = current
        percent = int((current / float(mmax)) * 100) if mmax > 0 else 0
        
        if percent >= 100:
            self.lbl_progresso_percent.config(text="100% Salvo", fg="green")
            self.lbl_info.config(text="Finalizado e Salvo na Área de Trabalho com sucesso!", fg="green")
        else:
            self.lbl_progresso_percent.config(text=f"{percent}%", fg="black")

    def finalizar_extracao(self, fn_extract, url, title_data, interface_callbacks):
        retorno, success = fn_extract(url, title_data, interface_callbacks)
        if success:
            self.root.after(0, self.mostrar_sucesso, retorno)
        else:
            self.root.after(0, self.mostrar_erro, f"Ocorreu um erro ou nenhuma tabela de emenda encontrada:\n{retorno}")

    def mostrar_sucesso(self, file_path):
        messagebox.showinfo("Sucesso!", f"Dados extraídos com eficácia.\nPlanilha Salva em:\n{file_path}")
        self.btn_buscar.config(state=tk.NORMAL)
        # Reseta se estiver em mode Search para o texto vazio normal.
        if self.input_mode.get() == "SEARCH":
            self.btn_toggle.invoke()
        else:
            self.url_entry.delete(0, tk.END)

    def mostrar_erro(self, msg):
        messagebox.showerror("Erro", msg)
        self.btn_buscar.config(state=tk.NORMAL)
        self.lbl_info.config(text="", fg="red")
        self.progress_frame.pack_forget()


if __name__ == "__main__":
    root = tk.Tk()
    try:
        root.iconbitmap(resource_path('assets/brasao.ico'))
    except Exception:
        pass
    app = EmendasApp(root)
    root.mainloop()
