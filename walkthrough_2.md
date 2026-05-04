# Walkthrough: Integrazione GSD & Repomix in SwarmDev

Questo documento spiega nel dettaglio *cosa* è stato fatto a livello di codice per raggiungere gli obiettivi dell'Aggiornamento 2, blindando l'automazione.

## 1. Modifica al Modello Dati (`core/models.py`)
> [!NOTE]
> Abbiamo aggiunto il campo `workspace_snapshot` (di tipo `Optional[str]`) al modello `ValidationResult`. 
Questo campo è vitale: serve a trasportare il dump XML dell'intero progetto generato dal Worker, spedendolo verso la `refine_queue` in modo strutturato e serializzabile.

## 2. Inibizione del "Chatter Smell" (`arm/opencode_wrapper.py`)
Il nostro obiettivo era rendere OpenCode un esecutore robotico passivo, emulando il framework "Get-Shit-Done" (GSD):
- **Cambiamento del Prompt**: Invece di usare template discorsivi, ora iniettiamo il JSON del Contratto all'interno di un template XML rigidissimo. L'LLM agisce come `<task type="auto">` e riceve l'ordine categorico di terminare in silenzio (`<done>`).
- **Nessuna Interattività**: L'esecuzione di OpenCode è forzata a operare in modo asincrono, silenziando i prompt dei permessi tramite `--dangerously-skip-permissions` e ricevendo l'input via `stdin`. Abbiamo inoltre rimosso i flag inesistenti che avrebbero bloccato la CLI.

## 3. Gestione del Path del Workspace (`arm/worker.py`)
> [!IMPORTANT]
> Affinché il Quality Gate possa eseguire Repomix nel posto giusto, deve sapere *dove* OpenCode ha generato i file.
Abbiamo alterato `generate_code` nel wrapper affinché restituisca anche la `job_dir` creata. In `worker.py`, questo percorso viene ora estratto e iniettato nel campo `file_path` dell'oggetto `CodeGenerationResult`.

## 4. Integrazione del Radar Repomix (`quality_gate/validator_service.py`)
Questa è la modifica che completa l'architettura difensiva:
- Quando il `validator_service` riceve il pacchetto dal Worker, legge la directory dal `file_path`.
- Se esiste, viene invocato un comando `subprocess`: `npx.cmd --yes repomix --style xml --token-count-encoding o200k_base`. 
- Il flag `--yes` in `npx` è l'eroe silenzioso: previene blocchi infiniti forzando l'installazione temporanea del pacchetto repomix, in totale assenza di intervento umano.
- Viene poi letto e parsato il file `repomix-output.xml`.
- Se il codice viola le policy (es. keyword vietate, sintassi OCL errata), la stringa XML completa di Repomix viene allegata in `workspace_snapshot` e pubblicata assieme all'errore sulla `refine_queue`.

## Conclusione
Il loop agentico è ora autonomo al 100%. L'agente Esecutivo è isolato cognitivamente dai suoi stessi output discorsivi, e il Quality Gate possiede una mappa completa della codebase da fornire all'agente di Self-Refine per fargli applicare una chirurgia del codice perfetta.
