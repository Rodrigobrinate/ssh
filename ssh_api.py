#!/usr/bin/env python3
import paramiko
import logging
from flask import Flask, request, jsonify

# Configuração básica de logging para ver a saída no Docker
# O logging ajuda a depurar problemas de conexão e execução.
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def execute_huawei_command(host, port, username, password, command):
    """
    Conecta-se a um dispositivo Huawei via SSH usando exec_command, executa um comando
    e retorna o resultado de forma limpa e robusta.

    Este método é preferível ao invoke_shell para a execução de comandos únicos,
    pois é menos propenso a erros de timing e parsing de prompt.
    """
    client = None
    try:
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        logging.info(f"Conectando a {host}:{port}...")
        client.connect(
            hostname=host,
            port=port,
            username=username,
            password=password,
            look_for_keys=False,
            allow_agent=False,
            timeout=20  # Timeout para a conexão inicial
        )
        logging.info("Conexão SSH bem-sucedida.")

        # Combina o comando de desabilitar paginação com o comando real.
        # Isso garante que a saída completa seja recebida.
        full_command = f"screen-length 0 temporary\n{command}\n"

        logging.info(f"Executando comando: '{command}'")
        # Usar exec_command é mais simples e robusto para comandos não-interativos.
        # Ele retorna stdin, stdout, e stderr diretamente.
        stdin, stdout, stderr = client.exec_command(full_command, timeout=30) # Timeout para a execução do comando

        # Lê a saída padrão (stdout) e a saída de erro (stderr)
        output = stdout.read().decode('utf-8', errors='ignore')
        error_output = stderr.read().decode('utf-8', errors='ignore')

        # Verifica se houve algum erro na execução do comando
        if error_output:
            # Muitos dispositivos enviam avisos inofensivos para stderr, mas é bom registrar.
            logging.warning(f"Recebida saída de erro (stderr) de {host}: {error_output.strip()}")
            # Dependendo do caso, você pode querer tratar isso como um erro fatal:
            # raise Exception(f"Erro na execução do comando: {error_output.strip()}")

        # A saída de stdout de exec_command já é limpa (sem prompt ou eco de comando).
        # No entanto, a saída do comando 'screen-length' pode aparecer. Vamos removê-la.
        # Isso torna o código mais limpo que a versão original.
        lines = output.splitlines()
        command_line_index = -1
        for i, line in enumerate(lines):
            # Encontra a linha onde o comando principal foi ecoado
            if command in line:
                command_line_index = i
                break

        if command_line_index != -1:
            # Retorna tudo que veio depois da linha do comando
            clean_output = "\n".join(lines[command_line_index + 1:]).strip()
        else:
            # Se não encontrar o eco do comando, retorna a saída como está,
            # removendo o comando de paginação se ele estiver lá.
            clean_output = output.replace('screen-length 0 temporary', '').strip()

        logging.info(f"Saída final limpa recebida de {host}:\n---\n{clean_output}\n---")
        return clean_output

    except paramiko.AuthenticationException:
        logging.error(f"Erro de autenticação para o host {host}.")
        # Propaga a exceção para ser tratada pela API Flask
        raise Exception("Erro de autenticação. Verifique usuário e senha.")
    except Exception as e:
        logging.error(f"Um erro ocorreu ao conectar ou executar o comando em {host}: {e}", exc_info=True)
        # Propaga a exceção com uma mensagem clara
        raise Exception(f"Erro na operação SSH em {host}: {e}")
    finally:
        if client:
            client.close()
            logging.info(f"Conexão SSH com {host} fechada.")


# --- Configuração da API com Flask ---
app = Flask(__name__)

@app.route('/execute', methods=['POST'])
def handle_execute():
    """
    Endpoint da API para receber os detalhes da conexão e o comando a ser executado.
    """
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
    port = data.get('port', 22) # Usa a porta 22 como padrão

    try:
        command_output = execute_huawei_command(host, port, username, password, command)
        return jsonify({
            "status": "success",
            "host": host,
            "command": command,
            "output": command_output
        })
    except Exception as e:
        # Retorna um erro 500 (Internal Server Error) se a função SSH falhar
        return jsonify({
            "status": "error",
            "host": host,
            "command": command,
            "message": str(e)
        }), 500

# Se este script for executado diretamente, inicie o servidor Flask.
# Em produção, use um servidor WSGI como Gunicorn.
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5500, debug=True)
