# SwarmDev 🐝

**SwarmDev** è un framework sperimentale per la **parallelizzazione agentica deterministica**, basato su un'architettura Event-Driven a microservizi.

L'obiettivo principale del progetto è eliminare il cosiddetto *"Chatter Smell"* (incomprensioni in linguaggio naturale tra agenti IA) durante la scrittura del codice. Per farlo, SwarmDev adotta un approccio basato su **Contratti A2A-OCL** (Agent-to-Agent Object Constraint Language), i quali vengono scambiati in maniera asincrona su code di messaggistica.

---

## 🏛️ L'Architettura: Il "Paradigma della Carrozza"

Il framework è stato re-ingegnerizzato disaccoppiando completamente la cognizione dall'esecuzione. Nessun agente "parla" con l'altro: si scambiano solo file JSON validati.

L'ecosistema si compone di 4 microservizi indipendenti:

1. **🧠 The Mind (Cognizione)**: Costruito su [Parlant](https://github.com/parlant-project/parlant), è il "cervello" del sistema. Si occupa del *Context Engineering*, elabora il task dell'utente, genera un set di vincoli e li auto-valida in un *Micro-Loop*. Una volta pronti, rilascia un **Contratto JSON** formale sulla coda.
2. **🔗 The Reins (Orchestrazione)**: L'infrastruttura di routing guidata da **RabbitMQ**. Assicura l'isolamento dei nodi instradando i messaggi su code asincrone (es. `contract_queue`, `validation_queue`).
3. **🦾 The Arm (Il Braccio Esecutivo)**: Nodi Worker asincroni *headless* che consumano i Contratti JSON. Ricevuto l'ordine, usano la CLI di **OpenCode** (un AI Coding Assistant) in background per generare coercitivamente il codice seguendo i vincoli.
4. **🛡️ Product Revision (Quality Gate)**: Riceve il codice appena prodotto e lo valuta contro il contratto A2A-OCL. Se fallisce, crea un "Delta Errore" per innescare un ciclo di *Self-Refine*, altrimenti approva e rilascia.

---

## 🚀 Setup e Installazione

### Requisiti
- **Python 3.10+**
- **RabbitMQ** (Installabile in locale o tramite Docker)
- **OpenCode** CLI (installato globalmente via npm: `npm i -g opencode-ai`)
- Un provider LLM configurato nel `.env` (es. `OPENAI_API_KEY`)

### Installazione
1. Clona la repository:
   ```bash
   git clone https://github.com/tuo-username/SwarmDev.git
   cd SwarmDev
   ```
2. Crea un ambiente virtuale e installa le dipendenze:
   ```bash
   python -m venv .venv
   .\.venv\Scripts\activate  # Su Windows
   pip install -r requirements.txt
   ```
3. Rinomina `.env.example` in `.env` e inserisci le tue API Key.

---

## 🕹️ Come Eseguire il Sistema

Assicurati che il tuo server **RabbitMQ** sia in esecuzione (es. `docker run -d -p 5672:5672 rabbitmq`).

Poi, in **tre terminali separati**, avvia i microservizi:

1. **Avvia il Quality Gate:**
   ```bash
   python -m quality_gate.validator_service
   ```
2. **Avvia i Nodi Worker (Arm):**
   ```bash
   python -m arm.worker
   ```
3. **Avvia la Cognizione (Mind):**
   ```bash
   python -m mind.main
   ```

Una volta avviata la Mente, il server Parlant sarà raggiungibile su **[http://localhost:8800](http://localhost:8800)**. 
Scrivi al tuo agente indicando il task da svolgere: lui pianificherà, scriverà i vincoli in OCL e innescherà la reazione a catena nel sistema Event-Driven, generandoti il codice nella cartella `/workspace`.

---

## 🛠️ Modelli e Grammatica

Tutti i Contratti scambiati sul broker sono definiti in Pydantic all'interno di `core/models.py`. 
La sintassi vincolante (A2A-OCL) sfrutta la grammatica EBNF definita in `core/grammar/a2a_ocl.lark` per una validazione sintattica rigorosa prima dell'esecuzione.
