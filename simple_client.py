import socket
import re
import os
import json
import time
from dataclasses import dataclass
from typing import List, Optional, Tuple
from enum import Enum

# Configurazione
HOST = '0.0.0.0'
PORT = 5555
BOOKMARKS_FILE = "bookmarks.json"
HISTORY_FILE = "history.json"
MAX_HISTORY = 100

# Colori ANSI
class Colors:
    RESET = "\033[0m"
    TITLE = "\033[1;34m"       # Blu intenso
    SUBTITLE = "\033[1;36m"    # Ciano
    BULLET = "\033[1;33m"      # Giallo
    LINK = "\033[1;32m"        # Verde
    BOLD = "\033[1m"
    ERROR = "\033[1;31m"       # Rosso
    PATH = "\033[1;35m"        # Magenta per breadcrumb
    SUCCESS = "\033[1;92m"     # Verde chiaro
    WARNING = "\033[1;93m"     # Giallo chiaro
    CODE = "\033[90m"          # Grigio
    QUOTE = "\033[35m"         # Magenta

@dataclass
class SimpleNetResponse:
    """Risposta dal server"""
    status_code: str
    status_message: str
    content: str
    content_type: str = "text/smd"

class SimpleNetClient:
    def __init__(self):
        self.history_back = []
        self.history_forward = []
        self.bookmarks = self._load_bookmarks()
        self.connection_timeout = 10.0
        
    def _load_bookmarks(self) -> dict:
        """Carica i segnalibri dal file"""
        try:
            if os.path.exists(BOOKMARKS_FILE):
                with open(BOOKMARKS_FILE, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception as e:
            print(f"{Colors.WARNING}⚠️ Errore caricamento segnalibri: {e}{Colors.RESET}")
        return {}
        
    def _save_bookmarks(self) -> None:
        """Salva i segnalibri nel file"""
        try:
            with open(BOOKMARKS_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.bookmarks, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"{Colors.ERROR}❌ Errore salvataggio segnalibri: {e}{Colors.RESET}")
            
    def _save_history(self) -> None:
        """Salva la cronologia"""
        try:
            history_data = {
                'back': self.history_back[-MAX_HISTORY:],
                'forward': self.history_forward[-MAX_HISTORY:]
            }
            with open(HISTORY_FILE, 'w', encoding='utf-8') as f:
                json.dump(history_data, f, indent=2)
        except Exception as e:
            print(f"{Colors.WARNING}⚠️ Errore salvataggio cronologia: {e}{Colors.RESET}")
            
    def _load_history(self) -> None:
        """Carica la cronologia"""
        try:
            if os.path.exists(HISTORY_FILE):
                with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.history_back = data.get('back', [])
                    self.history_forward = data.get('forward', [])
        except Exception as e:
            print(f"{Colors.WARNING}⚠️ Errore caricamento cronologia: {e}{Colors.RESET}")

    def clear_screen(self) -> None:
        """Pulisce lo schermo"""
        os.system('cls' if os.name == 'nt' else 'clear')

    def parse_response(self, raw_response: str) -> SimpleNetResponse:
        """Parse della risposta del server"""
        try:
            if '\r\n\r\n' in raw_response:
                header_part, content = raw_response.split('\r\n\r\n', 1)
            elif '\n\n' in raw_response:
                header_part, content = raw_response.split('\n\n', 1)
            else:
                # Formato legacy - tutto è contenuto
                return SimpleNetResponse("20", "OK", raw_response)
                
            lines = header_part.split('\r\n' if '\r\n' in header_part else '\n')
            if not lines:
                return SimpleNetResponse("50", "Server Error", "Risposta malformata")
                
            # Parse prima riga: SIMPLENET/1.0 20 OK
            status_line = lines[0].strip()
            if status_line.startswith('SIMPLENET/1.0'):
                parts = status_line.split(' ', 2)
                if len(parts) >= 3:
                    status_code = parts[1]
                    status_message = parts[2]
                else:
                    status_code = "50"
                    status_message = "Server Error"
            else:
                # Fallback per formato legacy
                return SimpleNetResponse("20", "OK", raw_response)
                
            # Parse headers (opzionale per ora)
            content_type = "text/smd"
            for line in lines[1:]:
                if line.startswith('Content-Type:'):
                    content_type = line.split(':', 1)[1].strip()
                    
            return SimpleNetResponse(status_code, status_message, content, content_type)
            
        except Exception as e:
            return SimpleNetResponse("50", "Client Error", f"Errore parsing risposta: {e}")

    def fetch_page(self, path: str) -> SimpleNetResponse:
        """Recupera una pagina dal server"""
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(self.connection_timeout)
                s.connect((HOST, PORT))
                
                # Invia richiesta in formato protocollo
                request = f"{path}\r\n\r\n"
                s.sendall(request.encode('utf-8'))
                
                # Ricevi risposta
                response_data = b""
                while True:
                    chunk = s.recv(4096)
                    if not chunk:
                        break
                    response_data += chunk
                    # Controlla se abbiamo ricevuto tutto
                    if len(response_data) > 1024*1024:  # Max 1MB
                        break
                        
                response_str = response_data.decode('utf-8', errors='replace')
                return self.parse_response(response_str)
                
        except socket.timeout:
            return SimpleNetResponse("42", "Timeout", 
                f"{Colors.ERROR}❌ Timeout connessione al server{Colors.RESET}")
        except ConnectionRefused:
            return SimpleNetResponse("50", "Connection Error",
                f"{Colors.ERROR}❌ Impossibile connettersi al server {HOST}:{PORT}{Colors.RESET}")
        except Exception as e:
            return SimpleNetResponse("50", "Network Error",
                f"{Colors.ERROR}❌ Errore di rete: {e}{Colors.RESET}")

    def parse_and_display(self, response: SimpleNetResponse) -> List[str]:
        """Parse e visualizzazione del contenuto"""
        # Mostra status se non è OK
        if response.status_code != "20":
            print(f"{Colors.ERROR}Status: {response.status_code} {response.status_message}{Colors.RESET}")
            
        content = response.content
        lines = content.splitlines()
        links = []
        in_code_block = False

        print()  # Riga vuota sopra

        for line in lines:
            line = line.rstrip()

            # Blocchi di codice
            if line.startswith("```"):
                in_code_block = not in_code_block
                if in_code_block:
                    print(Colors.CODE, end="")
                else:
                    print(Colors.RESET, end="")
                continue

            if in_code_block:
                print("    " + line)
                continue

            # Citazioni
            if line.startswith(">"):
                quote = line[1:].strip()
                print(f"{Colors.QUOTE}❝ {quote}{Colors.RESET}")
                continue

            # Titoli
            if line.startswith("### "):
                print(f"{Colors.SUBTITLE}🔹 {line[4:]}{Colors.RESET}")
                continue
            elif line.startswith("## "):
                print(f"{Colors.SUBTITLE}🔷 {line[3:]}{Colors.RESET}")
                continue
            elif line.startswith("# "):
                title = line[2:].upper()
                print(f"\n{Colors.TITLE}{title}{Colors.RESET}")
                print(f"{Colors.TITLE}{'-' * len(title)}{Colors.RESET}")
                continue

            # Liste numerate
            if re.match(r'^\d+\.\s', line):
                print(f"  {line}")
                continue

            # Liste puntate
            if line.startswith("* "):
                print(f"{Colors.BULLET} • {line[2:]}{Colors.RESET}")
                continue

            # Link interni
            if line.startswith("=>"):
                parts = line.split(maxsplit=2)
                if len(parts) >= 2:
                    link = parts[1]
                    text = parts[2] if len(parts) == 3 else link
                    links.append(link)
                    print(f"{Colors.LINK}[{len(links)}] {text}{Colors.RESET}")
                continue

            # Link esterni stile [testo](url)
            def replace_link(match):
                text = match.group(1)
                url = match.group(2)
                links.append(url)
                return f"{Colors.LINK}[{len(links)}] {text}{Colors.RESET}"

            line = re.sub(r'\[(.+?)\]\((https?://[^\s]+)\)', replace_link, line)

            # Formattazione testo
            line = re.sub(r"\*\*(.*?)\*\*", lambda m: f"{Colors.BOLD}{m.group(1)}{Colors.RESET}", line)
            line = re.sub(r"\*(.*?)\*", lambda m: f"\033[3m{m.group(1)}{Colors.RESET}", line)

            print(line)

        print()
        return links

    def render_breadcrumb(self, path: str) -> str:
        """Renderizza il breadcrumb"""
        return f"{Colors.PATH}simple://{path}{Colors.RESET}"

    def show_bookmarks(self) -> None:
        """Mostra i segnalibri"""
        if not self.bookmarks:
            print(f"{Colors.WARNING}📚 Nessun segnalibro salvato{Colors.RESET}")
            return
            
        print(f"\n{Colors.BOLD}📚 I tuoi segnalibri:{Colors.RESET}")
        for i, (name, url) in enumerate(self.bookmarks.items(), 1):
            print(f"{Colors.LINK}[{i}] {name} → {url}{Colors.RESET}")
        print()

    def add_bookmark(self, path: str) -> None:
        """Aggiunge un segnalibro"""
        name = input(f"{Colors.BOLD}📝 Nome del segnalibro: {Colors.RESET}").strip()
        if name:
            self.bookmarks[name] = path
            self._save_bookmarks()
            print(f"{Colors.SUCCESS}✅ Segnalibro '{name}' salvato!{Colors.RESET}")
        else:
            print(f"{Colors.WARNING}⚠️ Nome non valido{Colors.RESET}")

    def show_help(self) -> None:
        """Mostra l'aiuto"""
        help_text = f"""
{Colors.BOLD}🆘 Comandi disponibili:{Colors.RESET}

{Colors.LINK}[numero]{Colors.RESET} → Vai al link numerato
{Colors.LINK}b{Colors.RESET} → Indietro nella cronologia
{Colors.LINK}f{Colors.RESET} → Avanti nella cronologia  
{Colors.LINK}r{Colors.RESET} → Ricarica pagina corrente
{Colors.LINK}h{Colors.RESET} → Mostra questo aiuto
{Colors.LINK}bm{Colors.RESET} → Mostra segnalibri
{Colors.LINK}add{Colors.RESET} → Aggiungi segnalibro
{Colors.LINK}go [url]{Colors.RESET} → Vai direttamente a un URL
{Colors.LINK}q{Colors.RESET} → Esci dal client

{Colors.BOLD}Esempi di navigazione:{Colors.RESET}
• giorgio.net
• giorgio.net/about
• lucia.org
"""
        print(help_text)

    def run(self) -> None:
        """Loop principale del client"""
        self._load_history()
        
        print(f"{Colors.BOLD}🌐 Benvenuto in SimpleNet!{Colors.RESET}")
        print(f"Digita 'h' per l'aiuto o 'q' per uscire")
        
        current_path = input(f"{Colors.BOLD}🔗 Inserisci un indirizzo (es: giorgio.net): {Colors.RESET}").strip()
        if not current_path:
            current_path = "default"

        while True:
            self.clear_screen()

            # Breadcrumb
            print(self.render_breadcrumb(current_path))
            print("-" * (10 + len(current_path)))

            # Carica e mostra pagina
            response = self.fetch_page(current_path)
            links = self.parse_and_display(response)

            # Menu comandi
            print(f"{Colors.BOLD}Comandi:{Colors.RESET}")
            print("  [numero] → link | b/f → nav | r → reload | bm → bookmarks | add → +bookmark | h → help | q → quit")

            choice = input(f"{Colors.BOLD}→ {Colors.RESET}").strip().lower()

            if choice == "q":
                self._save_history()
                print(f"{Colors.SUCCESS}👋 Grazie per aver usato SimpleNet!{Colors.RESET}")
                break
                
            elif choice == "h":
                self.show_help()
                input("Premi invio per continuare...")
                
            elif choice == "b":
                if self.history_back:
                    self.history_forward.append(current_path)
                    current_path = self.history_back.pop()
                else:
                    print(f"{Colors.WARNING}⚠️ Nessuna pagina precedente{Colors.RESET}")
                    input("Premi invio per continuare...")
                    
            elif choice == "f":
                if self.history_forward:
                    self.history_back.append(current_path)
                    current_path = self.history_forward.pop()
                else:
                    print(f"{Colors.WARNING}⚠️ Nessuna pagina avanti{Colors.RESET}")
                    input("Premi invio per continuare...")
                    
            elif choice == "r":
                pass  # Ricarica pagina corrente
                
            elif choice == "bm":
                self.show_bookmarks()
                bookmark_choice = input(f"{Colors.BOLD}Scegli segnalibro [numero] o invio per continuare: {Colors.RESET}").strip()
                if bookmark_choice.isdigit():
                    idx = int(bookmark_choice)
                    bookmarks_list = list(self.bookmarks.values())
                    if 1 <= idx <= len(bookmarks_list):
                        self.history_back.append(current_path)
                        current_path = bookmarks_list[idx - 1]
                        self.history_forward.clear()
                        
            elif choice == "add":
                self.add_bookmark(current_path)
                input("Premi invio per continuare...")
                
            elif choice.startswith("go "):
                new_path = choice[3:].strip()
                if new_path:
                    self.history_back.append(current_path)
                    current_path = new_path
                    self.history_forward.clear()
                    
            elif choice.isdigit():
                idx = int(choice)
                if 1 <= idx <= len(links):
                    self.history_back.append(current_path)
                    current_path = links[idx - 1]
                    self.history_forward.clear()
                else:
                    print(f"{Colors.ERROR}❌ Numero link non valido{Colors.RESET}")
                    input("Premi invio per continuare...")
                    
            else:
                print(f"{Colors.ERROR}❌ Comando non riconosciuto. Digita 'h' per l'aiuto{Colors.RESET}")
                input("Premi invio per continuare...")

def main():
    """Punto di ingresso"""
    try:
        client = SimpleNetClient()
        client.run()
    except KeyboardInterrupt:
        print(f"\n{Colors.SUCCESS}👋 Uscita forzata{Colors.RESET}")
    except Exception as e:
        print(f"{Colors.ERROR}❌ Errore fatale: {e}{Colors.RESET}")

if __name__ == "__main__":
    main()
