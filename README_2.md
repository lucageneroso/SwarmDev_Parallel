# SwarmDev Parallel - Event-Driven Architecture (Aggiornamento 2)

Benvenuti all'aggiornamento architetturale di **SwarmDev**. In questa fase abbiamo consolidato l'approccio *Event-Driven* eliminando le derive conversazionali degli agenti (Chatter Smell) e ottimizzando il meccanismo di validazione.

## 🌟 Novità di questa Versione

### 1. Esecutore Silenzioso (GSD Approach)
L'agente esecutivo (Braccio / OpenCode) non agisce più come un assistente "umano" prolisso. Abbiamo implementato l'approccio **Get-Shit-Done (GSD)**:
- Il prompt di istruzione è stato ingabbiato in un rigoroso schema **XML**.
- L'LLM opera in un *fresh context* isolato e deterministico, con l'esplicito divieto di produrre output discorsivo o interattivo.
- L'esecuzione bypassa ogni blocco interattivo tramite l'argomento `--dangerously-skip-permissions` e l'injection diretta via `stdin`.

### 2. Repomix come Radar del Quality Gate
Per permettere un *Self-Refine* efficace in caso di fallimento, il Quality Gate è stato potenziato con **Repomix**:
- Al termine della generazione, il Validator scansiona programmaticamente il nuovo workspace invocando `repomix` via `npx`.
- L'intera codebase generata viene condensata in un file XML ottimizzato per il conteggio token (`o200k_base`).
- In caso di violazione dei vincoli A2A-OCL, questo "Snapshot" viene allegato al payload di errore (`workspace_snapshot`) e inviato sulla `refine_queue`. L'agente incaricato del fix avrà così una fotografia precisa senza esplosione del context window.

## 🚀 Come Avviare il Sistema

Il sistema si compone di microservizi disaccoppiati in comunicazione asincrona tramite RabbitMQ.

### 1. Prerequisiti
Assicurati che **RabbitMQ** sia in esecuzione (es. tramite Docker locale):
```bash
docker run -d -p 5672:5672 -p 15672:15672 rabbitmq:3-management
```

### 2. Avvio dei Nodi (in terminali separati)
Apri il tuo terminale nella root del progetto (`c:\Users\lucag\SwarmDev_Parallel`) e attiva il tuo ambiente virtuale.

**Terminale 1 (Quality Gate):**
```powershell
python -m quality_gate.validator_service
```

**Terminale 2 (Worker/Braccio):**
```powershell
python -m arm.worker
```

### 3. Iniezione di un Contratto (Test)
Per testare il sistema end-to-end, puoi pubblicare un contratto di prova sulla coda eseguendo il file di test in un terzo terminale:
```powershell
python test_pipeline.py
```
*(Questo script inietterà un task formale, innescando l'intero ciclo di generazione e l'eventuale fallimento con validazione annessa).*
