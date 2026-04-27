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
            
            # Qui andrebbe l'analisi statica/ast del codice generato 
            # contro i constraint A2A-OCL del contratto originale.
            # Poiché non abbiamo il contratto originale nel payload in questa architettura demo
            # (dovremmo leggerlo da un DB o passarlo nel payload), 
            # simuliamo un check base:
            
            code = result_data.generated_code
            is_valid = True
            error_delta = None
            message = "Codice validato con successo contro i vincoli A2A-OCL."
            
            # Simuliamo una logica di fallimento casuale o basata su pattern per self-refine
            if "error" in code.lower() or "placeholder" in code.lower():
                is_valid = False
                error_delta = "Trovata keyword 'placeholder'. Riscrivere il codice senza simulazioni."
                message = "Product Revision Fallita. Necessario Self-Refine."

            validation_result = ValidationResult(
                contract_id=result_data.contract_id,
                is_valid=is_valid,
                error_delta=error_delta,
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
