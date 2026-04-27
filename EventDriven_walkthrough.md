# Walkthrough: Architettura Event-Driven SwarmDev

Ho completato la re-ingegnerizzazione di SwarmDev implementando il "Paradigma della Carrozza". Ora l'intero sistema è disaccoppiato in quattro cluster di microservizi guidati dagli eventi.

> [!NOTE]
> Il flusso di comunicazione orizzontale è stato interrotto a favore di uno scambio asincrono di Contratti JSON e artefatti di codice tramite code RabbitMQ. Nessun "Chatter Smell" è possibile.

## Cosa è Cambiato

### 1. La Mente (Cognizione)
- `main.py` è stato spostato in [mind/main.py](file:///c:/Users/lucag/SwarmDev_Parallel/mind/main.py).
- Il toolset Parlant è stato esteso con `publish_final_contract` (in [parlant_context/parlant_tools.py](file:///c:/Users/lucag/SwarmDev_Parallel/parlant_context/parlant_tools.py)), che l'agente deve invocare come ultimo step dopo aver validato tutti i constraint A2A-OCL.
- È stato creato un [mind/publisher.py](file:///c:/Users/lucag/SwarmDev_Parallel/mind/publisher.py) che gestisce l'invio fisico dei Contratti Pydantic alla coda del broker.

### 2. Le Redini (Message Broker)
- Abbiamo inserito `pika` come client e strutturato le code (Contract, Validation, Refine, Release) all'interno di [reins/broker.py](file:///c:/Users/lucag/SwarmDev_Parallel/reins/broker.py).
- Una singola istanza Broker è condivisa da tutti i microservizi per standardizzare QoS e connessione.

### 3. Il Braccio (Esecuzione Parallela)
- È nato il servizio daemon [arm/worker.py](file:///c:/Users/lucag/SwarmDev_Parallel/arm/worker.py) in costante ascolto sulla `contract_queue`.
- **Integrazione OpenCode**: È stato scritto un wrapper intelligente ([arm/opencode_wrapper.py](file:///c:/Users/lucag/SwarmDev_Parallel/arm/opencode_wrapper.py)) che formatta coercitivamente un prompt in base ai vincoli OCL e prova ad invocare asincronamente tramite terminale `npx opencode` in background (`subprocess`). Se `opencode` non dovesse funzionare subito, ho inserito una logica di fallback mock per permetterti di non bloccare i test.
- Una volta terminata la generazione del codice, l'Arm non risponde alla Mind, ma rilascia l'artefatto nella `validation_queue`.

### 4. Quality Gate (Product Revision)
- Il validatore di grammatica è stato elevato a servizio vero e proprio in [quality_gate/validator_service.py](file:///c:/Users/lucag/SwarmDev_Parallel/quality_gate/validator_service.py).
- Resta in ascolto sulla `validation_queue`. Controlla staticamente il codice. In caso di errore crea un "Delta Errore" che instrada sulla `refine_queue`, altrimenti approva sulla `release_queue`.

> [!TIP]
> **Come Testare Localmente l'Infrastruttura:**
> Assicurati di avere RabbitMQ in esecuzione (puoi avviarlo semplicemente con `docker run -d --name rabbitmq -p 5672:5672 rabbitmq`).
> Quindi, in tre terminali separati avvia:
> 1. `python -m quality_gate.validator_service`
> 2. `python -m arm.worker`
> 3. `python -m mind.main`
>
> A quel punto, manda una richiesta HTTP all'agente Parlant per generare l'app. Vedrai i servizi operare isolatamente osservando solo i loro log sul terminale.
