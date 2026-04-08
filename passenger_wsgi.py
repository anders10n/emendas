import sys
import os

# Adiciona o diretório da aplicação ao path do Python
sys.path.insert(0, os.path.dirname(__file__))

# Importa o objeto 'app' do seu arquivo app.py e passa para o Passenger via variável 'application'
from app import app as application
