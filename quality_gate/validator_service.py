# quality_gate/validator_service.py
import sys
import os

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
        print("🛡️ [Quality Gate] Servizio inizializzato. In ascolto per Product Revision...")
        self.broker.consume('validation_queue', self.evaluate_code)

    def evaluate_code(self, message_data: dict):
        try:
            result_data = CodeGenerationResult(**message_data)
            print(f"🔍 [Quality Gate] Valutazione codice generato per contratto: {result_data.contract_id}")

            import subprocess

            # -----------------------------
            # 1. Esecuzione Repomix
            # -----------------------------
            workspace_snapshot = None
            if result_data.file_path and os.path.exists(result_data.file_path):
                print(f"📡 [Quality Gate] Esecuzione Repomix in {result_data.file_path}...")
                try:
                    cmd = ["npx.cmd", "--yes", "repomix", "--style", "xml", "--token-count-encoding", "o200k_base"]
                    subprocess.run(cmd, cwd=result_data.file_path, capture_output=True, text=True, check=False)
                    
                    repomix_out = os.path.join(result_data.file_path, "repomix-output.xml")
                    if os.path.exists(repomix_out):
                        with open(repomix_out, "r", encoding="utf-8") as f:
                            workspace_snapshot = f.read()
                        print(f"✅ [Quality Gate] Repomix ha generato con successo lo snapshot XML.")
                    else:
                        print(f"⚠️ [Quality Gate] Repomix non ha generato il file repomix-output.xml.")
                except Exception as e:
                    print(f"⚠️ [Quality Gate] Errore esecuzione repomix: {e}")

            # -----------------------------
            # 2. Recupero codice
            # -----------------------------
            code = ""

            if result_data.files:
                print(f"📦 [Quality Gate] Trovati {len(result_data.files)} file generati.")

                # aggregazione codice
                code = "\n\n".join(
                    f"// FILE: {f.path}\n{f.content}"
                    for f in result_data.files
                )
            elif result_data.generated_code:
                print("⚠️ [Quality Gate] Uso modalità legacy (generated_code).")
                code = result_data.generated_code
            else:
                raise Exception("Nessun codice da validare.")

            # -----------------------------
            # 3. Validazione base
            # -----------------------------
            is_valid = True
            error_delta = None
            message = "Codice validato con successo contro i vincoli A2A-OCL."

            # ❌ controllo placeholder
            if "placeholder" in code.lower():
                is_valid = False
                error_delta = "Trovata keyword 'placeholder'. Riscrivere il codice reale."
                message = "Product Revision Fallita (placeholder rilevato)."

            # ❌ controllo file vuoti
            if result_data.files:
                empty_files = [f.path for f in result_data.files if not f.content.strip()]
                if empty_files:
                    is_valid = False
                    error_delta = f"File vuoti trovati: {empty_files}"
                    message = "Product Revision Fallita (file vuoti)."

            # ❌ controllo estensioni sospette
            if result_data.files:
                invalid_ext = [
                    f.path for f in result_data.files
                    if not any(f.path.endswith(ext) for ext in [".js", ".ts", ".py", ".html", ".css", ".json", ".java", ".php"])
                ]
                if invalid_ext:
                    is_valid = False
                    error_delta = f"File con estensioni non valide: {invalid_ext}"
                    message = "Product Revision Fallita (estensioni non valide)."

            # ❌ controllo error generico
            if "error" in code.lower():
                is_valid = False
                error_delta = "Keyword 'error' rilevata nel codice."
                message = "Product Revision Fallita (error rilevato)."

            # -----------------------------
            # 4. Risultato
            # -----------------------------
            validation_result = ValidationResult(
                contract_id=result_data.contract_id,
                is_valid=is_valid,
                error_delta=error_delta,
                workspace_snapshot=workspace_snapshot if not is_valid else None,
                message=message
            )

            if is_valid:
                print(f"✅ [Quality Gate] Revisione superata. Invio a release_queue.")
                self.broker.publish('release_queue', validation_result.model_dump())
            else:
                print(f"❌ [Quality Gate] Revisione fallita. Invio Delta Errore a refine_queue.")
                self.broker.publish('refine_queue', validation_result.model_dump())

        except Exception as e:
            print(f"❌ [Quality Gate] Errore critico nel processing della validazione: {e}")

if __name__ == "__main__":
    qg = QualityGateService()
    qg.start()
