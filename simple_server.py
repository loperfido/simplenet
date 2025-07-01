import socket
import os
import json

HOST = '127.0.0.1'
PORT = 5555

PAGES_DIR = "pages"
DNS_FILE = "dns.json"

def load_dns():
    """Carica il file dns.json se presente"""
    try:
        with open(DNS_FILE, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}

DNS = load_dns()

def get_page_content(requested_path):
    """
    Risolve una richiesta tipo 'giorgio.net/about'
    o solo 'giorgio.net' (shortcut per 'home')
    """
    if '/' in requested_path:
        domain, page = requested_path.split('/', 1)
    else:
        # Shortcut: giorgio.net → giorgio.net/home
        domain = requested_path
        page = "home"

    # Risolvi cartella del dominio
    domain_folder = DNS.get(domain, domain)
    file_path = os.path.join(PAGES_DIR, domain_folder, page + '.smd')

    if os.path.exists(file_path):
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read()
    else:
        return f"❌ 404 - Pagina '{page}' non trovata su '{domain}'."

def run_server():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server_socket:
        server_socket.bind((HOST, PORT))
        server_socket.listen()
        print(f"🛰  Server SimpleNet attivo su {HOST}:{PORT}")

        while True:
            conn, addr = server_socket.accept()
            with conn:
                print(f"🌐 Connessione da {addr}")
                requested_path = conn.recv(1024).decode().strip()
                print(f"📥 Richiesta: {requested_path}")
                content = get_page_content(requested_path)
                conn.sendall(content.encode())

if __name__ == "__main__":
    run_server()
