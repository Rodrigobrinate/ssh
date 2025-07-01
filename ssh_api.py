#!/usr/bin/env python3
import paramiko
import logging
from flask import Flask, request, jsonify

# Configuração de logging mais verbosa para garantir que vejamos a saída.
logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s - %(levelname)s - P(%(process)d) - %(message)s'
)

def execute_huawei_command_debug(host, port, username, password, command):
    """
    Versão de diagnóstico da função SSH.
    - Adiciona logs e prints detalhados em cada etapa.
    - Trata qualquer saída em stderr como um erro fatal.
    - Simplifica a execução para isolar a causa do problema.
    """
    # Logs e prints para garantir que a função foi chamada.
    logging.info(f"--- INICIANDO EXECUÇÃO SSH PARA {host} ---")
    print(f"DEBUG: Função execute_huawei_command_debug foi chamada para {host}.")

    client = None
    try:
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        logging.info(f"Tentando conectar a {host}:{port}...")
        print(f"DEBUG: Conectando a {host}:{port} com o usuário {username}.")
        client.connect(
            hostname=host,
            port=port,
            username=username,
            password=password,
            look_for_keys=False,
            allow_agent=False,
            timeout=20
        )
        logging.info("Conexão SSH bem-sucedida.")
        print("DEBUG: Conexão SSH estabelecida com sucesso.")

        # --- EXECUÇÃO SIMPLIFICADA ---
        # Por enquanto, vamos remover o 'screen-length' para testar apenas o comando principal.
        # Isso nos ajuda a identificar se o problema está na execução de múltiplos comandos.
        logging.info(f"Executando comando simples: '{command}'")
        print(f"DEBUG: Executando comando: '{command}'")
        stdin, stdout, stderr = client.exec_command(command, timeout=30)

        # --- LEITURA DE SAÍDA E ERRO (ETAPA CRÍTICA) ---
        output = stdout.read().decode('utf-8', errors='ignore')
        error_output = stderr.read().decode('utf-8', errors='ignore').strip()

        # Logs detalhados do que foi recebido do dispositivo
        logging.info(f"Saída RAW (stdout) recebida:\n---\n{output}\n---")
        logging.info(f"Saída de Erro (stderr) recebida:\n---\n{error_output}\n---")
        print(f"DEBUG: Comprimento da saída stdout: {len(output)}")
        print(f"DEBUG: Comprimento da saída stderr: {len(error_output)}")

        # --- TRATAMENTO DE ERRO AGRESSIVO ---
        # Se QUALQUER coisa for recebida em stderr, vamos tratar como um erro e parar a execução.
        if error_output:
            error_message = f"Dispositivo retornou um erro em stderr: {error_output}"
            logging.error(error_message)
            print(f"DEBUG: ERRO DETECTADO: {error_message}")
            raise Exception(error_message)

        # Se não houve erro, mas a saída está vazia, registramos isso.
        if not output.strip():
            logging.warning(f"Comando '{command}' executou, mas não produziu nenhuma saída em stdout.")
            print("DEBUG: stdout estava vazio.")
        
        return output.strip()

    except Exception as e:
        # Se qualquer exceção ocorrer, vamos registrá-la e imprimi-la.
        logging.error(f"Uma exceção ocorreu durante a operação SSH: {e}", exc_info=True)
        print(f"DEBUG: Uma exceção foi capturada: {type(e).__name__} - {e}")
        # Re-lança a exceção para que a API Flask a capture e retorne um erro 500.
        raise
    finally:
        if client:
            client.close()
            logging.info("Conexão SSH fechada.")
            print("DEBUG: Conexão SSH fechada.")


# --- Configuração da API com Flask ---
app = Flask(__name__)

@app.route('/execute', methods=['POST'])
def handle_execute():
    # Adicionando um log para saber que a rota foi chamada.
    logging.info(f"Requisição recebida em /execute de {request.remote_addr}")
    print(f"DEBUG: Rota /execute foi chamada.")

    data = request.get_json()
    if not data:
        return jsonify({"status": "error", "message": "Payload da requisição deve ser em formato JSON."}), 400

    required_fields = ['host', 'username', 'password', 'command']
    missing_fields = [field for field in required_fields if field not in data]
    if missing_fields:
        return jsonify({"status": "error", "message": f"Campos obrigatórios ausentes: {', '.join(missing_fields)}"}), 400

    host = data['host']
    username = data['username']
    password = data['password']
    command = data['command']
    port = data.get('port', 22)

    try:
        # Chame a nova função de debug
        command_output = execute_huawei_command_debug(host, port, username, password, command)
        
        response_data = {
            "status": "success",
            "host": host,
            "command": command,
            "output": command_output
        }
        logging.info(f"Retornando sucesso para o cliente: {response_data}")
        return jsonify(response_data)
        
    except Exception as e:
        # A exceção lançada pela função de debug será capturada aqui.
        error_message = str(e)
        logging.error(f"Falha na API ao executar comando em {host}. Erro: {error_message}")
        return jsonify({
            "status": "error",
            "host": host,
            "command": command,
            "message": error_message
        }), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5500)
