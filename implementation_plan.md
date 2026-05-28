# Integrazione Nodo Mind in LangGraph Orchestrator

Questo documento descrive il piano architetturale per dismettere Parlant e integrare le responsabilità del nodo **Mind** (Requirements Elicitation, Planning, Contract Generation e OCL Validation) direttamente all'interno di `graph_orchestrator.py`.

## Obiettivo
Trasformare l'attuale workflow LangGraph (che si occupava solo della fase di Execution/Worker) in un grafo "End-to-End". Il nuovo grafo partirà da una richiesta utente testuale, eseguirà un ciclo maieutico per raccogliere i requisiti (Discovery), genererà l'architettura e i vincoli OCL, li validerà tramite un Micro-Loop interno, e infine scatenerà i Worker in parallelo.

> [!IMPORTANT]
> **User Review Required**
> Poiché LangGraph per default non offre un'interfaccia web (come faceva Parlant), la fase di *Discovery* dovrà avvenire tramite riga di comando (CLI). Il grafo si fermerà chiedendo input tramite terminale (`input()`) finché i requisiti non saranno chiari. È un compromesso accettabile?

## Open Questions
- **Gestione RabbitMQ**: Attualmente `graph_orchestrator.py` entrava in azione ascoltando `contract_queue`. Se inglobiamo la Mind nel grafo, possiamo far partire il grafo *direttamente* da terminale senza passare per RabbitMQ (generando i contratti in memoria e passandoli ai Worker successivi), oppure vuoi che il nodo Mind dentro LangGraph pubblichi comunque il contratto su RabbitMQ e poi si fermi, lasciando che un secondo script lo consumi? Consiglio di unire tutto in un singolo grafo per avere uno State condiviso e un terminale unico.
- **Prompt SUPERPOWERS**: Vuoi che io scriva un system prompt estremamente forte ("SUPERPOWERS") da iniettare nel nodo Discovery per guidare l'LLM nell'estrazione chirurgica dei requisiti senza divagare? O hai già un prompt che vuoi fornirmi?

## 🧠 Swarm Mind — Piano di Implementazione (v2.3 — Fase 3)

## Decisioni dell'Utente (Consolidate)

| Domanda | Decisione |
|---------|-----------|
| Persistenza Strato B | **Cold Storage** — Archivio SQLite separato dopo consolidamento. Log crudi conservati per futuro fine-tuning. |
| Neo4j | **No, per ora.** ChromaDB + CodeGraph. |
| Trigger Consolidamento | **Nodo LangGraph** alla fine del grafo (auto-contenuto, atomico). |
| Priorità Fasi | **Fase 0→1→2→3→4** (ordine proposto). |
| Modularizzazione | **Obbligatoria come Fase 0.** Prerequisito architetturale. |

---

## Fase 0 — Modularizzazione di `graph_orchestrator.py` (COMPLETATA)
La modularizzazione è stata eseguita con successo. Il grafo viene compilato correttamente ed è stato verificato con successo.

---

## Fase 1 — Fondamenta (Strato B + evoluzione Strato C)

### Schema DB SQLite (Short-Term Memory / Diario di Bordo)
Verranno creati due database SQLite sotto `workspace/memory/`:
1. `episodic_active.db`: Contiene i log crudi delle transazioni del run corrente dello swarm.
2. `episodic_archive.db`: Contiene l'archivio storico cold storage di tutti i run completati.

**Tabella `episodes` (in entrambi i DB):**
- `id` (INTEGER PRIMARY KEY AUTOINCREMENT)
- `task_id` (TEXT NOT NULL) — Identificativo unico del run generato all'avvio.
- `timestamp` (TEXT NOT NULL) — ISO8601 UTC.
- `node_name` (TEXT NOT NULL) — Nome del nodo che ha generato il log.
- `input_data` (TEXT) — JSON stringificata (input del nodo).
- `output_data` (TEXT) — JSON stringificata (output del nodo o codice generato).
- `errors` (TEXT) — Eventuali errori di compilazione, lint o runtime associati.
- `metadata` (TEXT) — JSON stringificata (es. modello LLM, token consumati, esito).

### Progettazione del Package `swarm_mind/`

#### [NEW] [__init__.py](file:///c:/Users/lucag/SwarmDev_Parallel/swarm_mind/__init__.py)
Inizializzazione del package `swarm_mind`.

#### [NEW] [episodic_buffer.py](file:///c:/Users/lucag/SwarmDev_Parallel/swarm_mind/episodic_buffer.py)
Classe `EpisodicBuffer` per gestire le letture e scritture sui database SQLite.
```python
class EpisodicBuffer:
    def __init__(self, active_db_path: str = None, archive_db_path: str = None):
        # Inizializza i path di default sotto workspace/memory/ e crea le cartelle
        ...
    def record(self, task_id: str, node_name: str, input_data: dict, output_data: dict, errors: str = None, metadata: dict = None) -> int:
        # Inserisce un record nel database attivo
        ...
    def get_active_episodes(self, task_id: str = None) -> list[dict]:
        # Ritorna la lista delle transazioni attive per il task corrente
        ...
    def archive_and_clear(self, task_id: str):
        # Transferisce i dati da active_db_path a archive_db_path per il task specificato e cancella dall'attivo
        ...
```

### Modifiche allo Stato del Grafo e ai Nodi

#### [MODIFY] [state.py](file:///c:/Users/lucag/SwarmDev_Parallel/graph/state.py)
Aggiunta del campo `task_id` all' `OrchestratorState` per consentire ai nodi di taggare correttamente gli episodi.
```python
class OrchestratorState(TypedDict):
    task_id: str
    ...
```

#### [MODIFY] [graph_orchestrator.py](file:///c:/Users/lucag/SwarmDev_Parallel/graph_orchestrator.py)
Generazione del `task_id` (UUID o timestamp) all'interno di `start_interactive_session()` ed inserimento nell' `initial_state`.

#### [MODIFY] Strumentazione dei Nodi (`graph/nodes/*.py`)
Ogni nodo registrerà il proprio stato finale invocando `EpisodicBuffer().record(...)` prima di fare return.
1. `discovery_node` / `planning_node`: input dell'utente e design doc generato.
2. `frontend_actor` / `backend_actor`: codici sorgenti generati e contratti.
3. `frontend_critic` / `backend_critic`: lint errors ed esiti.
4. `test_writer_actor` / `test_evaluator_node`: test generati ed esito dei test.
5. `quality_evaluation_node` / `runtime_execution_node`: feedback del quality gate e PM2 runtime logs.

### Evoluzione ChromaDB (Strato C)
Aggiornamento delle utility in [aci.py](file:///c:/Users/lucag/SwarmDev_Parallel/graph/aci.py) per supportare metadati più dettagliati. Nelle prossime fasi il consolidamento estrarrà informazioni dagli SQLite e le caricherà su ChromaDB strutturando l'episodio.

---

## Fase 2 — Consolidamento + Oblio (Mente ad Alveare)

### Il Nodo di Consolidamento (`consolidation_node`)
Aggiungeremo un nuovo nodo LangGraph [consolidation.py](file:///c:/Users/lucag/SwarmDev_Parallel/graph/nodes/consolidation.py) che verrà eseguito alla fine del grafo (intercettando la transizione prima del traguardo `END`).

**Algoritmo di Consolidamento:**
1. Recupera tutti i log del run corrente da `episodic_active.db` tramite `EpisodicBuffer().get_active_episodes(task_id)`.
2. Se non ci sono episodi o se il run è fallito prima di produrre codice, esce.
3. Se ci sono episodi significativi (es. errori di linting corretti negli attori, o crash risolti nel runtime), formatta la sequenza temporale delle transazioni ed interroga il `mind_llm` con un prompt di sintesi cognitiva.
4. L'LLM produce un report semantico "Errore -> Soluzione" (es. "Errore PM2 causato da PYTHONPATH errato -> Risolto impostando PYTHONPATH a livello OS").
5. Salva questa coppia semantica in ChromaDB (Strato C - Long-Term Memory) richiamando `_chromadb_add_fix()`.
6. Chiama `EpisodicBuffer().archive_and_clear(task_id)` per archiviare a freddo tutti i log grezzi nel database storico di archivio e ripulire il database attivo.

### Logica di Oblio (Memory Decay)
Nelle memorie biologiche, i ricordi meno rilevanti decadono nel tempo. Per simulare questo fenomeno, implementeremo un meccanismo di **Decadimento Temporale** durante la query di ChromaDB:
- In [aci.py](file:///c:/Users/lucag/SwarmDev_Parallel/graph/aci.py), la funzione `_chromadb_query` includerà il calcolo di un coefficiente di rilevanza temporale (usando il timestamp memorizzato nei metadati del documento).
- Se una memoria ha un'età superiore a una soglia configurabile (es. 30 giorni) e un punteggio di similarità non eccezionale, verrà ignorata o "dimenticata" dallo swarm per evitare interferenze da soluzioni obsolete.

---

## Fase 3 — Pattern Completion + Metamemoria

### Il Nodo Familiarità (`familiarity_check_node`)
Inseriremo un nuovo nodo LangGraph [familiarity.py](file:///c:/Users/lucag/SwarmDev_Parallel/graph/nodes/familiarity.py) posizionato subito dopo `discovery_node` e prima di `planning_node`.

**Funzionamento:**
1. Quando l'LLM approva il design doc, lo swarm interroga semantizzazione di ChromaDB passando il design e i requisiti estratti.
2. Cerca match ad alta confidenza (distanza < 0.5):
   - Se trova una memoria consimile ad alta confidenza: la carica come `design_rag_context` nello Stato.
   - Il `planning_node` userà questa memoria per non replicare errori architetturali passati fin dal primo codice generato (Pattern Completion).

### Metamemoria ed LTP/LTD (Potenziamento/Depressione a Lungo Termine)
Per simulare il rinforzo sinaptico biologico:
- In `_chromadb_add_fix` ed in `consolidation_node`, terremo traccia dell'efficacia delle soluzioni memorizzate.
- Se lo swarm risolve il compito con successo al primo tentativo dopo aver iniettato una memoria RAG, applichiamo **LTP (Long-Term Potentiation)**: ringiovaniamo il timestamp nei metadati di quella specifica memoria (impostandolo alla data odierna) ed incrementiamo `uses_count` (rinforzo).
- Se lo swarm fallisce o deve fare più retry per via dello stesso errore, applichiamo **LTD (Long-Term Depression)**: penalizziamo quella memoria incrementando artificialmente la sua `distance` nelle ricerche successive o impostando `failures_count` nei metadati per disabilitarla se i fallimenti superano una soglia.

---

## Fase 4 — Mining Storico + Polish (Invariata)
- Bootstrap dai 52+ progetti in `workspace/`
- SOP per consolidamento
- CLI di ispezione

---

## Verification Plan

### Verification Plan (Fase 1 e 2 - COMPLETATI)
- Unit test in `tests/test_swarm_mind.py` e `tests/test_consolidation.py` eseguiti con successo.
- Moduli integrati ed assemblati in LangGraph con successo.

### Verification Plan (Fase 3)
1. **Unit Test per Metamemoria (LTP/LTD)**:
   - Scrittura di `tests/test_metamemory.py` per validare che l'LTP aggiorni la data del fix ed il contatore di utilizzi, e che l'LTD decrementi la priorità del fix o lo marchi come deprecato in base ai metadati.
2. **Integrazione del Grafo**:
   - Iniezione manuale di una memoria difettosa ed una memoria valida in un ChromaDB mockato/reale e verifica che lo swarm selezioni la corretta memoria ed applichi il feedback loop a fine DAG.

---

## Aggiornamento Sito Documentale (`docs/`)

Per illustrare chiaramente la "Mente ad Alveare" aggiungeremo una nuova sezione dedicata in `docs/index.html` e `docs/style.css`.

### Contenuto della Sezione
- **Implementazione e Architettura**: Spiegazione dettagliata dei tre strati cognitivi (Sensory/Working Memory, Episodic Buffer, Long-Term Semantic Memory).
- **Test e Interazione CLI**: Guida rapida su come interrogare la memoria tramite `cli.py` (es. `long-term-list`, `short-term`).
- **Meccanica LTP/LTD**: Come i ricordi vengono potenziati (LTP) o dimenticati (LTD) in base all'uso e agli errori ripetuti.

### L'Animazione (CSS/SVG)
Creeremo un'animazione a 3 livelli ("Memory Strata") fluida e d'impatto:
1. **Livello 1 (Top) - Working Memory (Context Window)**: Un'area dinamica in cui nodi effimeri (token/messaggi) lampeggiano velocemente. Rappresenta lo stato del grafo in tempo reale.
2. **Livello 2 (Middle) - Episodic Buffer (SQLite)**: "Gocce" di dati scendono dal Livello 1 e si impilano ordinatamente come log strutturati. Rappresenta il Diario di Bordo.
3. **Livello 3 (Bottom) - Semantic Memory (ChromaDB)**: Un "Consolidatore" raccoglie ciclicamente i blocchi dal Livello 2 e li converte in "Vettori" (simboli geometrici incandescenti) che si posizionano in uno spazio vettoriale profondo 3D (resa tramite isometrica CSS o layer sovrapposti).

> [!IMPORTANT]
> **User Review Required**
> Sei d'accordo con l'impostazione visiva a tre livelli per l'animazione della Memoria? Se approvi, procedo immediatamente con la scrittura del codice HTML e CSS per il sito!
