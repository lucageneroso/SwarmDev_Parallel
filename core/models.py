from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any


class Contract(BaseModel):
    id: str = Field(..., description="ID Univoco del contratto")
    context: str = Field(..., description="Il contesto del contratto (es. Frontend, Backend, Database)")
    description: str = Field(..., description="Descrizione in linguaggio naturale del task da eseguire")
    a2a_ocl_constraints: List[str] = Field(default_factory=list, description="Lista dei vincoli validati A2A-OCL")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Metadati opzionali aggiuntivi")


# 🔹 NUOVO
class GeneratedFile(BaseModel):
    path: str = Field(..., description="Percorso relativo del file")
    content: str = Field(..., description="Contenuto del file")


class CodeGenerationResult(BaseModel):
    contract_id: str

    # 🔹 nuovo formato principale
    files: Optional[List[GeneratedFile]] = Field(default=None)

    # 🔹 legacy (compatibilità)
    generated_code: Optional[str] = Field(default=None)
    file_path: Optional[str] = Field(default=None)


# 🔹 ⚠️ QUESTO TI MANCA (causa errore)
class ValidationResult(BaseModel):
    contract_id: str
    is_valid: bool
    error_delta: Optional[str] = Field(
        None,
        description="In caso di fallimento, l'errore per il self-refine"
    )
    workspace_snapshot: Optional[str] = Field(
        None,
        description="Snapshot XML del workspace generato da Repomix"
    )
    message: str