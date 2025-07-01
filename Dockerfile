# --- Estágio 1: Definir a imagem base ---
# Usamos uma imagem oficial do Python. A versão "slim" é mais leve.
FROM python:3.9-slim

# --- Estágio 2: Configurar o ambiente ---
# Define o diretório de trabalho dentro do contêiner.
# Todos os comandos a seguir serão executados a partir deste diretório.
WORKDIR /app

# --- Estágio 3: Instalar as dependências ---
# Copia primeiro o arquivo de dependências.
# Isso aproveita o cache do Docker: se o requirements.txt não mudar,
# o Docker não reinstalará as dependências em builds futuros.
COPY requirements.txt .

# Instala as dependências listadas no requirements.txt
# --no-cache-dir: não armazena o cache do pip, mantendo a imagem menor.
# --trusted-host pypi.python.org: pode ajudar a evitar problemas de SSL em algumas redes.
RUN pip install --no-cache-dir --trusted-host pypi.python.org -r requirements.txt

# --- Estágio 4: Copiar o código da aplicação ---
# Copia o script da sua API para o diretório de trabalho no contêiner.
COPY ssh.py .

# --- Estágio 5: Definir o comando de execução ---
# Expõe a porta 5000, que é a porta que o Gunicorn usará.
EXPOSE 5500

# Define o comando que será executado quando o contêiner iniciar.
# Usamos o Gunicorn para servir a aplicação Flask.
# -w 4: Inicia 4 "workers" (processos) para lidar com as requisições.
# -b 0.0.0.0:5000: Faz o servidor escutar em todas as interfaces de rede na porta 5000.
# ssh_api:app: Diz ao Gunicorn para encontrar o objeto 'app' no arquivo 'ssh_api.py'.
CMD ["gunicorn", "-w", "4", "-b", "0.0.0.0:5500", "ssh_api:app"]
