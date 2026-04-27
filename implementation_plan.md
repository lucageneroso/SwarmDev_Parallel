# Evoluzione Architetturale SwarmDev: Paradigma della Carrozza

Questo documento descrive il piano per re-ingegnerizzare l'attuale base di codice monolitica di SwarmDev in un'architettura a microservizi Event-Driven, garantendo il disaccoppiamento totale e l'assenza di "Chatter Smell" tra agenti.

## User Review Required

> [!IMPORTANT]
> **Scelta del Message Broker (Le Redini)**
> Il piano prevede l'utilizzo di **RabbitMQ** (tramite la libreria Python `pika`) come Message Broker per garantire un instradamento asincrono, resiliente e totalmente isolato tra i nodi. RabbitMQ è lo standard de facto per architetture Event-Driven robuste.
> *Sei d'accordo con l'utilizzo di RabbitMQ, o preferisci Redis (tramite `redis-py`) o un'altra tecnologia per la gestione delle code?*

> [!IMPORTANT]
> **Definizione di OpenCode (Il Braccio)**
> Il "Braccio" (Worker OpenCode) dovrà agire in modalità headless. Nel contesto attuale, struttureremo il worker per simulare o eseguire le pipeline OpenCode (o l'esecuzione di script/comandi) basandosi unicamente sul JSON ricevuto dal broker. 
> *Hai già un eseguibile CLI o una libreria specifica per OpenCode che dobbiamo integrare, o andiamo a implementare un wrapper Python che invoca la generazione del codice tramite chiamate LLM headless separate?*

## Open Questions

> [!WARNING]
> **Deployment e Containerizzazione**
> Per garantire l'isolamento, idealmente ogni servizio (Mind, Arm, Quality Gate) dovrebbe girare nel proprio container o processo indipendente. In questa fase configureremo dei file di avvio Python (`start_mind.py`, `start_arm.py`, etc.) da lanciare separatamente, oltre a fornire un ipotetico `docker-compose.yml`. Va bene procedere in questo modo per la fase di sviluppo locale?

## Proposed Changes

La struttura del progetto sarà rimodellata per separare logicamente e fisicamente i servizi.

### Core (Condiviso)
Tutti i componenti accederanno a una libreria condivisa per i modelli dati (Contratti JSON) e la grammatica.
#### [NEW] [core/models.py](file:///c:/Users/lucag/SwarmDev_Parallel/core/models.py)
Creazione di modelli Pydantic per serializzare e validare rigidamente i Contratti JSON scambiati sul Message Broker.
#### [MODIFY] [core/grammar/a2a_ocl.lark](file:///c:/Users/lucag/SwarmDev_Parallel/core/grammar/a2a_ocl.lark)
Nessuna modifica strutturale, ma diventerà una risorsa letta dal Quality Gate e dalla Mind.

---

### The Mind (Cognizione)
Gestisce la cognizione tramite Parlant. Reagirà agli input, validerà l'A2A-OCL tramite tool locale e pubblicherà i contratti JSON validati sul broker.
#### [NEW] [mind/agent.py](file:///c:/Users/lucag/SwarmDev_Parallel/mind/agent.py)
Inizializza l'agente Parlant (SwarmDev Orchestrator).
#### [NEW] [mind/publisher.py](file:///c:/Users/lucag/SwarmDev_Parallel/mind/publisher.py)
Modulo che riceve l'output finale da Parlant e invia un evento `ContractCreated` sulla coda RabbitMQ per i worker.
#### [MODIFY] [main.py](file:///c:/Users/lucag/SwarmDev_Parallel/main.py) -> `mind/main.py`
Diventerà il punto d'ingresso esclusivo per il microservizio "Mind".

---

### The Reins (Orchestrazione Asincrona)
Infrastruttura di routing.
#### [NEW] [reins/broker.py](file:///c:/Users/lucag/SwarmDev_Parallel/reins/broker.py)
Classe wrapper per connessione e configurazione code RabbitMQ (`contract_queue`, `validation_queue`, `refine_queue`).

---

### The Arm (Braccio Esecutivo)
Nodi worker headless.
#### [NEW] [arm/worker.py](file:///c:/Users/lucag/SwarmDev_Parallel/arm/worker.py)
Ascolta la `contract_queue`. Quando riceve un Contratto JSON, esegue coercitivamente le istruzioni. Generato il codice (o simulata la generazione), pubblica un evento `CodeGenerated` (contenente il sorgente e il contratto) sulla `validation_queue`.

---

### Product Revision (Quality Gate)
Servizio terminale che verifica il codice prodotto contro i vincoli del contratto.
#### [NEW] [quality_gate/validator_service.py](file:///c:/Users/lucag/SwarmDev_Parallel/quality_gate/validator_service.py)
Ascolta la `validation_queue`. Verifica staticamente il codice. 
- Se passa: pubblica su `release_queue`.
- Se fallisce: calcola un "Delta Errore" e pubblica su `refine_queue` affinché un worker ripeta il task isolatamente.
#### [MODIFY] [orchestrator/validator_tool.py](file:///c:/Users/lucag/SwarmDev_Parallel/orchestrator/validator_tool.py) -> `quality_gate/ocl_evaluator.py`
Il tool A2AOCLValidator viene riposizionato e potenziato per valutare non solo la sintassi della grammatica, ma anche le metriche del codice prodotto.

## Verification Plan

### Manual Verification
1. **Setup Broker**: Avviare RabbitMQ in locale (es. via Docker `docker run -d --name rabbitmq -p 5672:5672 rabbitmq`).
2. **Avvio Servizi**: In terminali separati, avviare:
   - `python -m quality_gate.validator_service`
   - `python -m arm.worker`
   - `python -m mind.main`
3. **Simulazione Flusso**: Richiedere alla Mind di generare un contratto A2A-OCL semplice.
4. **Osservabilità**: Verificare i log nei rispettivi terminali (Nessuna conversazione testuale).
   - Mind pubblica il contratto in JSON.
   - Arm riceve il JSON e genera il codice in isolamento, poi pubblica il risultato.
   - Quality Gate analizza il codice, emette un Delta Errore o un success message asincrono.
