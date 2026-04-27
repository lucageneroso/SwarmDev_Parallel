# arm/worker.py
import sys
import os

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)

from reins.broker import RabbitMQBroker
from core.models import Contract, CodeGenerationResult
from arm.opencode_wrapper import OpenCodeWrapper

class ArmWorker:
    def __init__(self):
        self.broker = RabbitMQBroker()
        self.opencode = OpenCodeWrapper(output_dir=os.path.join(PROJECT_ROOT, "workspace"))

    def start(self):
        print("🚀 [Arm] Nodi Worker inizializzati. In ascolto dei Contratti JSON...")
        self.broker.consume('contract_queue', self.process_contract)

    def process_contract(self, message_data: dict):
        try:
            # Deserializza dal Broker
            contract = Contract(**message_data)
            print(f"📥 [Arm] Ricevuto contratto: {contract.id} ({contract.context})")
            
            # 1. Esecuzione (Headless, Isolata, Nessuna Chat)
            generated_code = self.opencode.generate_code(
                context=contract.context,
                description=contract.description,
                constraints=contract.a2a_ocl_constraints
            )
            
            # 2. Creazione Risultato
            result = CodeGenerationResult(
                contract_id=contract.id,
                generated_code=generated_code,
                file_path=None
            )
            
            # 3. Invio al Quality Gate
            self.broker.publish('validation_queue', result.model_dump())
            print(f"📤 [Arm] Codice per {contract.id} generato e inviato alla validation_queue.")

        except Exception as e:
            print(f"❌ [Arm] Errore critico nel processing del contratto: {e}")

if __name__ == "__main__":
    worker = ArmWorker()
    worker.start()
