#!/usr/bin/env python3
import paramiko
import time
import socket
import logging
from flask import Flask, request, jsonify

# Configuração básica de logging para ver a saída no Docker
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def execute_huawei_command(host, port, username, password, command):
    """
    Conecta a um dispositivo Huawei via SSH, executa um comando e retorna o resultado.
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
            banner_timeout=200,
            timeout=20
        )
        logging.info("Conexão bem-sucedida.")

        channel = client.invoke_shell()
        channel.settimeout(10.0)

        # 1. Limpar o buffer inicial (banner e primeiro prompt)
        logging.info("Limpando buffer inicial...")
        time.sleep(1)
        try:
            initial_buffer = channel.recv(65535).decode('utf-8', errors='ignore')
            logging.info(f"Buffer inicial recebido:\n---\n{initial_buffer}\n---")
        except socket.timeout:
            logging.warning("Timeout ao limpar buffer inicial (normal se não houver banner).")

        # 2. Desabilitar paginação
        logging.info("Desabilitando paginação...")
        channel.send('screen-length 0 temporary\n')
        time.sleep(0.5)
        try:
            channel.recv(65535) # Limpa a resposta do comando de paginação
        except socket.timeout:
            pass

        # 3. Enviar o comando principal
        logging.info(f"Enviando comando: '{command}'")
        channel.send(command + '\n')

        # 4. Ler a saída até que o prompt do switch apareça novamente
        output = ""
        while True:
            try:
                chunk = channel.recv(4096) # Lê em pedaços menores
                if not chunk:
                    break
                
                decoded_chunk = chunk.decode('utf-8', errors='ignore')
                output += decoded_chunk
                logging.info(f"Recebido chunk: {decoded_chunk.strip()}")

                # <-- MUDANÇA: Condição de parada mais flexível e robusta
                # Verifica se o prompt ('>' ou '#') está na última linha recebida.
                # Isso funciona mesmo que haja espaços ou outros caracteres depois do prompt.
                last_line = decoded_chunk.strip().splitlines()[-1] if decoded_chunk.strip() else ""
                if '>' in last_line or '#' in last_line:
                    logging.info(f"Prompt detectado em '{last_line}'. Finalizando a leitura.")
                    break
            except socket.timeout:
                logging.warning("Timeout na leitura do canal. Assumindo que o comando terminou.")
                break
        
        logging.info("Leitura da saída finalizada.")
        channel.send('quit\n') # Envia quit após a leitura

        # 5. Limpeza da saída para remover o comando ecoado e o prompt final
        lines = output.splitlines()
        
        # Encontra a linha onde o comando foi ecoado para começar a limpeza a partir dela
        command_line_index = -1
        for i, line in enumerate(lines):
            if command in line:
                command_line_index = i
                break
        
        if command_line_index != -1 and len(lines) > command_line_index + 1:
            # Pega as linhas entre o eco do comando e o prompt final
            clean_lines = lines[command_line_index + 1:-1]
            clean_output = "\n".join(clean_lines).strip()
        else:
            clean_output = "" # Retorna vazio se a saída não for como esperado

        logging.info(f"Saída final limpa:\n---\n{clean_output}\n---")
        return clean_output

    except paramiko.AuthenticationException:
        logging.error("Erro de autenticação.")
        raise Exception("Erro de autenticação. Verifique usuário e senha.")
    except paramiko.SSHException as ssh_err:
        logging.error(f"Erro no SSH: {ssh_err}")
        raise Exception(f"Erro no SSH: {ssh_err}")
    except socket.error as sock_err:
        logging.error(f"Erro de conexão (socket): {sock_err}")
        raise Exception(f"Erro de conexão (socket): {sock_err}")
    except Exception as e:
        logging.error(f"Um erro inesperado ocorreu: {e}", exc_info=True)
        raise Exception(f"Um erro inesperado ocorreu: {e}")
    finally:
        if client:
            client.close()
            logging.info("Conexão SSH fechada.")


# --- Configuração da API com Flask ---
app = Flask(__name__)

@app.route('/execute', methods=['POST'])
def handle_execute():
    data = request.get_json()
    if not data:
        return jsonify({"error": "Payload da requisição deve ser em formato JSON."}), 400

    required_fields = ['host', 'username', 'password', 'command']
    if not all(field in data for field in required_fields):
        return jsonify({"error": f"Campos obrigatórios ausentes. É preciso ter: {required_fields}"}), 400

    host = data['host']
    username = data['username']
    password = data['password']
    command = data['command']
    port = data.get('port', 22)

    try:
        command_output = execute_huawei_command(host, port, username, password, command)
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
            "message": str(e)
        }), 500

```

Por favor, atualize seu arquivo `ssh_api.py`, reconstrua a imagem e teste novamente. Se o problema persistir, os logs do `docker logs` que você coletar serão a chave para resolvermos de v
