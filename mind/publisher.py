# mind/publisher.py
import sys
import os

# Assicuriamoci che python trovi i moduli partendo dalla root
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)

from reins.broker import RabbitMQBroker
from core.models import Contract

class MindPublisher:
    def __init__(self):
        self.broker = RabbitMQBroker()

    def publish_contract(self, contract: Contract):
        """Pubblica un contratto validato sulla coda per i worker (Arm)."""
        # Convertiamo il pydantic model in dict per il broker
        message_data = contract.model_dump()
        self.broker.publish('contract_queue', message_data)
        print(f"🧠 [Mind] Contratto JSON {contract.id} pubblicato su contract_queue")

# Singleton istance per la Mind
publisher_instance = MindPublisher()
