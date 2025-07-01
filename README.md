# SimpleNet

Un sistema di navigazione web minimalista basato su protocollo TCP personalizzato.

## Caratteristiche

- **Protocollo personalizzato**: Comunicazione TCP diretta senza HTTP
- **Markup semplificato**: Formato `.smd` (Simple Markdown) per contenuti
- **Client colorato**: Interfaccia terminale con evidenziazione ANSI
- **Sistema DNS locale**: Risoluzione domini tramite file JSON
- **Navigazione completa**: Cronologia avanti/indietro, ricarica pagina
- **Link interni ed esterni**: Supporto per collegamenti tra pagine e verso il web

## Struttura del Progetto

```
simplenet/
├── simple_server.py      # Server TCP per gestire richieste
├── simple_client.py      # Client terminale con interfaccia colorata
├── dns.json             # Risoluzione domini locali
└── pages/               # Directory contenuti
    ├── default/
    │   └── home.smd     # Pagina di default
    ├── giorgio.net/
    │   ├── home.smd
    │   └── about.smd
    └── lucia.org/
        └── home.smd
```

## Formato .smd (Simple Markdown)

Il formato supporta i seguenti elementi:

### Intestazioni
```
# Titolo principale
## Sottotitolo
### Titolo terziario
```

### Liste
```
1. Lista numerata
2. Secondo elemento

* Lista puntata
* Altro elemento
```

### Link
```
=> giorgio.net/about Testo del link        # Link interno
[OpenAI](https://openai.com)               # Link esterno
```

### Formattazione
```
**testo in grassetto**
*testo in corsivo*

> Citazione

Blocco di codice:
```
print("Hello World")
```
```

## Installazione e Uso

### Prerequisiti
- Python 3.6+
- Sistema Unix/Linux/macOS o Windows con supporto ANSI

### Avvio del Server
```bash
python simple_server.py
```
Il server si avvia su `127.0.0.1:5555`

### Avvio del Client
```bash
python simple_client.py
```

All'avvio, inserisci un dominio (es: `giorgio.net`) o premi invio per la pagina default.

### Comandi del Client
- **[numero]** - Naviga al link numerato
- **b** - Torna indietro nella cronologia
- **f** - Vai avanti nella cronologia  
- **r** - Ricarica la pagina corrente
- **q** - Esci dal client

## Configurazione DNS

Il file `dns.json` mappa i domini alle cartelle:

```json
{
  "giorgio.net": "giorgio.net",
  "lucia.org": "lucia.org"
}
```

Per aggiungere un nuovo dominio:
1. Aggiungi la mappatura in `dns.json`
2. Crea la cartella corrispondente in `pages/`
3. Aggiungi almeno un file `home.smd`

## Esempi di Navigazione

- `giorgio.net` → `pages/giorgio.net/home.smd`
- `giorgio.net/about` → `pages/giorgio.net/about.smd`
- `default` → `pages/default/home.smd`

**SimpleNet** - Un'alternativa minimalista al web moderno 🌐
