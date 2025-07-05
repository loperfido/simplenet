import re
import os
import json
import time
import uuid
import paho.mqtt.client as mqtt
from dataclasses import dataclass
from typing import List

# Configurazione
BOOKMARKS_FILE = "bookmarks.json"
HISTORY_FILE = "history.json"
MAX_HISTORY = 100

# Colori ANSI
class Colors:
    RESET = "\033[0m"
    TITLE = "\033[1;34m"
    SUBTITLE = "\033[1;36m"
    BULLET = "\033[1;33m"
    LINK = "\033[1;32m"
    BOLD = "\033[1m"
    ERROR = "\033[1;31m"
    PATH = "\033[1;35m"
    SUCCESS = "\033[1;92m"
    WARNING = "\033[1;93m"
    CODE = "\033[90m"
    QUOTE = "\033[35m"

@dataclass
class SimpleNetResponse:
    """Risposta dal server (ricevuta via MQTT)"""
    status_code: str
    status_message: str
    content: str
    content_type: str = "text/smd"

class MqttNetClient:
    """Gestisce la comunicazione di rete tramite MQTT"""
    def __init__(self):
        self.broker = "broker.emqx.io"
        self.port = 1883
        self.client_id = f'simplenet-client-{uuid.uuid4().hex[:6]}'
        self.request_topic = "simplenet/request"
        self.response_topic = f"simplenet/response/{self.client_id}"
        
        self.client = mqtt.Client()
        self.client.on_connect = self._on_connect
        self.client.on_message = self._on_message
        
        self.response_data = None
        self.response_received = False
        self.connection_timeout = 15.0

    def _on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            client.subscribe(self.response_topic)
        else:
            print(f"{Colors.ERROR}Errore connessione MQTT: {rc}{Colors.RESET}")

    def _on_message(self, client, userdata, msg):
        self.response_data = msg.payload
        self.response_received = True

    def connect(self):
        try:
            self.client.connect(self.broker, self.port, 60)
            self.client.loop_start()
            time.sleep(1) # Attesa per connessione
            return True
        except Exception as e:
            print(f"{Colors.ERROR}Impossibile connettersi al broker: {e}{Colors.RESET}")
            return False

    def disconnect(self):
        self.client.loop_stop()
        self.client.disconnect()

    def fetch_page(self, path: str) -> SimpleNetResponse:
        self.response_data = None
        self.response_received = False
        
        request_payload = json.dumps({
            "client_id": self.client_id,
            "path": path
        })
        
        self.client.publish(self.request_topic, request_payload, qos=1)
        
        start_time = time.time()
        while not self.response_received:
            if time.time() - start_time > self.connection_timeout:
                return SimpleNetResponse("42", "Timeout", f"{Colors.ERROR}❌ Timeout: nessuna risposta dal server{Colors.RESET}")
            time.sleep(0.1)
        
        try:
            data = json.loads(self.response_data.decode('utf-8'))
            return SimpleNetResponse(
                status_code=data.get("status_code", "50"),
                status_message=data.get("status_message", "Client Error"),
                content=data.get("content", "Risposta malformata"),
                content_type=data.get("content_type", "text/smd")
            )
        except (json.JSONDecodeError, AttributeError):
            return SimpleNetResponse("50", "Client Error", f"{Colors.ERROR}❌ Errore parsing JSON dal server{Colors.RESET}")


class SimpleNetMqttClient:
    def __init__(self):
        self.net_client = MqttNetClient()
        self.history_back = []
        self.history_forward = []
        self.bookmarks = self._load_bookmarks()

    def _load_bookmarks(self) -> dict:
        try:
            if os.path.exists(BOOKMARKS_FILE):
                with open(BOOKMARKS_FILE, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception as e:
            print(f"{Colors.WARNING}⚠️ Errore caricamento segnalibri: {e}{Colors.RESET}")
        return {}

    def _save_bookmarks(self) -> None:
        try:
            with open(BOOKMARKS_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.bookmarks, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"{Colors.ERROR}❌ Errore salvataggio segnalibri: {e}{Colors.RESET}")

    def _save_history(self) -> None:
        try:
            history_data = {
                'back': self.history_back[-MAX_HISTORY:],
                'forward': self.history_forward[-MAX_HISTORY:]
            }
            with open(HISTORY_FILE, 'w', encoding='utf-8') as f:
                json.dump(history_data, f, indent=2)
        except Exception as e:
            print(f"{Colors.WARNING}⚠️ Errore caricamento cronologia: {e}{Colors.RESET}")

    def _load_history(self) -> None:
        try:
            if os.path.exists(HISTORY_FILE):
                with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.history_back = data.get('back', [])
                    self.history_forward = data.get('forward', [])
        except Exception as e:
            print(f"{Colors.WARNING}⚠️ Errore caricamento cronologia: {e}{Colors.RESET}")

    def clear_screen(self) -> None:
        os.system('cls' if os.name == 'nt' else 'clear')

    def parse_and_display(self, response: SimpleNetResponse) -> List[str]:
        if response.status_code != "20":
            print(f"{Colors.ERROR}Status: {response.status_code} {response.status_message}{Colors.RESET}")
        
        content = response.content
        lines = content.splitlines()
        links = []
        in_code_block = False

        print()

        for line in lines:
            line = line.rstrip()

            if line.startswith("```"):
                in_code_block = not in_code_block
                print(Colors.CODE if in_code_block else Colors.RESET, end="")
                continue

            if in_code_block:
                print("    " + line)
                continue

            if line.startswith(">"):
                print(f"{Colors.QUOTE}❝ {line[1:].strip()}{Colors.RESET}")
                continue

            if line.startswith("### "):
                print(f"{Colors.SUBTITLE}🔹 {line[4:]}{Colors.RESET}")
            elif line.startswith("## "):
                print(f"{Colors.SUBTITLE}🔷 {line[3:]}{Colors.RESET}")
            elif line.startswith("# "):
                title = line[2:].upper()
                print(f"\n{Colors.TITLE}{title}{Colors.RESET}")
                print(f"{Colors.TITLE}{'-' * len(title)}{Colors.RESET}")
            elif re.match(r'^\d+\.\s', line):
                print(f"  {line}")
            elif line.startswith("* "):
                print(f"{Colors.BULLET} • {line[2:]}{Colors.RESET}")
            elif line.startswith("=>"):
                parts = line.split(maxsplit=2)
                if len(parts) >= 2:
                    link = parts[1]
                    text = parts[2] if len(parts) == 3 else link
                    links.append(link)
                    print(f"{Colors.LINK}[{len(links)}] {text}{Colors.RESET}")
            else:
                def replace_link(match):
                    text = match.group(1)
                    url = match.group(2)
                    links.append(url)
                    return f"{Colors.LINK}[{len(links)}] {text}{Colors.RESET}"
                line = re.sub(r'\[(.+?)\]\((https?://[^\s]+)\)', replace_link, line)
                line = re.sub(r"\*\*(.*?)\*\*", lambda m: f"{Colors.BOLD}{m.group(1)}{Colors.RESET}", line)
                line = re.sub(r"\*(.*?)\*", lambda m: f"\033[3m{m.group(1)}{Colors.RESET}", line)
                print(line)

        print()
        return links

    def render_breadcrumb(self, path: str) -> str:
        return f"{Colors.PATH}simple://{path}{Colors.RESET}"

    def show_bookmarks(self) -> None:
        if not self.bookmarks:
            print(f"{Colors.WARNING}📚 Nessun segnalibro salvato{Colors.RESET}")
            return
        print(f"\n{Colors.BOLD}📚 I tuoi segnalibri:{Colors.RESET}")
        for i, (name, url) in enumerate(self.bookmarks.items(), 1):
            print(f"{Colors.LINK}[{i}] {name} → {url}{Colors.RESET}")
        print()

    def add_bookmark(self, path: str) -> None:
        name = input(f"{Colors.BOLD}📝 Nome del segnalibro: {Colors.RESET}").strip()
        if name:
            self.bookmarks[name] = path
            self._save_bookmarks()
            print(f"{Colors.SUCCESS}✅ Segnalibro '{name}' salvato!{Colors.RESET}")
        else:
            print(f"{Colors.WARNING}⚠️ Nome non valido{Colors.RESET}")

    def show_help(self) -> None:
        help_text = f"""
{Colors.BOLD}🆘 Comandi disponibili:{Colors.RESET}
{Colors.LINK}[numero]{Colors.RESET} → Vai al link numerato
{Colors.LINK}b{Colors.RESET} → Indietro
{Colors.LINK}f{Colors.RESET} → Avanti
{Colors.LINK}r{Colors.RESET} → Ricarica
{Colors.LINK}h{Colors.RESET} → Aiuto
{Colors.LINK}bm{Colors.RESET} → Segnalibri
{Colors.LINK}add{Colors.RESET} → Aggiungi segnalibro
{Colors.LINK}go [url]{Colors.RESET} → Vai a URL
{Colors.LINK}q{Colors.RESET} → Esci
"""
        print(help_text)

    def run(self) -> None:
        if not self.net_client.connect():
            return

        self._load_history()
        
        print(f"{Colors.BOLD}🌐 Benvenuto in SimpleNet-MQTT!{Colors.RESET}")
        print(f"Digita 'h' per l'aiuto o 'q' per uscire")
        
        current_path = input(f"{Colors.BOLD}🔗 Inserisci un indirizzo (es: giorgio.net): {Colors.RESET}").strip()
        if not current_path:
            current_path = "default"

        while True:
            self.clear_screen()
            print(self.render_breadcrumb(current_path))
            print("-" * (10 + len(current_path)))

            response = self.net_client.fetch_page(current_path)
            links = self.parse_and_display(response)

            print(f"{Colors.BOLD}Comandi:{Colors.RESET}")
            print("  [numero] → link | b/f → nav | r → reload | bm → bookmarks | add → +bookmark | h → help | q → quit")
            choice = input(f"{Colors.BOLD}→ {Colors.RESET}").strip().lower()

            if choice == "q":
                self._save_history()
                self.net_client.disconnect()
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
                pass
            elif choice == "bm":
                self.show_bookmarks()
                bookmark_choice = input(f"{Colors.BOLD}Scegli [numero] o invio: {Colors.RESET}").strip()
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
                print(f"{Colors.ERROR}❌ Comando non riconosciuto{Colors.RESET}")
                input("Premi invio per continuare...")

def main():
    try:
        client = SimpleNetMqttClient()
        client.run()
    except KeyboardInterrupt:
        print(f"\n{Colors.SUCCESS}👋 Uscita forzata{Colors.RESET}")
    except Exception as e:
        print(f"{Colors.ERROR}❌ Errore fatale: {e}{Colors.RESET}")

if __name__ == "__main__":
    main()