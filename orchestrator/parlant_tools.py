# parlant_context/parlant_tools.py
import sys
import os
import parlant.sdk as p

# 1. Calcoliamo il percorso assoluto della radice del progetto (SwarmDev)
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, '..'))

# Aggiungiamo la root al path di Python per gli import
sys.path.append(PROJECT_ROOT)

from orchestrator.validator_tool import A2AOCLValidator

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
