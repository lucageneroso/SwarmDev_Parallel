# ROADMAP

## Onda 1: Modellazione delle Entità e Vincoli Base
- Definizione delle entità principali: Sala, Spettacolo, Biglietto, Utente
- Implementazione dei vincoli fondamentali:
  - Capienza sala come limite massimo biglietti
  - Ogni spettacolo associato a una sola sala e data/ora
  - Biglietto venduto una sola volta per spettacolo/posto
  - Utente identificato solo tramite id

## Onda 2: API e Logica di Gestione
- Progettazione delle API per:
  - Creazione e gestione di sale, spettacoli, biglietti, utenti
  - Acquisto biglietti con controllo capienza e unicità
- Validazione dei vincoli tramite espressioni A2A-OCL

## Onda 3: Edge Cases e Test
- Gestione casi limite (anche se non segnalati, verifica robustezza)
- Test di validazione automatica (Micro-Loop)
- Preparazione del Contratto JSON finale