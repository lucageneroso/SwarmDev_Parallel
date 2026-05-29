# GurdjDev
**Un framework Multi-Agente con architettura cognitiva e ragionamento Socratico.**

![SwarmDev Architecture](log2.png)

## Le 4 Feature Killer

### A) Il Paradigma "GurdjDev"
Ispirato alla celebre allegoria della carrozza di Gurdjieff, il framework introduce una separazione netta tra il decisore e l'esecutore:
- **La Mente (Il Cocchiere / Planner)**: L'orchestratore intelligente. Analizza i requisiti, pondera le decisioni architetturali e genera istruzioni formali.
- **La Carrozza (Gli Actor)**: I worker operativi confinati all'implementazione materiale (approccio *Get-Shit-Done*), totalmente ignari della logica globale e focalizzati unicamente sull'output del codice.
Questa rigida separazione elimina radicalmente il "Chatter Smell" (incomprensioni e loop discorsivi) tipico dei framework ad agenti generici.

### B) La "Swarm Mind"
Una Mente ad Alveare (Cognitive Architecture) che permette al framework di apprendere dagli errori e auto-migliorarsi iterativamente tramite una memoria strutturata su tre livelli:
- **Working Memory**: Lo stato attivo e volatile di esecuzione del grafo (LangGraph).
- **Episodic Buffer (SQLite)**: Il "Diario di Bordo" a breve termine che logga in tempo reale ogni singola azione, tentativo ed errore di sistema.
- **Semantic Memory (ChromaDB)**: Memoria vettoriale permanente in cui il sistema deposita l'esperienza distillata. Rinforza autonomamente i ricordi che permettono di risolvere fix veloci (LTP - Long-Term Potentiation) e sfuma nel dimenticatoio i dati obsoleti (LTD - Long-Term Depression).

### C) Socratic Planning (Ask, Then Think)
Implementazione nativa del paradigma di ragionamento socratico per azzerare le allucinazioni architetturali. Prima di impartire le direttive formali, il planner entra in una fase Socratic Reasoning: si pone internamente domande critiche sulle zone d'ombra dei requisiti, chiarisce le ambiguità, esplora i casi limite e valida mentalmente i vincoli. Solo dopo questa analisi rilascia l'output finale, garantendo robustezza e successo al primo tentativo (*pass_at_1*).

### D) Contratti JSON Matematici (A2A-OCL)
Bando alle ambiguità del linguaggio naturale inter-agente. Gli attori di GurdjDev comunicano esclusivamente tramite payload JSON validati in modo strettamente matematico. Le regole di vincolo seguono uno standard proprietario basato su **A2A-OCL** (Agent-to-Agent Object Constraint Language), garantendo che l'input ricevuto dai worker (Carrozza) sia formalmente infallibile.

---

## Tecnologie Principali
- **LangGraph & LangChain**: Motore centrale per l'orchestrazione a grafo dei flussi di lavoro paralleli, routing condizionale e state management.
- **LiteLLM**: Routing flessibile verso molteplici provider LLM (OpenAI, Anthropic, Google Gemini, ecc.).
- **Lark (A2A-OCL)**: Parsing e validazione della grammatica custom dei contratti di interscambio.
- **Pydantic & SQLAlchemy**: Definizione formale, serializzazione e validazione dei payload.
- **Node.js & Repomix**: Utilizzati dal Quality Gate per generare uno *snapshot* XML ottimizzato dell'intero workspace, permettendo al modello di comprendere l'intera codebase minimizzando l'uso dei token.
- **Container & Analisi Statica (Docker, SeaClip, Sonar)**: 
  - **Docker**: Gestione isolata dei microservizi ancillari.
  - **SeaClip**: Server locale per l'indicizzazione semantica e recupero contestuale avanzato.
  - **Sonar (SonarQube) / Black / Flake8 / ESLint**: Pipeline rigorosa di code analysis integrata direttamente come *critic node* nel grafo.

---

## Come Avviare il Sistema

### Prerequisiti
- **Python 3.10+**
- **Node.js & npm** (indispensabili per eseguire npx, repomix, eslint, opencode)
- **Docker** (per avviare i servizi di infrastruttura come ChromaDB, Sonar e SeaClip)

### Setup Iniziale
1. **Avvio Servizi Infrastrutturali (Docker)**:
   Per abilitare il database vettoriale e le pipe di controllo, esegui il docker compose:
   ```bash
   docker-compose up -d
   ```

2. **Inizializzazione Ambiente Python**:
   ```bash
   python -m venv .venv
   .\.venv\Scripts\activate
   pip install -r requirements.txt
   ```

3. **Configurazione Variabili d'Ambiente (`.env`)**:
   Crea una copia del file `.env.example`, rinominalo in `.env` e compila le variabili principali:
   - `OPENAI_API_KEY` (o chiavi per altri LLM)
   - `LLM_MODEL` (es. `gpt-4o`)

### Esecuzione Ordinaria
Avvia l'engine di LangGraph per processare task paralleli in modalità deterministica:
```bash
python graph_orchestrator.py
```

### Ispezione della "Swarm Mind" via CLI
L'architettura cognitiva (sia episodica a breve termine, sia semantica a lungo termine) è liberamente esplorabile dal terminale:
```bash
# Ispeziona il Diario di Bordo attivo (Episodic Buffer Short-Term)
python swarm_mind/cli.py short-term --active

# Visualizza i top 10 "Ricordi Consolidati" (Semantic Memory Long-Term)
python swarm_mind/cli.py long-term-list --limit 10

# Usa il database vettoriale per ricercare passate soluzioni
python swarm_mind/cli.py long-term-query "React error ESLint"
```
