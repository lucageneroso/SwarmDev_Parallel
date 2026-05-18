# SwarmDev Parallel - Project Summary & Lab Setup Guide

## 1. Panoramica del Progetto
**SwarmDev Parallel** è un framework sperimentale per la **parallelizzazione agentica deterministica** basato su un'architettura Event-Driven. L'obiettivo primario è eliminare il "Chatter Smell" (le incomprensioni e i loop discorsivi in linguaggio naturale tra agenti AI) forzando una comunicazione basata esclusivamente su contratti JSON deterministici, validati tramite **A2A-OCL** (Agent-to-Agent Object Constraint Language). 

In questa recente evoluzione ("Wave 2"), il progetto si è dotato di un sistema di orchestrazione a grafo (tramite **LangGraph**) che permette l'esecuzione parallela di attori (es. Frontend e Backend in simultanea) inseriti in un rigido sistema di *Quality Gate* automatizzato (Actor-Critic).

---

## 2. Architettura e Distribuzione dei File

L'architettura è disaccoppiata e divisa in moduli specializzati che comunicano o tramite code asincrone (RabbitMQ) o tramite lo state-graph dell'orchestratore.

### Directory Principali
- **`core/`**: Contiene le fondamenta del sistema.
  - `models.py`: Modelli Pydantic che definiscono i Contratti JSON (la "lingua franca" degli agenti).
  - `grammar/a2a_ocl.lark`: La grammatica EBNF custom utilizzata per parsare e validare i vincoli matematici contrattuali.
- **`directives/`**: Contiene i file YAML (`execution_rules.yaml`, `reasoning_constraints.yaml`) utilizzati per iniettare regole comportamentali (Parlant Policy Directives) all'interno dei prompt di sistema degli agenti.
- **`quality_gate/`**: Il "severo giudice" del codice.
  - `validator_service.py`: Microservizio in ascolto su RabbitMQ che riceve il codice generato. Usa `repomix` via npx per creare uno snapshot XML ottimizzato per gli LLM dell'intero workspace, dopodiché avvia i tool di analisi statica reale (es. *radon* per complessità ciclomatica > 10, *flake8* per linting). Restituisce un feedback matematico e rigido.
  - `ocl_evaluator.py`: Script che valuta i vincoli A2A-OCL.
- **`arm/`**: L'esecutore "silenzioso" (Worker).
  - `worker.py`: Nodo che consuma i contratti JSON dal broker.
  - `opencode_wrapper.py`: Wrapper Python che invoca la CLI di `opencode` (AI Coding Assistant) iniettando i task in `stdin` con permessi bypassati in modo da non generare output discorsivo (Get-Shit-Done approach).
- **`workspace/`**: La directory (ignorata da git) dove viene materialmente salvato e raffinato il codice generato dalle iterazioni degli agenti.

### I File di Orchestrazione (La novità della Wave 2)
- **`graph_orchestrator.py`**: È il cuore parallelo del progetto. Crea un **DAG LangGraph** in ascolto su RabbitMQ. Appena riceve un contratto, splitta l'esecuzione su `frontend_actor` e `backend_actor` (usando LiteLLM in modo agnostico rispetto ai provider: OpenAI, Anthropic via OpenRouter, ecc.). Il codice poi passa ai critici (`frontend_critic` e `backend_critic`), i quali eseguono reali quality gates (ESLint, Black, Radon, Flake8). Se ci sono errori, l'orchestratore fa *routing condizionale* rimandando in loop *solo* l'attore che ha fallito (max 3 tentativi) passandogli esattamente l'errore del compilatore.
- **`run_wave2_orchestrator.py`**: Script dimostrativo usato per testare il sistema end-to-end. Crea un task reale (es. API per le prenotazioni di una birroteca) e lo spara sulla coda di RabbitMQ, innescando l'orchestratore.

---

## 3. Istruzioni Pratiche: Setup sulla Macchina di Laboratorio

Passaggi operativi per avviare il sistema.

### Step 1: Prerequisiti di Sistema
Assicurati che sulla macchina di laboratorio siano installati:
1. **Python 3.10+** (necessario per LangGraph e le sintassi moderne).
2. **Node.js & npm** (obbligatori perché il Quality Gate invoca tool come `npx repomix`, `npx eslint` e i worker usano `npx opencode`).
3. **Docker** (il metodo più rapido per istanziare RabbitMQ).

### Step 2: Avvio di RabbitMQ
Il sistema è Event-Driven, senza broker i pezzi non comunicano. Apri un terminale e avvia RabbitMQ:
```bash
docker run -d -p 5672:5672 -p 15672:15672 rabbitmq:3-management
```
*(Se non c'è Docker nel lab, devi installare e avviare RabbitMQ server localmente e assicurarti che giri in background).*

### Step 3: Inizializzazione Ambiente Python
Portati col terminale nella root della repo scaricata (`SwarmDev_Parallel`) e inizializza l'environment:
```powershell
# 1. Crea l'ambiente virtuale
python -m venv .venv

# 2. Attiva l'ambiente (sintassi per Windows PowerShell)
.\.venv\Scripts\activate

# 3. Installa le librerie richieste
pip install -r requirements.txt
```

### Step 4: Variabili d'Ambiente (.env)
1. Fai una copia del file `.env.example` e rinominala `.env`.
2. Aprili e compila i campi:
   - Inserisci la tua `OPENAI_API_KEY` (o configurazione per altri LLM).
   - Inserisci `LLM_MODEL=gpt-4o` (o il modello da te scelto per LiteLLM).
   - Assicurati che `RABBITMQ_HOST=localhost` e `RABBITMQ_PORT=5672`.

### Step 5: Test End-to-End
Sei pronto per mostrare la potenza del sistema. Il modo migliore per farlo è utilizzare il nuovo workflow parallelo (LangGraph).

**Terminale 1 (L'Orchestratore):**
Apri il terminale, attiva l'ambiente virtuale (`.\.venv\Scripts\activate`) ed esegui l'orchestratore:
```powershell
python graph_orchestrator.py
```
*Questo script si connetterà a RabbitMQ e aspetterà ordini. Quando gli ordini arriveranno, stamperà a schermo la diramazione parallela per il frontend e backend.*

**Terminale 2 (Il Trigger):**
Apri un secondo terminale, attiva l'ambiente virtuale, e simula l'invio del contratto della "Wave 2":
```powershell
python run_wave2_orchestrator.py
```
*Appena lancerai questo script, osserva il Terminale 1: vedrai l'architettura LangGraph entrare in azione, istanziare gli attori in parallelo, generare il codice, sottoporlo ai tool di Analisi Statica (Black, Flake8, ESLint) ed iterare eventuali correzioni.*

Tutto il codice validato con successo verrà poi depositato in una sottocartella all'interno della directory `/workspace`.
