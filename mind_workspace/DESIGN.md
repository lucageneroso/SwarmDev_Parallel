# DESIGN.md - Gestionale Prenotazioni BIRROTECA

## Scopo
Sistema per la gestione delle prenotazioni tavoli alla BIRROTECA, con cancellazione autonoma e visualizzazione disponibilità in tempo reale.

## Modello Dati
- **Tavolo**
  - `id`: string/int (identificativo univoco)
  - `numero_posti`: int (numero massimo persone per tavolo)

- **Prenotazione**
  - `id`: string/int (identificativo univoco)
  - `nome_cliente`: string
  - `numero_persone`: int
  - `data_ora`: datetime (data e ora prenotazione)
  - `tavolo_id`: riferimento a Tavolo
  - `stato`: enum ["attiva", "cancellata"]

## Flusso Prenotazione
1. L'utente accede all'app e seleziona una fascia oraria.
2. Il sistema mostra i tavoli disponibili per quella fascia (nessuna doppia prenotazione sullo stesso tavolo e orario).
3. L'utente seleziona tavolo, inserisce nome e numero persone, conferma la prenotazione.
4. L'utente può cancellare autonomamente la prenotazione in qualsiasi momento.
5. Alla cancellazione, il tavolo torna immediatamente disponibile per la stessa fascia oraria.
6. Non è prevista la modifica delle prenotazioni: per cambiare dati occorre cancellare e rifare la prenotazione.
7. Nessuna notifica automatica (email, push, ecc.).

## API Principali
- **GET /tavoli/disponibili?data_ora=...**
  - Restituisce lista tavoli disponibili per data/ora specificata.
- **POST /prenotazioni**
  - Crea una nuova prenotazione (richiede nome_cliente, numero_persone, data_ora, tavolo_id).
- **DELETE /prenotazioni/{id}**
  - Cancella una prenotazione (solo se effettuata dall'utente stesso).
- **GET /prenotazioni/mie**
  - Restituisce le prenotazioni dell'utente.

## Edge Cases
- Prenotazione su tavolo già occupato nella stessa fascia oraria: rifiutata.
- Cancellazione: nessun limite temporale, il tavolo torna subito disponibile.
- Nessuna modifica prenotazione: solo cancellazione e nuova creazione.

## Vincoli
- Un tavolo non può avere più di una prenotazione attiva per la stessa data/ora.
- Numero persone per prenotazione ≤ numero_posti del tavolo.
- Solo l'utente che ha creato la prenotazione può cancellarla.

## Non Previsto
- Notifiche automatiche (email, push, ecc.).
- Politiche di cancellazione restrittive.
- Gestione di modifiche alle prenotazioni.
