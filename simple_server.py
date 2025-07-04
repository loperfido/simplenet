import socket
import os
import json
import threading
import time
import logging
from dataclasses import dataclass
from typing import Optional, Dict, Any
from enum import Enum

# Configurazione logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('simplenet.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class StatusCode(Enum):
    """Status codes per il protocollo SimpleNet"""
    OK = "20"
    NOT_FOUND = "40" 
    SERVER_ERROR = "50"
    BAD_REQUEST = "41"
    TIMEOUT = "42"

@dataclass
class SimpleNetResponse:
    """Struttura per le risposte del server"""
    status: StatusCode
    message: str
    content: str = ""
    content_type: str = "text/smd"
    
    def to_bytes(self) -> bytes:
        """Converte la risposta in formato wire protocol"""
        header = f"SIMPLENET/1.0 {self.status.value} {self.message}\r\n"
        header += f"Content-Type: {self.content_type}\r\n"
        header += f"Content-Length: {len(self.content.encode('utf-8'))}\r\n"
        header += "\r\n"
        return (header + self.content).encode('utf-8')

class SimpleNetServer:
    def __init__(self, host='0.0.0.0', port=5555, max_connections=10):
        self.host = host
        self.port = port
        self.max_connections = max_connections
        self.pages_dir = "pages"
        self.dns_file = "dns.json"
        self.dns_cache = {}
        self.dns_last_modified = 0
        self.connection_count = 0
        self.rate_limiter = {}  # IP -> [timestamps]
        self.max_requests_per_minute = 60
        
        # Carica DNS iniziale
        self._reload_dns()
        
    def _reload_dns(self) -> None:
        """Ricarica il file DNS se modificato"""
        try:
            if not os.path.exists(self.dns_file):
                logger.warning(f"File DNS {self.dns_file} non trovato")
                self.dns_cache = {}
                return
                
            mtime = os.path.getmtime(self.dns_file)
            if mtime > self.dns_last_modified:
                with open(self.dns_file, "r", encoding='utf-8') as f:
                    self.dns_cache = json.load(f)
                self.dns_last_modified = mtime
                logger.info(f"DNS ricaricato: {len(self.dns_cache)} domini")
        except (json.JSONDecodeError, IOError) as e:
            logger.error(f"Errore caricamento DNS: {e}")
            
    def _check_rate_limit(self, client_ip: str) -> bool:
        """Controlla rate limiting per IP"""
        now = time.time()
        minute_ago = now - 60
        
        if client_ip not in self.rate_limiter:
            self.rate_limiter[client_ip] = []
            
        # Rimuovi richieste più vecchie di un minuto
        self.rate_limiter[client_ip] = [
            timestamp for timestamp in self.rate_limiter[client_ip] 
            if timestamp > minute_ago
        ]
        
        # Controlla limite
        if len(self.rate_limiter[client_ip]) >= self.max_requests_per_minute:
            return False
            
        # Aggiungi timestamp corrente
        self.rate_limiter[client_ip].append(now)
        return True
        
    def _parse_request(self, request: str) -> Dict[str, Any]:
        """Parse della richiesta client"""
        lines = request.strip().split('\r\n')
        if not lines:
            return {'path': '', 'valid': False}
            
        path = lines[0].strip()
        
        # Validazione base del path
        if not path or len(path) > 256:
            return {'path': path, 'valid': False}
            
        # Caratteri non permessi
        forbidden_chars = ['..', '<', '>', '|', '*', '?', '"']
        if any(char in path for char in forbidden_chars):
            return {'path': path, 'valid': False}
            
        return {'path': path, 'valid': True}
        
    def _get_page_content(self, requested_path: str) -> SimpleNetResponse:
        """Risolve e carica il contenuto della pagina"""
        try:
            # Ricarica DNS se necessario
            self._reload_dns()
            
            # Parse del path
            if '/' in requested_path:
                domain, page = requested_path.split('/', 1)
            else:
                domain = requested_path
                page = "home"
                
            # Risoluzione dominio
            domain_folder = self.dns_cache.get(domain, domain)
            file_path = os.path.join(self.pages_dir, domain_folder, page + '.smd')
            
            # Normalizza path per sicurezza
            file_path = os.path.normpath(file_path)
            pages_abs = os.path.abspath(self.pages_dir)
            file_abs = os.path.abspath(file_path)
            
            # Verifica che il file sia dentro pages_dir (sicurezza)
            if not file_abs.startswith(pages_abs):
                logger.warning(f"Tentativo di accesso fuori da pages_dir: {file_path}")
                return SimpleNetResponse(
                    StatusCode.BAD_REQUEST,
                    "Bad Request",
                    "❌ Percorso non valido"
                )
            
            # Carica file
            if os.path.exists(file_path) and os.path.isfile(file_path):
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    
                logger.info(f"Servita pagina: {requested_path} -> {file_path}")
                return SimpleNetResponse(
                    StatusCode.OK,
                    "OK",
                    content
                )
            else:
                logger.info(f"Pagina non trovata: {requested_path}")
                return SimpleNetResponse(
                    StatusCode.NOT_FOUND,
                    "Not Found",
                    f"❌ 404 - Pagina '{page}' non trovata su '{domain}'.\n\n"
                    f"Domini disponibili: {', '.join(self.dns_cache.keys())}"
                )
                
        except UnicodeDecodeError as e:
            logger.error(f"Errore encoding file {file_path}: {e}")
            return SimpleNetResponse(
                StatusCode.SERVER_ERROR,
                "Server Error",
                "❌ Errore di codifica del file"
            )
        except Exception as e:
            logger.error(f"Errore server per {requested_path}: {e}")
            return SimpleNetResponse(
                StatusCode.SERVER_ERROR,
                "Server Error",
                "❌ Errore interno del server"
            )
            
    def _handle_client(self, conn: socket.socket, addr: tuple) -> None:
        """Gestisce una singola connessione client"""
        client_ip = addr[0]
        
        try:
            # Rate limiting
            if not self._check_rate_limit(client_ip):
                logger.warning(f"Rate limit superato per {client_ip}")
                response = SimpleNetResponse(
                    StatusCode.BAD_REQUEST,
                    "Too Many Requests",
                    "❌ Troppe richieste. Riprova tra un minuto."
                )
                conn.sendall(response.to_bytes())
                return
                
            # Timeout per la ricezione
            conn.settimeout(10.0)
            
            # Ricevi richiesta
            request_data = b""
            while len(request_data) < 1024:  # Max 1KB per richiesta
                chunk = conn.recv(1024 - len(request_data))
                if not chunk:
                    break
                request_data += chunk
                if b'\r\n\r\n' in request_data or b'\n\n' in request_data:
                    break
                    
            if not request_data:
                logger.warning(f"Richiesta vuota da {client_ip}")
                return
                
            request_str = request_data.decode('utf-8', errors='replace')
            parsed = self._parse_request(request_str)
            
            logger.info(f"🌐 {client_ip} richiede: {parsed['path']}")
            
            if not parsed['valid']:
                response = SimpleNetResponse(
                    StatusCode.BAD_REQUEST,
                    "Bad Request",
                    "❌ Richiesta non valida"
                )
            else:
                response = self._get_page_content(parsed['path'])
                
            # Invia risposta
            conn.sendall(response.to_bytes())
            
        except socket.timeout:
            logger.warning(f"Timeout connessione da {client_ip}")
            try:
                response = SimpleNetResponse(
                    StatusCode.TIMEOUT,
                    "Timeout",
                    "❌ Timeout della richiesta"
                )
                conn.sendall(response.to_bytes())
            except:
                pass
        except Exception as e:
            logger.error(f"Errore gestione client {client_ip}: {e}")
        finally:
            try:
                conn.close()
            except:
                pass
            self.connection_count -= 1
            
    def run(self) -> None:
        """Avvia il server"""
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server_socket:
            # Opzioni socket
            server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            
            try:
                server_socket.bind((self.host, self.port))
                server_socket.listen(self.max_connections)
                logger.info(f"🛰  Server SimpleNet avviato su {self.host}:{self.port}")
                logger.info(f"📁 Directory pagine: {os.path.abspath(self.pages_dir)}")
                logger.info(f"🌐 Domini caricati: {len(self.dns_cache)}")
                
                while True:
                    try:
                        conn, addr = server_socket.accept()
                        
                        # Controllo numero massimo connessioni
                        if self.connection_count >= self.max_connections:
                            logger.warning(f"Massimo numero connessioni raggiunto")
                            conn.close()
                            continue
                            
                        self.connection_count += 1
                        
                        # Gestisci in thread separato
                        client_thread = threading.Thread(
                            target=self._handle_client,
                            args=(conn, addr),
                            daemon=True
                        )
                        client_thread.start()
                        
                    except KeyboardInterrupt:
                        logger.info("🛑 Arresto server richiesto")
                        break
                    except Exception as e:
                        logger.error(f"Errore accettazione connessione: {e}")
                        
            except OSError as e:
                logger.error(f"Errore binding socket {self.host}:{self.port}: {e}")
                raise

def main():
    """Punto di ingresso principale"""
    try:
        # Verifica directory
        if not os.path.exists("pages"):
            os.makedirs("pages")
            logger.info("Creata directory 'pages'")
            
        server = SimpleNetServer()
        server.run()
        
    except KeyboardInterrupt:
        logger.info("👋 Server fermato dall'utente")
    except Exception as e:
        logger.error(f"Errore fatale: {e}")
        raise

if __name__ == "__main__":
    main()
