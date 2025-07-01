import socket
import re
import os

HOST = '127.0.0.1'
PORT = 5555

# Colori ANSI base
COLOR_RESET = "\033[0m"
COLOR_TITLE = "\033[1;34m"       # Blu intenso
COLOR_SUBTITLE = "\033[1;36m"    # Ciano
COLOR_BULLET = "\033[1;33m"      # Giallo
COLOR_LINK = "\033[1;32m"        # Verde
COLOR_BOLD = "\033[1m"
COLOR_ERROR = "\033[1;31m"       # Rosso
COLOR_PATH = "\033[1;35m"        # Magenta per breadcrumb

def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')

def parse_and_display(content):
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
                print("\033[90m")  # colore grigio per codice
            else:
                print("\033[0m")  # reset colore
            continue

        if in_code_block:
            print("    " + line)
            continue

        # Citazioni
        if line.startswith(">"):
            quote = line[1:].strip()
            print(f"\033[35m❝ {quote}\033[0m")
            continue

        # Titoli
        if line.startswith("### "):
            print(f"{COLOR_SUBTITLE}🔹 {line[4:]}{COLOR_RESET}")
            continue
        elif line.startswith("## "):
            print(f"{COLOR_SUBTITLE}🔷 {line[3:]}{COLOR_RESET}")
            continue
        elif line.startswith("# "):
            title = line[2:].upper()
            print(f"\n{COLOR_TITLE}{title}{COLOR_RESET}")
            print(f"{COLOR_TITLE}{'-' * len(title)}{COLOR_RESET}")
            continue

        # Liste numerate
        if re.match(r'^\d+\.\s', line):
            print(f"  {line}")
            continue

        # Liste puntate
        if line.startswith("* "):
            print(f"{COLOR_BULLET} • {line[2:]}{COLOR_RESET}")
            continue

        # Link interni o esterni
        if line.startswith("=>"):
            parts = line.split(maxsplit=2)
            if len(parts) >= 2:
                link = parts[1]
                text = parts[2] if len(parts) == 3 else link
                links.append(link)
                print(f"{COLOR_LINK}[{len(links)}] {text}{COLOR_RESET}")
            continue

        # Link esterni stile [testo](url)
        def replace_link(match):
            text = match.group(1)
            url = match.group(2)
            links.append(url)
            return f"{COLOR_LINK}[{len(links)}] {text}{COLOR_RESET}"

        line = re.sub(r'\[(.+?)\]\((https?://[^\s]+)\)', replace_link, line)

        # Grassetto **testo**
        line = re.sub(r"\*\*(.*?)\*\*", lambda m: f"{COLOR_BOLD}{m.group(1)}{COLOR_RESET}", line)
        # Corsivo *testo*
        line = re.sub(r"\*(.*?)\*", lambda m: f"\033[3m{m.group(1)}{COLOR_RESET}", line)

        print(line)

    print()
    return links

def fetch_page(path):
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.connect((HOST, PORT))
            s.sendall(path.encode())
            data = s.recv(8192)
            return data.decode()
    except Exception as e:
        return f"{COLOR_ERROR}❌ Errore di connessione: {e}{COLOR_RESET}"

def render_breadcrumb(path_list):
    # path_list è una lista di segmenti, es ['giorgio.net', 'about', 'team']
    breadcrumb = " > ".join(path_list)
    return f"{COLOR_PATH}simple://{breadcrumb}{COLOR_RESET}"

def split_path(path):
    # divide per '/' i segmenti di un percorso semplice
    return [seg for seg in path.strip().split("/") if seg]

def main():
    history_back = []
    history_forward = []

    current_path = input(f"{COLOR_BOLD}🌐 Inserisci un indirizzo (es: giorgio.net): {COLOR_RESET}").strip()
    if not current_path:
        current_path = "default"



    while True:
        clear_screen()

        # Visualizzo breadcrumb
        path_segments = split_path(current_path)
        print(render_breadcrumb(path_segments))
        print("-" * (10 + len(current_path)))

        page = fetch_page(current_path)
        links = parse_and_display(page)

        print(f"{COLOR_BOLD}Comandi:{COLOR_RESET}")
        print("  [numero] → vai al link")
        print("  b → indietro")
        print("  f → avanti")
        print("  r → ricarica pagina")
        print("  q → esci")

        choice = input(f"{COLOR_BOLD}→ {COLOR_RESET}").strip().lower()

        if choice == "q":
            print(f"{COLOR_BOLD}👋 Grazie per aver usato SimpleNet!{COLOR_RESET}")
            break
        elif choice == "b":
            if history_back:
                history_forward.append(current_path)
                current_path = history_back.pop()
            else:
                print(f"{COLOR_ERROR}⚠️ Nessuna pagina precedente.{COLOR_RESET}")
                input("Premi invio per continuare...")
        elif choice == "f":
            if history_forward:
                history_back.append(current_path)
                current_path = history_forward.pop()
            else:
                print(f"{COLOR_ERROR}⚠️ Nessuna pagina avanti.{COLOR_RESET}")
                input("Premi invio per continuare...")
        elif choice == "r":
            # Ricarica pagina corrente: non cambia la cronologia
            pass
        elif choice.isdigit():
            idx = int(choice)
            if 1 <= idx <= len(links):
                history_back.append(current_path)
                current_path = links[idx - 1]
                history_forward.clear()
            else:
                print(f"{COLOR_ERROR}❌ Numero link non valido.{COLOR_RESET}")
                input("Premi invio per continuare...")
        else:
            print(f"{COLOR_ERROR}❌ Comando non riconosciuto.{COLOR_RESET}")
            input("Premi invio per continuare...")

if __name__ == "__main__":
    main()
