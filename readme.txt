PS C:\Users\lucia\Desktop\GeoRiskXAI> python --version
Python 3.12.0

Instalação 
Crie um ambiente virtual
PS C:\Users\lucia\Desktop\GeoRiskXAI> python -m venv venv

Ative o ambiente virtual
PS C:\Users\lucia\Desktop\GeoRiskXAI> cd venv
PS C:\Users\lucia\Desktop\GeoRiskXAI\venv> .\Scripts\activate
(venv) PS C:\Users\lucia\Desktop\GeoRiskXAI\venv> cd ..

Instale as dependências
(venv) PS C:\Users\lucia\Desktop\GeoRiskXAI> pip install -r requirements.txt

Executar robô extração dataset

(venv) PS C:\Users\lucia\Desktop\GeoRiskXAI> python .\robo_diario_dataset.py