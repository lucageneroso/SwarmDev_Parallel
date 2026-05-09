import os
import sys
import uuid

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(CURRENT_DIR)
if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)

from core.models import Contract
from mind.publisher import publisher_instance
from quality_gate.ocl_evaluator import A2AOCLValidator

GRAMMAR_PATH = os.path.join(PROJECT_ROOT, "core", "grammar", "a2a_ocl.lark")
validator = A2AOCLValidator(grammar_path=GRAMMAR_PATH)

def run_wave_2():
    # Definiamo i vincoli OCL
    constraints = [
        "context Prenotazione inv: self.numero_persone <= self.tavolo.numero_posti",
        "context Prenotazione inv: self.tavolo.prenotazioni->forAll(p | p.data_ora != self.data_ora or p.id = self.id)"
    ]

    # Validiamo preventivamente
    for expr in constraints:
        res = validator.validate_expression(expr)
        if not res["is_valid"]:
            print(f"ERRORE VALIDAZIONE OCL: {res['message']}")
            return

    contract_id = str(uuid.uuid4())
    contract = Contract(
        id=contract_id,
        context="Backend_Node_Express_SQLite",
        description=(
            "Genera il codice backend (Node.js/Express/SQLite) per gestire la Wave 2 del Gestionale BIRROTECA.\n"
            "Endpoints richiesti:\n"
            "- POST /prenotazioni (crea prenotazione con nome_cliente, numero_persone, data_ora, tavolo_id)\n"
            "- DELETE /prenotazioni/:id (cancella prenotazione esistente)\n"
            "- GET /prenotazioni/mie (lista prenotazioni)\n"
            "Database Schema (SQLite):\n"
            "- table 'tavoli' (id INTEGER PRIMARY KEY, numero_posti INTEGER)\n"
            "- table 'prenotazioni' (id INTEGER PRIMARY KEY, nome_cliente TEXT, numero_persone INTEGER, data_ora TEXT, tavolo_id INTEGER, stato TEXT DEFAULT 'attiva')\n"
            "Rispetta rigorosamente i vincoli A2A-OCL indicati: un tavolo non può essere prenotato 2 volte alla stessa ora e il numero persone deve essere <= numero posti del tavolo."
        ),
        a2a_ocl_constraints=constraints
    )

    try:
        publisher_instance.publish_contract(contract)
        print(f"[OK] Orchestrator: Contratto {contract_id} pubblicato con successo su RabbitMQ per la Wave 2.")
        
        # Aggiorna lo stato in STATE.md
        state_path = os.path.join(PROJECT_ROOT, "mind_workspace", "STATE.md")
        with open(state_path, "r", encoding="utf-8") as f:
            state_content = f.read()
        
        state_content = state_content.replace(
            "- **Wave 2: Gestione prenotazioni e cancellazioni** - IN ATTESA",
            "- **Wave 2: Gestione prenotazioni e cancellazioni** - IN CORSO (Contratto pubblicato)"
        )
        
        with open(state_path, "w", encoding="utf-8") as f:
            f.write(state_content)
        print("[OK] Orchestrator: STATE.md aggiornato.")
        
    except Exception as e:
        print(f"[ERROR] Orchestrator Errore: {str(e)}")

if __name__ == "__main__":
    run_wave_2()
