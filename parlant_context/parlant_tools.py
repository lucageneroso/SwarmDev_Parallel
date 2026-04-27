# parlant_context/parlant_tools.py
import sys
import os
import parlant.sdk as p

# 1. Calcoliamo il percorso assoluto della radice del progetto (SwarmDev)
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, '..'))

# Aggiungiamo la root al path di Python per gli import
sys.path.append(PROJECT_ROOT)

from quality_gate.ocl_evaluator import A2AOCLValidator
from mind.publisher import publisher_instance
from core.models import Contract
import uuid

# 2. Costruiamo il percorso assoluto e infallibile per la grammatica
GRAMMAR_PATH = os.path.join(PROJECT_ROOT, "core", "grammar", "a2a_ocl.lark")

# Inizializziamo il validatore
ocl_validator = A2AOCLValidator(grammar_path=GRAMMAR_PATH)

@p.tool
async def validate_a2a_ocl_expression(context: p.ToolContext, expression: str) -> p.ToolResult:
    """
    Valida la sintassi di un vincolo A2A-OCL generato.
    DEVI USARE SEMPRE QUESTO TOOL prima di finalizzare il Contratto JSON.

    Args:
        expression: L'espressione A2A-OCL completa da validare (es. 'context Code inv: self.complexity <= 10')
    """
    result_dict = ocl_validator.validate_expression(expression)
    return p.ToolResult(data=result_dict)

@p.tool
async def publish_final_contract(context: p.ToolContext, target_context: str, description: str, a2a_ocl_constraints: list[str]) -> p.ToolResult:
    """
    Quando hai finito di validare tutti i vincoli A2A-OCL per il tuo task e il contratto è pronto,
    DEVI invocare questo tool per rilasciare il contratto al broker.

    Args:
        target_context: Il contesto (es. Frontend, Backend).
        description: La descrizione in linguaggio naturale di ciò che l'Arm deve implementare.
        a2a_ocl_constraints: La lista delle stringhe A2A-OCL che hai preventivamente validato.
    """
    contract_id = str(uuid.uuid4())
    contract = Contract(
        id=contract_id,
        context=target_context,
        description=description,
        a2a_ocl_constraints=a2a_ocl_constraints
    )
    
    # Pubblica asincronamente (tramite l'infrastruttura sincrona del publisher in un thread o simulato qui)
    try:
        publisher_instance.publish_contract(contract)
        return p.ToolResult(data={"status": "success", "message": f"Contratto {contract_id} rilasciato in produzione e inviato al worker."})
    except Exception as e:
         return p.ToolResult(data={"status": "error", "message": f"Errore broker: {str(e)}"})