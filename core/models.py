# core/models.py
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any

class Contract(BaseModel):
    id: str = Field(..., description="ID Univoco del contratto")
    context: str = Field(..., description="Il contesto del contratto (es. Frontend, Backend, Database)")
    description: str = Field(..., description="Descrizione in linguaggio naturale del task da eseguire")
    a2a_ocl_constraints: List[str] = Field(default_factory=list, description="Lista dei vincoli validati A2A-OCL")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Metadati opzionali aggiuntivi")

class CodeGenerationResult(BaseModel):
    contract_id: str
    generated_code: str = Field(..., description="Il codice sorgente generato da OpenCode")
    file_path: Optional[str] = Field(None, description="Percorso del file generato (se applicabile)")

class ValidationResult(BaseModel):
    contract_id: str
    is_valid: bool
    error_delta: Optional[str] = Field(None, description="In caso di fallimento, l'errore per il self-refine")
    message: str
