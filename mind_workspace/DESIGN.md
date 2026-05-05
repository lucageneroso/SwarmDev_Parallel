# DESIGN.md - Gestionale Biblioteca

## Scope e Funzionalità Principali
- Gestione prestiti
- Catalogazione libri
- Gestione utenti
- Prenotazioni
- Reportistica

## Data Model
### Libro
- titolo
- autore
- ISBN
- anno
- genere
- stato (disponibile, in prestito, prenotato)

### Utente
- nome
- email
- tessera
- storico prestiti

### Prestito
- utente
- libro
- data inizio
- data scadenza (1 mese)
- stato (attivo, restituito, in ritardo)

### Prenotazione
- utente
- libro
- data richiesta
- stato (attiva, scaduta, completata)

## Flusso Prestito
1. L’utente richiede un prestito tramite app.
2. Il sistema verifica che l’utente abbia meno di 3 prestiti attivi.
3. Se ok, la richiesta viene inviata in dashboard al bibliotecario per approvazione.
4. Se l’utente supera il limite, la richiesta non viene approvata.
5. Se un libro non viene restituito entro 1 mese, viene inviata una notifica automatica all’utente.

## Prenotazioni
- L’utente può prenotare un libro disponibile o attualmente in prestito.
- Nessuna scadenza automatica per la prenotazione se il libro non viene ritirato.

## Notifiche
- Notifica automatica all’utente in caso di ritardo restituzione.
- Notifica automatica al bibliotecario per nuove richieste di prestito.

## Disponibilità Libri
- Gli utenti possono vedere in tempo reale la disponibilità dei libri.

## Reportistica (Esempi)
- Libri più richiesti
- Utenti più attivi
- Prestiti in scadenza
- Libri attualmente in prestito

## Edge Cases
- Richiesta di prestito oltre il limite: rifiutata automaticamente.
- Prestito non restituito entro la scadenza: notifica automatica.
- Nessun dato aggiuntivo tracciato per gli utenti oltre quelli specificati.
- Prenotazioni senza scadenza automatica.

## Processo di Approvazione
- Tutte le richieste di prestito devono essere approvate dal bibliotecario tramite dashboard.
