import os
import sys
import uuid
import json
from dataclasses import asdict

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(CURRENT_DIR)
if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)

from core.models import Contract, CodeGenerationResult
from arm.opencode_wrapper import OpenCodeWrapper
from quality_gate.validator_service import QualityGateService

def run_pipeline():
    print("[START] Inizio esecuzione Wave 2 (Bypass Broker)")
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
            "Rispetta rigorosamente i vincoli A2A-OCL indicati."
        ),
        a2a_ocl_constraints=[
            "context Prenotazione inv: self.numero_persone <= self.tavolo.numero_posti",
            "context Prenotazione inv: self.tavolo.prenotazioni->forAll(p | p.data_ora != self.data_ora or p.id = self.id)"
        ]
    )
    
    print(f"[INFO] Contratto Generato: {contract_id}")
    
    # Init Worker
    print("[WORKER] Esecuzione OpenCode Worker...")
    wrapper = OpenCodeWrapper(output_dir=os.path.join(PROJECT_ROOT, "workspace"))
    try:
        generated_files, job_dir = wrapper.generate_code(
            context=contract.context,
            contract_id=contract.id,
            contract_json=contract.model_dump_json()
        )
        print(f"[OK] OpenCode ha completato in: {job_dir}")
        
        result = CodeGenerationResult(
            contract_id=contract.id,
            files=generated_files,
            generated_code=None,
            file_path=job_dir
        )
        
        # Init Quality Gate
        print("[QUALITY_GATE] Esecuzione Quality Gate...")
        qg = QualityGateService()
        # Mocking broker publish for QG to just print result
        def mock_publish(queue_name, data):
            print(f"[Mock Broker] Pubblicato su '{queue_name}'")
            if queue_name == 'refine_queue':
                print("[ERROR] Il codice ha fallito i controlli. Refine richiesto.")
            elif queue_name == 'release_queue':
                print("[OK] Il codice ha passato i controlli. Release pronta.")
        
        qg.broker.publish = mock_publish
        
        qg.evaluate_code(result.model_dump())
        
    except Exception as e:
        print(f"[ERROR] Errore durante l'esecuzione del worker: {e}")

if __name__ == "__main__":
    run_pipeline()
