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

from typing import Annotated

@p.tool
async def validate_a2a_ocl_expression(
    context: p.ToolContext, 
    expression: Annotated[str, p.ToolParameterOptions(source="context", description="L'espressione A2A-OCL completa da validare (es. 'context Code inv: self.complexity <= 10'). Obbligatorio.")]
) -> p.ToolResult:
    """
    Valida la sintassi di un vincolo A2A-OCL generato.
    DEVI USARE SEMPRE QUESTO TOOL prima di finalizzare il Contratto JSON.

    Args:
        expression (str): L'espressione A2A-OCL completa da validare (es. 'context Code inv: self.complexity <= 10'). Obbligatorio.
    """
    result_dict = ocl_validator.validate_expression(expression)
    return p.ToolResult(data=result_dict)

@p.tool
async def publish_final_contract(
    context: p.ToolContext, 
    target_context: Annotated[str, p.ToolParameterOptions(source="context", description="Il contesto (es. Frontend, Backend). Obbligatorio.")], 
    description: Annotated[str, p.ToolParameterOptions(source="context", description="La descrizione in linguaggio naturale di ciò che l'Arm deve implementare. Obbligatorio.")], 
    a2a_ocl_constraints: Annotated[list[str], p.ToolParameterOptions(source="context", description="La lista delle stringhe A2A-OCL che hai preventivamente validato. Obbligatorio.")]
) -> p.ToolResult:
    """
    Quando hai finito di validare tutti i vincoli A2A-OCL per il tuo task e il contratto è pronto,
    DEVI invocare questo tool per rilasciare il contratto al broker.

    Args:
        target_context (str): Il contesto (es. Frontend, Backend). Obbligatorio.
        description (str): La descrizione in linguaggio naturale di ciò che l'Arm deve implementare. Obbligatorio.
        a2a_ocl_constraints (list[str]): La lista delle stringhe A2A-OCL che hai preventivamente validato. Obbligatorio.
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

MIND_WORKSPACE = os.path.join(PROJECT_ROOT, "mind_workspace")
os.makedirs(MIND_WORKSPACE, exist_ok=True)

@p.tool
async def save_design_document(
    context: p.ToolContext, 
    content: Annotated[str, p.ToolParameterOptions(source="context", description="Il contenuto testuale completo in Markdown del file DESIGN.md che hai appena generato. DEVI fornire questo parametro.")]
) -> p.ToolResult:
    """
    Fase 1 (Discovery): Salva il documento di architettura (DESIGN.md) concordato con l'utente.
    
    Args:
        content (str): Il contenuto testuale completo in Markdown del file DESIGN.md che hai appena generato. DEVI fornire questo parametro.
    """
    file_path = os.path.join(MIND_WORKSPACE, "DESIGN.md")
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(content)
    return p.ToolResult(data={"status": "success", "message": f"DESIGN.md salvato in {file_path}"})

@p.tool
async def save_roadmap_document(
    context: p.ToolContext, 
    content: Annotated[str, p.ToolParameterOptions(source="context", description="Il contenuto completo in Markdown del file ROADMAP.md, strutturato per Onde (Onda 1, Onda 2, ...). DEVI fornire questo parametro.")]
) -> p.ToolResult:
    """
    Fase 2 (Planning): Salva la roadmap di sviluppo divisa in Onde (ROADMAP.md).
    
    Args:
        content (str): Il contenuto completo in Markdown del file ROADMAP.md, strutturato per Onde (Onda 1, Onda 2, ...). DEVI fornire questo parametro.
    """
    file_path = os.path.join(MIND_WORKSPACE, "ROADMAP.md")
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(content)
    return p.ToolResult(data={"status": "success", "message": f"ROADMAP.md salvato in {file_path}"})

@p.tool
async def save_state_document(
    context: p.ToolContext, 
    content: Annotated[str, p.ToolParameterOptions(source="context", description="Il contenuto in Markdown del file STATE.md che elenca lo stato di validazione di ogni Onda. DEVI fornire questo parametro.")]
) -> p.ToolResult:
    """
    Fase 2/3 (Execution): Traccia lo stato di avanzamento delle Onde in STATE.md.
    
    Args:
        content (str): Il contenuto in Markdown del file STATE.md che elenca lo stato di validazione di ogni Onda. DEVI fornire questo parametro.
    """
    file_path = os.path.join(MIND_WORKSPACE, "STATE.md")
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(content)
    return p.ToolResult(data={"status": "success", "message": f"STATE.md salvato in {file_path}"})