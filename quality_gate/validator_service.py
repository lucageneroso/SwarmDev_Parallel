# quality_gate/validator_service.py
import sys
import os
import subprocess
import re

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)

from reins.broker import RabbitMQBroker
from core.models import CodeGenerationResult, ValidationResult
from quality_gate.ocl_evaluator import A2AOCLValidator

class QualityGateService:
    def __init__(self):
        self.broker = RabbitMQBroker()
        
        # Riposizionamento ocl_evaluator
        grammar_path = os.path.join(PROJECT_ROOT, "core", "grammar", "a2a_ocl.lark")
        self.ocl_validator = A2AOCLValidator(grammar_path=grammar_path)

    def start(self):
        print("[Quality Gate] Servizio inizializzato. In ascolto per Product Revision...")
        self.broker.consume('validation_queue', self.evaluate_code)

    def _run_static_analysis(self, target_dir: str) -> tuple[bool, str]:
        """Esegue analisi statica reale (radon, flake8) e ritorna il delta errore matematico."""
        error_deltas = []
        is_valid = True

        # 1. Cyclomatic Complexity (radon)
        try:
            # radon cc -s (mostra complessità superiore a 10)
            cmd = [sys.executable, "-m", "radon", "cc", "-n", "B", "-s", target_dir] # -n B filters for grade B and worse (>5)
            # Per essere "unforgiving", mettiamo la soglia a 10 (Grade C o peggio)
            # Ma usiamo -n C per beccare > 10.
            cmd = [sys.executable, "-m", "radon", "cc", "-n", "C", "-s", target_dir]
            
            result = subprocess.run(cmd, capture_output=True, text=True, check=False)
            if result.stdout.strip():
                is_valid = False
                # Esempio output radon: "main.py:10:0: C 12"
                # Puliamo l'output per renderlo un delta matematico
                lines = [l.strip() for l in result.stdout.split('\n') if l.strip()]
                for line in lines:
                    error_deltas.append(f"Q1 Failed: Cyclomatic Complexity Violation. {line}")
        except Exception as e:
            print(f"[WARN] Errore esecuzione radon: {e}")

        # 2. Linting (flake8)
        try:
            cmd = [sys.executable, "-m", "flake8", "--max-complexity=10", "--ignore=E501,E302,W605", target_dir]
            result = subprocess.run(cmd, capture_output=True, text=True, check=False)
            if result.stdout.strip():
                is_valid = False
                lines = [l.strip() for l in result.stdout.split('\n') if l.strip()]
                for line in lines[:5]: # Limitiamo i primi 5 errori per non esplodere il context
                    error_deltas.append(f"Q2 Failed: Linting Error. {line}")
        except Exception as e:
            print(f"[WARN] Errore esecuzione flake8: {e}")

        return is_valid, "\n".join(error_deltas)

    def evaluate_code(self, message_data: dict):
        try:
            result_data = CodeGenerationResult(**message_data)
            print(f"[Quality Gate] Valutazione codice generato per contratto: {result_data.contract_id}")

            # -----------------------------
            # 1. Esecuzione Repomix (Snapshot)
            # -----------------------------
            workspace_snapshot = None
            if result_data.file_path and os.path.exists(result_data.file_path):
                print(f"[Quality Gate] Esecuzione Repomix in {result_data.file_path}...")
                try:
                    cmd = ["npx.cmd", "--yes", "repomix", "--style", "xml", "--token-count-encoding", "o200k_base"]
                    subprocess.run(cmd, cwd=result_data.file_path, capture_output=True, text=True, check=False)
                    
                    repomix_out = os.path.join(result_data.file_path, "repomix-output.xml")
                    if os.path.exists(repomix_out):
                        with open(repomix_out, "r", encoding="utf-8") as f:
                            workspace_snapshot = f.read()
                        print(f"[Quality Gate] Repomix ha generato con successo lo snapshot XML.")
                except Exception as e:
                    print(f"[Quality Gate] Errore esecuzione repomix: {e}")

            # -----------------------------
            # 2. Validazione Deterministica
            # -----------------------------
            is_valid = True
            error_delta_list = []

            # A. Analisi Statica Reale
            if result_data.file_path and os.path.exists(result_data.file_path):
                sa_valid, sa_delta = self._run_static_analysis(result_data.file_path)
                if not sa_valid:
                    is_valid = False
                    error_delta_list.append(sa_delta)

            # B. Controlli Strutturali (Legacy/Basic)
            code = ""
            if result_data.files:
                code = "\n".join(f.content for f in result_data.files)
            
            if "placeholder" in code.lower():
                is_valid = False
                error_delta_list.append("Error: Q3 Failed. Placeholder detected. Fix required.")

            # -----------------------------
            # 3. Risultato
            # -----------------------------
            final_error_delta = "\n".join(error_delta_list) if not is_valid else None
            message = "Codice validato con successo." if is_valid else "Product Revision Fallita."

            validation_result = ValidationResult(
                contract_id=result_data.contract_id,
                is_valid=is_valid,
                error_delta=final_error_delta,
                workspace_snapshot=workspace_snapshot if not is_valid else None,
                message=message
            )

            if is_valid:
                print(f"[Quality Gate] Revisione superata.")
                self.broker.publish('release_queue', validation_result.model_dump())
            else:
                print(f"[Quality Gate] Revisione fallita. Delta Errore:\n{final_error_delta}")
                self.broker.publish('refine_queue', validation_result.model_dump())

        except Exception as e:
            print(f"[Quality Gate] Errore critico nel processing della validazione: {e}")

if __name__ == "__main__":
    qg = QualityGateService()
    qg.start()
