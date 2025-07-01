#!/usr/bin/env python3
import paramiko
import time
import socket
from flask import Flask, request, jsonify

# --- Lógica principal do seu script, agora em uma função ---
# Esta função recebe os parâmetros e retorna o output ou levanta uma exceção.
def execute_huawei_command(host, port, username, password, command):
    """
    Conecta a um dispositivo Huawei via SSH, executa um comando e retorna o resultado.
    """
    output = ''
    client = None # Inicializa client como None para o bloco finally
    try:
        # Cria o cliente SSH e aceita hosts desconhecidos
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        
        # Tenta conectar ao dispositivo
        client.connect(
            hostname=host,
            port=port,
            username=username,
            password=password,
            look_for_keys=False,
            allow_agent=False,
            banner_timeout=200,
            timeout=20 # Aumentado para conexões mais lentas
        )

        # Inicia um shell interativo
        channel = client.invoke_shell()
        channel.settimeout(5.0) # Timeout para operações no canal

        # Espera pelo banner e o limpa
        time.sleep(1)
        try:
            # Lê o buffer inicial para limpá-lo
            channel.recv(65535)
        except socket.timeout:
            pass # É normal um timeout aqui se não houver banner imediato

        # 1) Desliga a paginação para receber a saída completa de uma vez
        channel.send('screen-length 0 temporary\n')
        time.sleep(0.5)
        try:
            # Limpa o buffer da resposta do comando de paginação
            channel.recv(65535)
        except socket.timeout:
            pass

        # 2) Envia o comando principal que queremos executar
        channel.send(command + '\n')
        time.sleep(2) # Aumenta a espera para comandos que demoram mais para executar

        # 3) Envia 'quit' para fechar a sessão de forma limpa
        channel.send('quit\n')
        time.sleep(0.5)

        # 4) Lê toda a saída do canal até que ele feche
        while not channel.closed:
            # Espera até que o status de saída esteja pronto ou haja dados para ler
            if channel.exit_status_ready() and not channel.recv_ready():
                break
            
            try:
                chunk = channel.recv(65535)
                if chunk:
                    output += chunk.decode('utf-8', errors='ignore')
                else:
                    # Se não há mais bytes, o canal foi fechado pelo servidor
                    break
            except socket.timeout:
                # Se o timeout ocorrer, consideramos que a saída terminou
                break
        
        return output

    except paramiko.AuthenticationException:
        raise Exception("Erro de autenticação. Verifique usuário e senha.")
    except paramiko.SSHException as ssh_err:
        raise Exception(f"Erro no SSH: {ssh_err}")
    except socket.error as sock_err:
        raise Exception(f"Erro de conexão (socket): {sock_err}")
    except Exception as e:
        # Captura qualquer outro erro inesperado
        raise Exception(f"Um erro inesperado ocorreu: {e}")
    finally:
        # Garante que a conexão seja sempre fechada
        if client:
            client.close()


# --- Configuração da API com Flask ---
app = Flask(__name__)

@app.route('/execute', methods=['POST'])
def handle_execute():
    """
    Endpoint da API para executar o comando.
    Espera um JSON no corpo da requisição com os seguintes campos:
    {
        "host": "192.168.1.1",
        "username": "admin",
        "password": "your_password",
        "command": "display interface brief",
        "port": 22 (opcional)
    }
    """
    # Pega os dados JSON da requisição
    data = request.get_json()

    if not data:
        return jsonify({"error": "Payload da requisição deve ser em formato JSON."}), 400

    # Valida se os campos obrigatórios foram enviados
    required_fields = ['host', 'username', 'password', 'command']
    if not all(field in data for field in required_fields):
        return jsonify({"error": f"Campos obrigatórios ausentes. É preciso ter: {required_fields}"}), 400

    # Extrai os dados do JSON
    host = data['host']
    username = data['username']
    password = data['password']
    command = data['command']
    port = data.get('port', 22) # Usa a porta 22 como padrão se não for fornecida

    try:
        # Chama a função principal e obtém o resultado
        command_output = execute_huawei_command(host, port, username, password, command)
        
        # Retorna o resultado com sucesso
        return jsonify({
            "status": "success",
            "host": host,
            "command": command,
            "output": command_output
        })

    except Exception as e:
        # Se ocorrer qualquer erro na função, retorna uma mensagem de erro
        return jsonify({
            "status": "error",
            "host": host,
            "message": str(e)
        }), 500

# --- Ponto de entrada para rodar o servidor Flask ---
if __name__ == '__main__':
    # Roda o servidor na porta 5000, acessível por qualquer IP da máquina
    # ATENÇÃO: debug=True não deve ser usado em produção!
    app.run(host='0.0.0.0', port=5000, debug=True)
