# SwarmDev Parallel

## 1. Contesto
**SwarmDev Parallel** è un framework sperimentale basato su un'architettura Event-Driven. L'esigenza nasce per risolvere il problema del "Chatter Smell", ovvero le incomprensioni, le allucinazioni e i loop discorsivi in linguaggio naturale che si verificano comunemente tra agenti AI durante lo sviluppo software. In questa "Wave 2", il progetto si è evoluto introducendo un sistema di orchestrazione a grafo (LangGraph) per gestire esecuzioni parallele (es. Frontend e Backend in simultanea), centralizzando il flusso e abbandonando la precedente infrastruttura basata su RabbitMQ.

## 2. Obiettivo
L'obiettivo primario è la **parallelizzazione agentica deterministica**. Forzando gli agenti a comunicare esclusivamente tramite contratti JSON rigidi e validati da vincoli matematici (tramite A2A-OCL - Agent-to-Agent Object Constraint Language), il sistema garantisce un output prevedibile e rigoroso. Gli attori vengono inseriti in un rigido sistema di Quality Gate automatizzato (approccio Actor-Critic) gestito direttamente dallo state-graph dell'orchestratore.

## 3. Tecnologie Utilizzate
- **LangGraph & LangChain**: Motore centrale per l'orchestrazione a grafo dei flussi di lavoro paralleli, routing condizionale e gestione degli stati (sostituisce la comunicazione asincrona tramite broker).
- **LiteLLM**: Per il routing flessibile verso diversi modelli e provider (OpenAI, Anthropic, Google Gemini, ecc.).
- **Lark (A2A-OCL)**: Per il parsing e la validazione della grammatica custom dei contratti.
- **Pydantic & SQLAlchemy**: Per la definizione formale e validazione dei payload JSON.
- **Node.js & Repomix**: Utilizzati dal Quality Gate per generare uno snapshot ottimizzato dell'intero workspace.
- **Black, Flake8, Radon, ESLint**: Strumenti di analisi statica reale utilizzati dai critici.

## 4. Repo di Riferimento
Questo repository (`SwarmDev_Parallel`) contiene l'architettura aggiornata e focalizzata interamente sul **Graph Orchestrator**.

## 5. Come Avviare il Tutto
Il sistema è ora centralizzato attorno allo script dell'orchestratore, eliminando la necessità di avviare Docker e molteplici microservizi separati.

### Prerequisiti
- **Python 3.10+**
- **Node.js & npm** (necessari per eseguire npx, repomix, eslint, opencode)

### Step 1: Setup dell'Ambiente Python
Apri il terminale nella root del progetto:
```powershell
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
```

### Step 2: Configurazione Variabili d'Ambiente (.env)
Crea o copia il file `.env.example` in `.env` e compila:
- `OPENAI_API_KEY` (o chiavi per altri LLM)
- `LLM_MODEL` (es. `gpt-4o`)

### Step 3: Esecuzione dell'Orchestratore
Per avviare il sistema e testare i flussi paralleli, è sufficiente eseguire lo script principale:
```powershell
python graph_orchestrator.py
```
*(Se utilizzi script di trigger specifici per testare flussi demo, assicurati di avviarli con l'ambiente attivato).*

## 6. Metodo
Il framework utilizza un approccio soprannominato **Get-Shit-Done (GSD)** coordinato da LangGraph:
- L'agente esecutivo (Worker/OpenCode) riceve prompt fortemente vincolati in XML ed esegue il task in un contesto isolato (fresh context), senza alcun permesso di produrre output discorsivo.
- Le esecuzioni di task complessi vengono splittate e gestite in parallelo direttamente dal grafo (es. nodo frontend e nodo backend).
- Il codice prodotto passa al **Quality Gate** (integrato come nodo del grafo) che sfrutta `repomix` per condensare la codebase in un file XML. In combinazione con i tool di analisi statica, il sistema produce un feedback matematico e oggettivo.
- Se si rilevano errori, l'orchestratore LangGraph attiva un *routing condizionale*: l'attore che ha fallito viene rimandato in loop di correzione (max 3 tentativi), ricevendo solo lo snapshot del codice fallato e l'errore nudo del compilatore, mantenendo snello il *context window* dell'LLM.
