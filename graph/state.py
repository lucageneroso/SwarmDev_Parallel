"""
graph.state — Graph State Definition & Constants
==================================================
Contiene OrchestratorState (TypedDict condiviso da tutti i nodi)
e le costanti di configurazione del DAG.

Estratto da graph_orchestrator.py righe 25-84.
"""

import operator
import os
import sys
from typing import TypedDict, Optional, Annotated

from langchain_core.messages import BaseMessage

# ============================================================================
# PROJECT ROOT — equivalente all'ex CURRENT_DIR di graph_orchestrator.py
# Punta alla radice del progetto SwarmDev_Parallel/
# ============================================================================
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Assicura che il project root sia nel sys.path per import come quality_gate.*
if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)

# ============================================================================
# DIRECTORY PATHS
# ============================================================================
DIRECTIVES_DIR = os.path.join(PROJECT_ROOT, "directives")
SUPERPOWERS_DIR = os.path.join(PROJECT_ROOT, "superpowers", "skills")

# ============================================================================
# GRAPH STATE
# ============================================================================
class OrchestratorState(TypedDict):
    task_id: Optional[str]
    chat_history: list[BaseMessage]
    design_doc: Optional[str]
    design_rag_context: Optional[str]
    ocl_errors: Optional[str]
    json_contract: Optional[str]
    requirements_json: Optional[str]
    
    frontend_code: Optional[str]
    backend_code: Optional[str]
    frontend_errors: Optional[str]
    backend_errors: Optional[str]
    retry_count: Annotated[int, operator.add]
    ocl_retry_count: Annotated[int, operator.add]
    total_tokens: Annotated[int, operator.add]
    documentation_ready: Optional[bool]
    documentation_path: Optional[str]

    # ── ACI Artifacts (CLI-Anything Integration) ─────────
    uml_diagram_path: Optional[str]       # Absolute path to rendered .png
    uml_diagram_error: Optional[str]      # CLI error (informational, never blocking)

    # ── Seaclip Kanban Tracking ──────────────────────────
    kanban_frontend_issue_id: Optional[str]   # Seaclip issue UUID for Frontend
    kanban_backend_issue_id: Optional[str]    # Seaclip issue UUID for Backend
    kanban_error: Optional[str]               # Last Seaclip error (info, never blocking)

    # ── RAG Memory (ChromaDB) ────────────────────────────
    frontend_rag_context: Optional[str]       # Past solutions from ChromaDB
    backend_rag_context: Optional[str]
    retrieved_memories: Optional[list]        # List of dicts/tuples of retrieved memories for LTP/LTD

    # ── Runtime Self-Healing (PM2) ───────────────────────
    runtime_errors: Optional[str]             # Errors extracted from PM2 logs
    runtime_retry_count: Annotated[int, operator.add]  # Runtime retry counter
    
    # ── Testing Swarm ────────────────────────────────────
    test_files: Optional[dict]
    test_feedback: Optional[str]
    test_coverage: Optional[float]
    test_retry_count: Annotated[int, operator.add]
    
    # ── Quality Gate (SonarQube) ─────────────────────────
    quality_passed: Optional[bool]
    quality_feedback: Optional[str]
    quality_retry_count: Annotated[int, operator.add]

# ============================================================================
# CONSTANTS
# ============================================================================
MAX_RETRIES = 3
MAX_OCL_RETRIES = 3
MAX_RUNTIME_RETRIES = 2
MAX_TEST_RETRIES = 2
MAX_QUALITY_RETRIES = 2
RUNTIME_WAIT_SECONDS = 8  # Seconds to wait after PM2 start before reading logs
CHROMADB_COLLECTION = "swarmdev_fixes"  # ChromaDB collection for RAG memory
