#!/usr/bin/env python3
import paramiko
import logging
import time
import re
from flask import Flask, request, jsonify

# Configuração de logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def execute_huawei_interactive(host, port, username, password, command):
    """
    Conecta-se a um dispositivo Huawei usando um shell interativo (invoke_shell)
    de forma robusta para executar comandos que podem exigir privilégios elevados.
    """
    logging.info(f"Iniciando sessão interativa em {host}:{port}")
    client = None
    try:
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        client.connect(
            hostname=host, port=port, username=username, password=password,
            look_for_keys=False, allow_agent=False, timeout=20
        )

        # Abrir um canal de shell interativo
        channel = client.invoke_shell()
        logging.info("Canal de shell aberto com sucesso.")

        # Função auxiliar para ler a saída até encontrar um prompt
        def read_until_prompt(prompt_regex=r"[<\[][\w.-]+[>\]]"):
            output = ""
            start_time = time.time()
            while time.time() - start_time < 15: # Timeout de 15s para cada comando
                time.sleep(0.5)
                if channel.recv_ready():
                    chunk = channel.recv(65535).decode('utf-8', errors='ignore')
                    output += chunk
                    # O prompt geralmente é a última coisa na saída
                    if re.search(prompt_regex, output.strip().splitlines()[-1]):
                        logging.info(f"Prompt detectado. Saída recebida:\n---\n{output}\n---")
                        return output
                # Se não houver mais dados e o prompt não foi encontrado, esperamos um pouco mais
            raise Exception("Timeout esperando pelo prompt do dispositivo.")

        # 1. Esperar pelo prompt inicial após o login
        read_until_prompt()

        # 2. Desabilitar a paginação
        logging.info("Desabilitando paginação (screen-length 0 temporary)")
        channel.send("screen-length 0 temporary\n")
        read_until_prompt() # Esperar a confirmação (novo prompt)

        # 3. Enviar o comando principal do usuário
        logging.info(f"Enviando comando principal: '{command}'")
        channel.send(f"{command}\n")
        full_output = read_until_prompt()

        # 4. Limpar a saída
        # Remove a primeira linha (eco do comando) e a última linha (prompt)
        lines = full_output.strip().splitlines()
        if len(lines) > 2 and command in lines[0]:
            clean_output = "\n".join(lines[1:-1]).strip()
        else:
            # Fallback caso o formato não seja o esperado
            clean_output = full_output

        logging.info(f"Saída final limpa:\n---\n{clean_output}\n---")
        return clean_output

    except Exception as e:
        logging.error(f"Falha na operação SSH interativa em {host}: {e}", exc_info=True)
        raise # Re-lança a exceção para ser tratada pela API
    finally:
        if client:
            client.close()
            logging.info(f"Conexão com {host} fechada.")


# --- Configuração da API com Flask ---
app = Flask(__name__)

@app.route('/execute', methods=['POST'])
def handle_execute():
    logging.info(f"Requisição recebida em /execute de {request.remote_addr}")
    data = request.get_json()
    if not data:
        return jsonify({"status": "error", "message": "Payload JSON ausente."}), 400

    required_fields = ['host', 'username', 'password', 'command']
    if not all(field in data for field in required_fields):
        return jsonify({"status": "error", "message": f"Campos obrigatórios ausentes: {required_fields}"}), 400

    host = data['host']
    username = data['username']
    password = data['password']
    command = data['command'].strip() # Remove espaços extras no início/fim
    port = data.get('port', 22)

    try:
        command_output = execute_huawei_interactive(host, port, username, password, command)
        return jsonify({
            "status": "success",
            "host": host,
            "command": command,
            "output": command_output
        })
    except Exception as e:
        return jsonify({
            "status": "error",
            "host": host,
            "command": command,
            "message": str(e)
        }), 500

# Para ser usado com Gunicorn/WSGI
# Se for executar diretamente com "python ssh_api.py", descomente as linhas abaixo
# if __name__ == '__main__':
#     app.run(host='0.0.0.0', port=5500)
