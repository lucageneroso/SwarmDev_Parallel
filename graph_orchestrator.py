import os
import sys
import tempfile
import subprocess
import operator
import json
import logging
import shutil
from typing import TypedDict, Optional, Annotated, Sequence
import yaml

from langchain_core.messages import SystemMessage, HumanMessage, AIMessage, BaseMessage
import warnings
warnings.filterwarnings("ignore", message=".*ChatLiteLLM.*")
from langchain_community.chat_models import ChatLiteLLM
from langgraph.graph import StateGraph, END
from dotenv import load_dotenv

load_dotenv()

# ============================================================================
# 1. GRAPH STATE
# ============================================================================
class OrchestratorState(TypedDict):
    chat_history: list[BaseMessage]
    design_doc: Optional[str]
    ocl_errors: Optional[str]
    json_contract: Optional[str]
    
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

    # ── Runtime Self-Healing (PM2) ───────────────────────
    runtime_errors: Optional[str]             # Errors extracted from PM2 logs
    runtime_retry_count: Annotated[int, operator.add]  # Runtime retry counter

# Constants
MAX_RETRIES = 3
MAX_OCL_RETRIES = 3
MAX_RUNTIME_RETRIES = 2
RUNTIME_WAIT_SECONDS = 8  # Seconds to wait after PM2 start before reading logs
CHROMADB_COLLECTION = "swarmdev_fixes"  # ChromaDB collection for RAG memory
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
DIRECTIVES_DIR = os.path.join(CURRENT_DIR, "directives")
SUPERPOWERS_DIR = os.path.join(CURRENT_DIR, "superpowers", "skills")

if CURRENT_DIR not in sys.path:
    sys.path.append(CURRENT_DIR)

# ============================================================================
# 2. CONTEXT & LLM INITIALIZATION
# ============================================================================
def load_directives() -> str:
    e_path = os.path.join(DIRECTIVES_DIR, "execution_rules.yaml")
    r_path = os.path.join(DIRECTIVES_DIR, "reasoning_constraints.yaml")
    
    directives_content = "SWARMDEV DIRECTIVES:\n"
    try:
        if os.path.exists(e_path):
            with open(e_path, "r", encoding="utf-8") as f:
                e_data = yaml.safe_load(f)
                directives_content += "\nEXECUTION RULES (E):\n"
                for rule in e_data.get("rules", []):
                    directives_content += f"- [{rule['id']}] {rule['content']}\n"
                    
        if os.path.exists(r_path):
            with open(r_path, "r", encoding="utf-8") as f:
                r_data = yaml.safe_load(f)
                directives_content += "\nREASONING CONSTRAINTS (R):\n"
                for constr in r_data.get("constraints", []):
                    directives_content += f"- [{constr['id']}] {constr['content']}\n"
    except Exception as e:
        print(f"[WARN] Error reading Parlant Directives: {e}")
    return directives_content

def load_superpowers() -> str:
    """Carica SOLO la skill brainstorming per la fase di Discovery.
    Writing-plans NON viene caricata perché causerebbe allucinazioni di
    'subagenti' e 'piani' che l'LLM simulerebbe in chat invece di
    emettere il trigger DESIGN_APPROVED: e cedere il controllo al DAG."""
    bs_path = os.path.join(SUPERPOWERS_DIR, "brainstorming", "SKILL.md")
    content = ""
    try:
        if os.path.exists(bs_path):
            with open(bs_path, "r", encoding="utf-8") as f:
                content = f.read()
    except Exception as e:
        print(f"[WARN] Error reading Superpowers: {e}")
    return content

llm_model = os.environ.get("LLM_MODEL", "gpt-4o-mini")
# We use a distinct model for Mind if specified
mind_model_name = os.environ.get("OPENROUTER_MODEL", llm_model)

mind_llm = ChatLiteLLM(model=mind_model_name, max_retries=3, temperature=0.2)
worker_llm = ChatLiteLLM(model=llm_model, max_retries=3, temperature=0.0)

import re
from datetime import datetime

logger = logging.getLogger("swarmdev.aci")

# ============================================================================
# 2b. ACI UTILITIES (CLI-Anything Safe Invocation Layer)
# ============================================================================
CLI_TIMEOUT_SECONDS = 30

def safe_cli_invoke(
    cmd: list[str],
    cwd: Optional[str] = None,
    timeout: int = CLI_TIMEOUT_SECONDS,
    parse_json: bool = False,
) -> dict:
    """
    Invoca un comando CLI in modo sicuro per il DAG.
    Non solleva MAI eccezioni verso il chiamante.
    Restituisce sempre un dict con success, stdout, stderr, returncode, parsed, error.
    """
    result = {
        "success": False,
        "stdout": "",
        "stderr": "",
        "returncode": -1,
        "parsed": None,
        "error": None,
    }
    
    try:
        proc = subprocess.run(
            cmd,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
        result["stdout"] = proc.stdout.strip()
        result["stderr"] = proc.stderr.strip()
        result["returncode"] = proc.returncode
        
        if proc.returncode == 0:
            result["success"] = True
            if parse_json and proc.stdout.strip():
                try:
                    result["parsed"] = json.loads(proc.stdout)
                except json.JSONDecodeError:
                    result["error"] = "CLI returned success but stdout is not valid JSON"
        else:
            result["error"] = f"CLI exit code {proc.returncode}: {proc.stderr or proc.stdout}"
            
    except subprocess.TimeoutExpired:
        result["error"] = f"CLI timeout after {timeout}s: {' '.join(cmd)}"
        logger.warning(result["error"])
    except FileNotFoundError:
        result["error"] = f"CLI binary not found: {cmd[0]}. Run 'cli-hub install mermaid' first."
        logger.error(result["error"])
    except OSError as e:
        result["error"] = f"OS error invoking CLI: {e}"
        logger.error(result["error"])
    except Exception as e:
        result["error"] = f"Unexpected error: {type(e).__name__}: {e}"
        logger.error(result["error"])
    
    return result


def _resolve_cli_binary(name: str) -> str:
    """Resolve a CLI binary name to its full path, checking the venv Scripts dir first."""
    import shutil as _shutil
    # Check if it's directly on PATH
    found = _shutil.which(name)
    if found:
        return found
    # Check the venv's Scripts directory (Windows: Scripts, Unix: bin)
    venv_dir = os.path.dirname(sys.executable)
    candidate = os.path.join(venv_dir, name)
    if os.name == "nt":
        for ext in (".exe", ".cmd", ""):
            if os.path.isfile(candidate + ext):
                return candidate + ext
    elif os.path.isfile(candidate):
        return candidate
    # Fallback: return the bare name and let subprocess raise FileNotFoundError
    return name


def _render_uml_diagram(mermaid_syntax: str, workspace_dir: str) -> tuple:
    """
    Pipeline ACI: Mermaid syntax → .png via cli-anything-mermaid.
    Returns (diagram_path, error_message). Never raises.
    """
    diagrams_dir = os.path.join(workspace_dir, "diagrams")
    os.makedirs(diagrams_dir, exist_ok=True)
    
    project_file = os.path.join(diagrams_dir, "uml_project.json")
    output_png = os.path.join(diagrams_dir, "architecture_uml.png")
    
    if os.path.exists(output_png):
        try:
            os.remove(output_png)
        except OSError:
            pass
            
    cli_bin = _resolve_cli_binary("cli-anything-mermaid")
    
    # Step 1: Create mermaid project
    step1 = safe_cli_invoke([
        cli_bin, "project", "new",
        "--sample", "flowchart",
        "-o", project_file,
    ])
    if not step1["success"]:
        return None, f"[ACI/Mermaid] project new failed: {step1['error']}"
    
    # Step 2: Set diagram source from mermaid syntax
    step2 = safe_cli_invoke([
        cli_bin,
        "--project", project_file,
        "diagram", "set",
        "--text", mermaid_syntax,
    ])
    if not step2["success"]:
        return None, f"[ACI/Mermaid] diagram set failed: {step2['error']}"
    
    # Step 3: Render to PNG
    step3 = safe_cli_invoke([
        cli_bin,
        "--project", project_file,
        "--json",
        "export", "render",
        output_png,
        "--format", "png",
    ])
    if not step3["success"]:
        return None, f"[ACI/Mermaid] export render failed: {step3['error']}"
    
    # Verify the file actually exists on disk
    if not os.path.exists(output_png):
        return None, f"[ACI/Mermaid] Render reported success but {output_png} not found"
    
    return output_png, None


# ── ACI/Seaclip Helpers ──────────────────────────────────────────────
def _seaclip_health_check() -> bool:
    """Check if SeaClip-Lite backend is reachable at localhost:5200."""
    cli_bin = _resolve_cli_binary("cli-anything-seaclip")
    result = safe_cli_invoke([cli_bin, "--json", "server", "health"], parse_json=True, timeout=5)
    return result["success"]


def _seaclip_create_issue(title: str, description: str, priority: str = "high") -> Optional[str]:
    """Create a Kanban issue and return its UUID, or None on failure."""
    cli_bin = _resolve_cli_binary("cli-anything-seaclip")
    result = safe_cli_invoke([
        cli_bin, "--json", "issue", "create",
        "--title", title,
        "--description", description,
        "--priority", priority,
    ], parse_json=True)
    if result["success"] and result.get("parsed"):
        parsed = result["parsed"]
        return parsed.get("id") or parsed.get("issue_id")
    return None


def _seaclip_move_issue(issue_id: Optional[str], column: str) -> bool:
    """Move a Kanban issue to a column. Returns True on success. Never raises."""
    if not issue_id:
        return False
    cli_bin = _resolve_cli_binary("cli-anything-seaclip")
    result = safe_cli_invoke([
        cli_bin, "--json", "issue", "move", issue_id,
        "--column", column,
    ])
    return result["success"]


# ── ACI/ChromaDB RAG Helpers ─────────────────────────────────────────
def _chromadb_health_check() -> bool:
    """Check if ChromaDB server is reachable (Docker on localhost:8000)."""
    cli_bin = _resolve_cli_binary("cli-anything-chromadb")
    result = safe_cli_invoke([cli_bin, "--json", "server", "heartbeat"], timeout=5)
    return result["success"]


def _chromadb_ensure_collection() -> bool:
    """Ensure the swarmdev_fixes collection exists. Idempotent."""
    cli_bin = _resolve_cli_binary("cli-anything-chromadb")
    result = safe_cli_invoke([
        cli_bin, "--json", "collection", "create",
        "--name", CHROMADB_COLLECTION,
    ])
    # Success OR already exists (409/error) is fine
    return True


def _chromadb_query(error_text: str, n_results: int = 3) -> Optional[str]:
    """Query RAG memory for past solutions to a given error. Returns formatted context or None."""
    if not error_text:
        return None
    cli_bin = _resolve_cli_binary("cli-anything-chromadb")
    result = safe_cli_invoke([
        cli_bin, "--json", "query", "search",
        "--collection", CHROMADB_COLLECTION,
        "--text", error_text[:500],  # Limit query length
        "--n-results", str(n_results),
    ], parse_json=True)
    if result["success"] and result.get("parsed"):
        parsed = result["parsed"]
        docs = parsed.get("documents", [[]])[0] if isinstance(parsed.get("documents"), list) else []
        if docs:
            return "\n---\n".join(docs[:n_results])
    return None


def _chromadb_add_fix(error: str, solution_summary: str) -> bool:
    """Store a successful error->fix pair in RAG memory."""
    import hashlib
    doc_id = "fix_" + hashlib.md5(error.encode()).hexdigest()[:12]
    text = f"ERRORE: {error[:200]}\nSOLUZIONE: {solution_summary[:500]}"
    cli_bin = _resolve_cli_binary("cli-anything-chromadb")
    result = safe_cli_invoke([
        cli_bin, "--json", "document", "add",
        "--collection", CHROMADB_COLLECTION,
        "--text", text,
        "--id", doc_id,
    ])
    return result["success"]


# ── ACI/PM2 Runtime Helpers ──────────────────────────────────────────
def _pm2_start(script_path: str, name: str = "swarmdev_backend") -> bool:
    """Start a process via PM2. Cleans up any previous instance first."""
    cli_bin = _resolve_cli_binary("cli-anything-pm2")
    # Cleanup previous instance (ignore errors)
    safe_cli_invoke([cli_bin, "--json", "lifecycle", "delete", name], timeout=10)
    result = safe_cli_invoke([
        cli_bin, "--json", "lifecycle", "start", script_path,
        "--name", name,
    ], timeout=15)
    return result["success"]


def _pm2_get_logs(name: str = "swarmdev_backend", lines: int = 30) -> Optional[str]:
    """Read recent logs from a PM2 process. Returns stdout text or None."""
    cli_bin = _resolve_cli_binary("cli-anything-pm2")
    result = safe_cli_invoke([
        cli_bin, "--json", "logs", "view", name,
        "--lines", str(lines),
    ], parse_json=True)
    if result["success"] and result.get("parsed"):
        return result["parsed"].get("stdout", "") or result["parsed"].get("stderr", "")
    # Fallback: raw stdout
    if result["success"]:
        return result["stdout"]
    return None


def _pm2_stop(name: str = "swarmdev_backend") -> bool:
    """Stop and delete a PM2 process."""
    cli_bin = _resolve_cli_binary("cli-anything-pm2")
    safe_cli_invoke([cli_bin, "--json", "lifecycle", "stop", name], timeout=10)
    safe_cli_invoke([cli_bin, "--json", "lifecycle", "delete", name], timeout=10)
    return True


def _extract_runtime_errors(log_text: str) -> Optional[str]:
    """Extract Python runtime errors (Traceback/Exception) from PM2 log output."""
    if not log_text:
        return None
    error_markers = ["Traceback", "Error:", "Exception:", "ModuleNotFoundError",
                     "ImportError", "SyntaxError", "NameError", "TypeError"]
    lines = log_text.split("\n")
    error_lines = []
    capturing = False
    for line in lines:
        if any(marker in line for marker in error_markers):
            capturing = True
        if capturing:
            error_lines.append(line)
    return "\n".join(error_lines) if error_lines else None


def extract_code(text: str) -> str:
    match = re.search(r"```[a-zA-Z]*\n?(.*?)```", text, re.DOTALL)
    if match:
        return match.group(1).strip()
    return text.strip()

def parse_xml_files(text: str) -> dict[str, str]:
    """Estrae i tag <file path="...">...</file> dall'output dell'LLM."""
    pattern = re.compile(r'<file\s+path=["\']([^"\']+)["\']\s*>([\s\S]*?)</file>', re.MULTILINE)
    files = {}
    for match in pattern.finditer(text):
        path = match.group(1).strip()
        content = match.group(2).strip()
        files[path] = content
    return files

def write_project_to_dir(files: dict[str, str], base_dir: str):
    """Scrive i file parsati su disco ricreando le sottocartelle."""
    os.makedirs(base_dir, exist_ok=True)
    for rel_path, content in files.items():
        full_path = os.path.join(base_dir, rel_path.lstrip("/"))
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        with open(full_path, "w", encoding="utf-8") as f:
            f.write(content)
    return base_dir

# ============================================================================
# 3. MIND NODES (Discovery, Planning, OCL Validation)
# ============================================================================
def human_node(state: OrchestratorState):
    history = state.get("chat_history", [])
    if not history:
        # Initial prompt
        user_input = input("\n[System] Inserisci la tua richiesta iniziale per SwarmDev:\n> ")
    else:
        user_input = input("\n> ")
        
    if user_input.strip() == "":
        user_input = "continue"
        
    history.append(HumanMessage(content=user_input))
    return {"chat_history": history}

DISCOVERY_SYSTEM_PROMPT = """
You are the SwarmDev Architect (The Mind). Your ONLY job in this phase is requirements elicitation.

You will follow the BRAINSTORMING SKILL below to understand the user's idea through conversation.

{brainstorming_skill}

---
## CRITICAL RULES FOR THIS AUTOMATED PIPELINE (READ CAREFULLY)

1. **ONE QUESTION AT A TIME.** Ask a single clarifying question and stop. Wait for the answer.
2. **DO NOT write code, implementation plans, or subagent instructions.** You are NOT in a chat UI.
   There are no real subagents. There is no file system access. Do NOT pretend to run commands.
3. **DO NOT mention 'subagent-driven development', 'inline execution', writing-plans, or implementation plans.**
   Those concepts do not exist in this pipeline.
4. **WHEN TO STOP ELICITING:** When you have enough information to define the full system
   (tech stack, data model, API endpoints, main components) AND the user has said YES/APPROVO/OK,
   you MUST immediately emit the DESIGN_APPROVED trigger.
5. **HOW TO EMIT THE TRIGGER:**
   - Output EXACTLY the string `DESIGN_APPROVED:` on its own line.
   - Immediately after that, write the complete Markdown design document.
   - Example:
     ```
     DESIGN_APPROVED:
     # MyProject Design
     ## Overview
     ...
     ```
6. **DO NOT output `DESIGN_APPROVED:` until the user has explicitly approved the design.**
   Words like 'approvo', 'yes', 'sì', 'ok', 'proceed', 'looks good' count as approval.
   Descriptions or clarifications do NOT count as approval.
"""

def discovery_node(state: OrchestratorState):
    history = state.get("chat_history", [])
    brainstorming_skill = load_superpowers()
    
    sys_msg = SystemMessage(
        content=DISCOVERY_SYSTEM_PROMPT.format(brainstorming_skill=brainstorming_skill)
    )
    
    print("[Mind] Thinking...")
    response = mind_llm.invoke([sys_msg] + history)
    
    # Extract token usage
    tokens = 0
    if hasattr(response, 'usage_metadata') and response.usage_metadata:
        tokens = response.usage_metadata.get('total_tokens', 0)
        
    content = response.content
    if "DESIGN_APPROVED:" in content:
        parts = content.split("DESIGN_APPROVED:")
        msg = parts[0].strip()
        design_doc = parts[1].strip() if len(parts) > 1 else "Design Doc Generato."
        
        if msg:
            print(f"\n[Mind]: {msg}\n")
        print(f"\n[Mind]: ✅ Design approvato e salvato in memoria.")
        
        history.append(AIMessage(content=msg + "\n[DESIGN APPROVED]"))
        return {"chat_history": history, "design_doc": design_doc, "total_tokens": tokens}
    else:
        print(f"\n[Mind]: {content}\n")
        history.append(response)
        return {"chat_history": history, "total_tokens": tokens}

def router_discovery(state: OrchestratorState):
    if state.get("design_doc"):
        return "planning_node"
    return "human_node"

def planning_node(state: OrchestratorState):
    print("\n[Mind] Planning & Contract Generation...")
    design = state.get("design_doc", "")
    errors = state.get("ocl_errors", "")
    
    sys_msg = SystemMessage(
        content="You are the SwarmDev Architect. Based on the DESIGN, generate a JSON Contract. "
                "The JSON must contain FOUR keys:\n"
                "1. 'frontend_requirements' (string)\n"
                "2. 'backend_requirements' (string)\n"
                "3. 'a2a_ocl_constraints' (list of strings)\n"
                "4. 'mermaid_syntax' (string): A Mermaid flowchart (graph TD) representing the system architecture. "
                "Max 15 nodes. Use simple labels. Example: 'graph TD; A[Frontend]-->B[API Gateway]; B-->C[Database];'\n\n"
                "=== A2A-OCL STRICT SYNTAX RULES ===\n"
                "Each constraint MUST match: context TYPE inv: EXPRESSION\n\n"
                "ALLOWED constructs:\n"
                "- Navigation: self.field, self.field.subfield\n"
                "- Comparison: =, !=, <, >, <=, >=\n"
                "- Logic: and, or, implies, not\n"
                "- Iterators: self.collection->forAll(x | EXPR), self.collection->exists(x | EXPR)\n"
                "- Method calls on collections: self.collection->contains(value), self.collection->size()\n"
                "- Literals: numbers (10, 0), booleans (true, false), strings with DOUBLE QUOTES (\"value\")\n"
                "- Grouping: (expression)\n\n"
                "FORBIDDEN (will cause parser failure):\n"
                "- NO function calls like currentDate(), now(), getTime()\n"
                "- NO single quotes: use \"value\" NOT 'value'\n"
                "- NO null keyword: use not self.field = 0 instead\n"
                "- NO standalone method calls: size() is only valid after -> like self.list->size()\n\n"
                "VALID EXAMPLES:\n"
                "- context Backend inv: self.cyclomatic_complexity <= 10\n"
                "- context API inv: self.endpoints->forAll(e | e.response_time <= 200)\n"
                "- context Data inv: self.records->exists(r | r.is_valid = true)\n"
                "- context Auth inv: self.role != \"guest\" implies self.permissions->size() > 0\n\n"
                "Output ONLY valid JSON. No markdown code fences."
    )
    
    hum_msg_content = f"DESIGN:\n{design}\n"
    if errors:
        hum_msg_content += f"\nCRITICAL OCL SYNTAX ERROR in previous attempt:\n{errors}\nFix the OCL expressions immediately."
        
    hum_msg = HumanMessage(content=hum_msg_content)
    response = mind_llm.invoke([sys_msg, hum_msg])
    
    tokens = 0
    if hasattr(response, 'usage_metadata') and response.usage_metadata:
        tokens = response.usage_metadata.get('total_tokens', 0)
        
    json_str = extract_code(response.content)
    
    # ── ACI: Render UML diagram from mermaid_syntax in contract (best-effort) ──
    uml_path = None
    uml_error = None
    
    try:
        contract_data = json.loads(json_str)
        mermaid_syntax = contract_data.get("mermaid_syntax", "")
    except (json.JSONDecodeError, AttributeError):
        mermaid_syntax = ""
    
    if mermaid_syntax:
        workspace_dir = os.path.join(CURRENT_DIR, "mind_workspace")
        print("[Mind/ACI] 🎨 Generating UML diagram via cli-anything-mermaid...")
        uml_path, uml_error = _render_uml_diagram(mermaid_syntax, workspace_dir)
        
        if uml_path:
            print(f"[Mind/ACI] ✅ UML Diagram rendered: {uml_path}")
        else:
            print(f"[Mind/ACI] ⚠️ UML generation failed (non-blocking): {uml_error}")
    else:
        uml_error = "[ACI/Mermaid] No mermaid_syntax key in contract (skipped)"
        print(f"[Mind/ACI] ⚠️ {uml_error}")
    
    # ── ACI/Seaclip: Create Kanban issues (best-effort) ──
    fe_issue_id = None
    be_issue_id = None
    kanban_err = None

    if _seaclip_health_check():
        print("[Mind/ACI] 📋 SeaClip backend online. Creating Kanban issues...")
        fe_issue_id = _seaclip_create_issue(
            title="Frontend: React App",
            description=f"Build frontend per: {design[:200]}...",
            priority="high",
        )
        be_issue_id = _seaclip_create_issue(
            title="Backend: Python API",
            description=f"Build backend per: {design[:200]}...",
            priority="high",
        )
        if fe_issue_id and be_issue_id:
            print(f"[Mind/ACI] ✅ Kanban: Frontend={fe_issue_id[:8]}... Backend={be_issue_id[:8]}...")
        else:
            kanban_err = "[ACI/Seaclip] Failed to create one or both issues"
            print(f"[Mind/ACI] ⚠️ {kanban_err}")
    else:
        kanban_err = "[ACI/Seaclip] Backend not reachable at localhost:5200 (skipped)"
        print(f"[Mind/ACI] ⚠️ {kanban_err}")

    return {
        "json_contract": json_str,
        "total_tokens": tokens,
        "uml_diagram_path": uml_path,
        "uml_diagram_error": uml_error,
        "kanban_frontend_issue_id": fe_issue_id,
        "kanban_backend_issue_id": be_issue_id,
        "kanban_error": kanban_err,
    }

def validate_ocl_node(state: OrchestratorState):
    print("[Mind] Validating A2A-OCL Constraints...")
    from quality_gate.ocl_evaluator import A2AOCLValidator
    
    json_contract = state.get("json_contract", "{}")
    
    try:
        data = json.loads(json_contract)
        constraints = data.get("a2a_ocl_constraints", [])
    except Exception as e:
        print(f"[Mind] Errore di parsing JSON del contratto: {e}")
        return {"ocl_errors": f"JSON Parse Error: {e}"}
        
    grammar_path = os.path.join(CURRENT_DIR, "core", "grammar", "a2a_ocl.lark")
    validator = A2AOCLValidator(grammar_path=grammar_path)
    
    errors = []
    for c in constraints:
        res = validator.validate_expression(c)
        if not res["is_valid"]:
            errors.append(f"Expression '{c}': {res.get('error_delta', 'Sintassi invalida')}")
            
    if errors:
        error_log = "\n".join(errors)
        print(f"[Mind] ⚠️ Validazione OCL FALLITA. ({len(errors)} errori):")
        for e in errors:
            print(f"       ❌ {e}")
        return {"ocl_errors": error_log, "ocl_retry_count": 1}
        
    print("[Mind] ✅ Validazione OCL SUPERATA. Passo il contratto ai Worker.")
    return {"ocl_errors": None}

def router_ocl(state: OrchestratorState):
    ocl_retries = state.get("ocl_retry_count", 0)
    if state.get("ocl_errors"):
        if ocl_retries >= MAX_OCL_RETRIES:
            print(f"[Mind] ⚠️ Max OCL retries ({MAX_OCL_RETRIES}) raggiunto. Procedo con vincoli NON validati.")
            return "fanout_node"
        print(f"[Mind] Micro-Loop retry {ocl_retries}/{MAX_OCL_RETRIES}...")
        return "planning_node"
    return "fanout_node"

def fanout_node(state: OrchestratorState):
    print("\n[Orchestrator] Avvio esecuzione parallela dei Worker (Frontend & Backend)...")
    return {}

# ============================================================================
# 4. WORKER NODES (Actors)
# ============================================================================
FRONTEND_SYSTEM_PROMPT = """
You are the SwarmDev Frontend Blind Builder.
You MUST generate a complete, multi-file React project structure ready for GitHub.
DO NOT output a single monolithic file. Generate EVERY file the project needs.

OUTPUT FORMAT (MANDATORY - NO EXCEPTIONS):
Output ONLY using <file> XML tags, one per file:
<file path="package.json">
{ "name": "my-app", ... }
</file>
<file path="src/index.jsx">
import React from 'react';
...
</file>

RULES:
- Use plain JavaScript (JSX), NOT TypeScript.
- Always include: package.json, public/index.html, src/index.jsx, src/App.jsx.
- Split components into separate files under src/components/.
- NO explanations, NO markdown, NO text outside <file> tags.
"""

def frontend_actor(state: OrchestratorState):
    print("[Frontend Actor] Generating Code...")
    # ACI/Seaclip: Move ticket to In Progress
    _seaclip_move_issue(state.get("kanban_frontend_issue_id"), "In Progress")
    directives = load_directives()
    
    sys_msg = SystemMessage(content=FRONTEND_SYSTEM_PROMPT + "\n" + directives)
    
    try:
        reqs = json.loads(state['json_contract']).get('frontend_requirements', state['json_contract'])
    except:
        reqs = state['json_contract']
        
    user_content = f"REQUIREMENTS:\n{reqs}"
    if state.get("frontend_errors") and state.get("frontend_code"):
        user_content += (
            f"\n\nYOUR PREVIOUS CODE:\n{state['frontend_code']}\n\n"
            f"CRITICAL FAILURE. Linter errors found:\n{state['frontend_errors']}\n\n"
            f"Fix ALL errors. Re-output the ENTIRE project using <file> tags."
        )
    # RAG: Inject past solutions if available
    if state.get("frontend_rag_context"):
        user_content += f"\n\n[RAG MEMORY - Past Solutions for Similar Errors]\n{state['frontend_rag_context']}"
        
    hum_msg = HumanMessage(content=user_content)
    response = worker_llm.invoke([sys_msg, hum_msg])
    
    tokens = 0
    if hasattr(response, 'usage_metadata') and response.usage_metadata:
        tokens = response.usage_metadata.get('total_tokens', 0)
    
    return {"frontend_code": response.content, "total_tokens": tokens}

BACKEND_SYSTEM_PROMPT = """
You are the SwarmDev Backend Blind Builder.
You MUST generate a complete, multi-file Python project structure ready for GitHub.
DO NOT output a single monolithic file. Generate EVERY file the project needs.

OUTPUT FORMAT (MANDATORY - NO EXCEPTIONS):
Output ONLY using <file> XML tags, one per file:
<file path="requirements.txt">
fastapi
uvicorn
</file>
<file path="app/main.py">
from fastapi import FastAPI
app = FastAPI()
</file>

RULES:
- Use Python 3.10+.
- Always include: requirements.txt, README.md, and a proper package structure.
- Split modules into separate files (routes, models, services).
- NO explanations, NO markdown, NO text outside <file> tags.
"""

def backend_actor(state: OrchestratorState):
    print("[Backend Actor] Generating Code...")
    # ACI/Seaclip: Move ticket to In Progress
    _seaclip_move_issue(state.get("kanban_backend_issue_id"), "In Progress")
    directives = load_directives()
    
    sys_msg = SystemMessage(content=BACKEND_SYSTEM_PROMPT + "\n" + directives)
    
    try:
        reqs = json.loads(state['json_contract']).get('backend_requirements', state['json_contract'])
    except:
        reqs = state['json_contract']
        
    user_content = f"REQUIREMENTS:\n{reqs}"
    if state.get("backend_errors") and state.get("backend_code"):
        user_content += (
            f"\n\nYOUR PREVIOUS CODE:\n{state['backend_code']}\n\n"
            f"CRITICAL FAILURE. Linter errors found:\n{state['backend_errors']}\n\n"
            f"Fix ALL errors. Re-output the ENTIRE project using <file> tags."
        )
    # RAG: Inject past solutions if available
    if state.get("backend_rag_context"):
        user_content += f"\n\n[RAG MEMORY - Past Solutions for Similar Errors]\n{state['backend_rag_context']}"
        
    hum_msg = HumanMessage(content=user_content)
    response = worker_llm.invoke([sys_msg, hum_msg])
    
    tokens = 0
    if hasattr(response, 'usage_metadata') and response.usage_metadata:
        tokens = response.usage_metadata.get('total_tokens', 0)
    
    return {"backend_code": response.content, "total_tokens": tokens}

# ============================================================================
# 5. CRITIC NODES (REAL QUALITY GATES - DIRECTORY-BASED)
# ============================================================================
def run_quality_gate_on_dir(tmp_dir: str, lang: str) -> str:
    """Esegue il Quality Gate sull'intera directory temporanea del progetto."""
    error_deltas = []

    if lang == "js":
        eslint_config_path = os.path.join(tmp_dir, "eslint.config.mjs")
        with open(eslint_config_path, "w", encoding="utf-8") as f:
            f.write("export default [{ languageOptions: { ecmaVersion: 2022, sourceType: 'module', parserOptions: { ecmaFeatures: { jsx: true } } }, rules: {} }];")
        try:
            cmd_eslint = ["npx.cmd" if os.name == "nt" else "npx", "eslint", "--no-color", "--ext", ".js,.jsx", "."]
            res = subprocess.run(cmd_eslint, cwd=tmp_dir, capture_output=True, text=True, timeout=30)
            if res.returncode != 0 and res.stdout.strip():
                lines = [l.strip() for l in res.stdout.strip().split("\n") if l.strip() and "error" in l.lower()]
                for line in lines[:8]:
                    error_deltas.append(f"ESLint: {line}")
        except Exception as e:
            error_deltas.append(f"ESLint Error: {e}")

    elif lang == "py":
        # Formatta con black (best effort)
        subprocess.run([sys.executable, "-m", "black", "-q", "."], cwd=tmp_dir, check=False)
        # Complessità ciclomatica con radon
        cmd_radon = [sys.executable, "-m", "radon", "cc", "-n", "C", "-s", "."]
        res_radon = subprocess.run(cmd_radon, cwd=tmp_dir, capture_output=True, text=True)
        if res_radon.stdout.strip():
            for line in res_radon.stdout.strip().split("\n"):
                if line.strip():
                    error_deltas.append(f"Radon CC: {line.strip()}")
        # Linting con flake8
        cmd_flake8 = [
            sys.executable, "-m", "flake8", ".",
            "--max-line-length=120",
            "--extend-ignore=E501,E302,W605,F401,F841,W291,W293"
        ]
        res_flake8 = subprocess.run(cmd_flake8, cwd=tmp_dir, capture_output=True, text=True)
        if res_flake8.returncode != 0 and res_flake8.stdout.strip():
            lines = [l.strip() for l in res_flake8.stdout.strip().split("\n") if l.strip()]
            for line in lines[:8]:
                error_deltas.append(f"Flake8: {line}")

    return "\n".join(error_deltas)

def frontend_critic(state: OrchestratorState):
    print("[Frontend Critic] Evaluating Code...")
    # ACI/Seaclip: Move ticket to Review
    _seaclip_move_issue(state.get("kanban_frontend_issue_id"), "Review")
    raw = state.get("frontend_code", "")
    if not raw:
        return {"frontend_errors": "Critical Error: No code generated."}
    
    files = parse_xml_files(raw)
    if not files:
        # Fallback: nessun file XML trovato, considera errore non bloccante
        print("[Frontend Critic] ⚠️ Nessun tag <file> trovato. Skippo la validazione.")
        return {"frontend_errors": None}
    
    with tempfile.TemporaryDirectory() as tmp_dir:
        write_project_to_dir(files, tmp_dir)
        errors = run_quality_gate_on_dir(tmp_dir, "js")
    
    if errors:
        # RAG READ: query ChromaDB for past solutions to these errors
        rag_hint = _chromadb_query(errors)
        if rag_hint:
            print("[Frontend Critic/RAG] Found past solutions in memory")
            return {"frontend_errors": errors, "frontend_rag_context": f"[RAG MEMORY - Past Solutions]\n{rag_hint}"}
        return {"frontend_errors": errors, "frontend_rag_context": None}
    
    # RAG WRITE: if we fixed errors in a previous retry, save the solution
    if state.get("retry_count", 0) > 0 and state.get("frontend_errors"):
        prev_error = state["frontend_errors"]
        _chromadb_add_fix(prev_error, "Frontend code fixed after retry via linter feedback")
        print("[Frontend Critic/RAG] Fix saved to RAG memory")
    
    return {"frontend_errors": None, "frontend_rag_context": None}

def backend_critic(state: OrchestratorState):
    print("[Backend Critic] Evaluating Code...")
    # ACI/Seaclip: Move ticket to Review
    _seaclip_move_issue(state.get("kanban_backend_issue_id"), "Review")
    raw = state.get("backend_code", "")
    if not raw:
        return {"backend_errors": "Critical Error: No code generated."}
    
    files = parse_xml_files(raw)
    if not files:
        print("[Backend Critic] ⚠️ Nessun tag <file> trovato. Skippo la validazione.")
        return {"backend_errors": None}
    
    # Escludi file non-Python dalla valutazione
    py_files = {k: v for k, v in files.items() if k.endswith(".py")}
    if not py_files:
        return {"backend_errors": None}
    
    with tempfile.TemporaryDirectory() as tmp_dir:
        write_project_to_dir(py_files, tmp_dir)
        errors = run_quality_gate_on_dir(tmp_dir, "py")
    
    if errors:
        # RAG READ: query ChromaDB for past solutions to these errors
        rag_hint = _chromadb_query(errors)
        if rag_hint:
            print("[Backend Critic/RAG] Found past solutions in memory")
            return {"backend_errors": errors, "backend_rag_context": f"[RAG MEMORY - Past Solutions]\n{rag_hint}"}
        return {"backend_errors": errors, "backend_rag_context": None}
    
    # RAG WRITE: if we fixed errors in a previous retry, save the solution
    if state.get("retry_count", 0) > 0 and state.get("backend_errors"):
        prev_error = state["backend_errors"]
        _chromadb_add_fix(prev_error, "Backend code fixed after retry via linter feedback")
        print("[Backend Critic/RAG] Fix saved to RAG memory")
    
    return {"backend_errors": None, "backend_rag_context": None}

# ============================================================================
# 6. ROUTING E DOCUMENTATION
# ============================================================================
def routing_node(state: OrchestratorState):
    f_err = state.get("frontend_errors")
    b_err = state.get("backend_errors")
    if f_err or b_err:
        return {"retry_count": 1}
    return {}

def conditional_router(state: OrchestratorState) -> Sequence[str]:
    f_err = state.get("frontend_errors")
    b_err = state.get("backend_errors")
    
    print(f"[Router] Checking Errors. Current Retry Count: {state.get('retry_count', 0)}")
    
    if not f_err and not b_err:
        print("[OK] Validation PASSED. Routing to Documentation Node...")
        return ["documentation_node"]
        
    if state.get("retry_count", 0) >= MAX_RETRIES:
        print("[FAIL] Max retries reached. Exiting with validation failures.")
        return [END]
        
    next_nodes = []
    if f_err:
        print(f"[RETRY] Routing back to Frontend Actor. Linter Errors:\n{f_err}")
        next_nodes.append("frontend_actor")
    if b_err:
        print(f"[RETRY] Routing back to Backend Actor. Linter Errors:\n{b_err}")
        next_nodes.append("backend_actor")
        
    return next_nodes

def documentation_node(state: OrchestratorState):
    print("[Documentation Node] Creating GitHub-ready workspace...")
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    workspace_root = os.path.join(CURRENT_DIR, "workspace", f"project_{timestamp}")
    frontend_dir = os.path.join(workspace_root, "frontend")
    backend_dir = os.path.join(workspace_root, "backend")
    
    f_raw = state.get("frontend_code", "")
    b_raw = state.get("backend_code", "")
    
    # --- Salva Frontend ---
    f_files = parse_xml_files(f_raw)
    if f_files:
        write_project_to_dir(f_files, frontend_dir)
        print(f"[Documentation Node] ✅ Frontend: {len(f_files)} file(s) scritti in {frontend_dir}")
    elif f_raw:
        # Fallback: se non ci sono tag XML, salva raw
        os.makedirs(frontend_dir, exist_ok=True)
        with open(os.path.join(frontend_dir, "App.jsx"), "w", encoding="utf-8") as f:
            f.write(extract_code(f_raw))
        print(f"[Documentation Node] ⚠️ Frontend: nessun tag XML trovato, salvato come App.jsx")

    # --- Salva Backend ---
    b_files = parse_xml_files(b_raw)
    if b_files:
        write_project_to_dir(b_files, backend_dir)
        print(f"[Documentation Node] ✅ Backend: {len(b_files)} file(s) scritti in {backend_dir}")
    elif b_raw:
        os.makedirs(backend_dir, exist_ok=True)
        with open(os.path.join(backend_dir, "main.py"), "w", encoding="utf-8") as f:
            f.write(extract_code(b_raw))
        print(f"[Documentation Node] ⚠️ Backend: nessun tag XML trovato, salvato come main.py")

    # --- Crea ROOT del workspace ---
    os.makedirs(workspace_root, exist_ok=True)
    
    # Salva CONTRACT.json
    if state.get("json_contract"):
        with open(os.path.join(workspace_root, "CONTRACT.json"), "w", encoding="utf-8") as f:
            f.write(state["json_contract"])
    
    # Salva DESIGN.md
    if state.get("design_doc"):
        with open(os.path.join(workspace_root, "DESIGN.md"), "w", encoding="utf-8") as f:
            f.write(state["design_doc"])
    
    # ── Copia UML Diagram se presente (ACI artifact) ──
    uml_src = state.get("uml_diagram_path")
    has_uml = False
    if uml_src and os.path.exists(uml_src):
        uml_dest = os.path.join(workspace_root, "architecture_uml.png")
        shutil.copy2(uml_src, uml_dest)
        has_uml = True
        print(f"[Documentation Node] 📐 UML Diagram copiato in {uml_dest}")
    
    # Salva README.md radice
    with open(os.path.join(workspace_root, "README.md"), "w", encoding="utf-8") as f:
        f.write(f"# SwarmDev Generated Project\n\n")
        f.write(f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        f.write("## Structure\n")
        f.write("```\n")
        f.write("project/\n")
        f.write("  frontend/    # React app\n")
        f.write("  backend/     # Python API\n")
        f.write("  DESIGN.md    # Design document\n")
        f.write("  CONTRACT.json # A2A-OCL Contract\n")
        if has_uml:
            f.write("  architecture_uml.png  # ACI-generated UML diagram\n")
        f.write("```\n")
    
    # ── ACI/Seaclip: Move both tickets to Done ──
    _seaclip_move_issue(state.get("kanban_frontend_issue_id"), "Done")
    _seaclip_move_issue(state.get("kanban_backend_issue_id"), "Done")
    print("[Documentation Node] 📋 Kanban: Both tickets moved to Done")
    
    print(f"\n[Documentation Node] Workspace pronto: {workspace_root}")
    return {"documentation_path": workspace_root, "documentation_ready": True}


# ============================================================================
# 6b. RUNTIME SELF-HEALING NODE (PM2)
# ============================================================================
def runtime_execution_node(state: OrchestratorState):
    """Launch the generated backend via PM2, check logs for runtime crashes."""
    print("[Runtime Node] Launching backend via PM2 for runtime validation...")
    
    # ACI/Seaclip: Move backend ticket to Testing
    _seaclip_move_issue(state.get("kanban_backend_issue_id"), "Testing")
    
    doc_path = state.get("documentation_path", "")
    if not doc_path:
        print("[Runtime Node] No documentation_path, skipping runtime check")
        return {"runtime_errors": None}
    
    backend_dir = os.path.join(doc_path, "backend")
    
    # Try multiple common entry points
    possible_entry_points = [
        "main.py",
        "app.py",
        os.path.join("app", "main.py"),
        os.path.join("app", "app.py"),
        os.path.join("src", "main.py")
    ]
    
    main_py = None
    for ep in possible_entry_points:
        cand = os.path.join(backend_dir, ep)
        if os.path.exists(cand):
            main_py = cand
            break
            
    if not main_py:
        print("[Runtime Node] No main.py/app.py found in root or app/, skipping runtime check")
        return {"runtime_errors": None}
    
    # Step 1: Start the process via PM2
    started = _pm2_start(main_py, name="swarmdev_backend")
    if not started:
        print("[Runtime Node] PM2 start failed (non-blocking, PM2 may not be installed)")
        return {"runtime_errors": None}
    
    # Step 2: Wait for the server to stabilize
    import time
    print(f"[Runtime Node] Waiting {RUNTIME_WAIT_SECONDS}s for process to stabilize...")
    time.sleep(RUNTIME_WAIT_SECONDS)
    
    # Step 3: Read logs
    logs = _pm2_get_logs("swarmdev_backend", lines=30)
    
    # Step 4: Analyze for runtime errors
    if logs:
        runtime_errs = _extract_runtime_errors(logs)
        if runtime_errs:
            print(f"[Runtime Node] Runtime errors detected:\n{runtime_errs[:300]}")
            _pm2_stop("swarmdev_backend")
            return {
                "runtime_errors": runtime_errs,
                "backend_errors": f"RUNTIME CRASH (from PM2 logs):\n{runtime_errs}",
                "runtime_retry_count": 1,
            }
        else:
            print("[Runtime Node] Backend running clean - no errors in logs")
    else:
        print("[Runtime Node] No logs captured (process may have exited immediately)")
    
    # Cleanup
    _pm2_stop("swarmdev_backend")
    
    # ACI/Seaclip: Move backend ticket to Done (runtime passed)
    _seaclip_move_issue(state.get("kanban_backend_issue_id"), "Done")
    print("[Runtime Node] Runtime validation PASSED")
    return {"runtime_errors": None}


def runtime_router(state: OrchestratorState) -> str:
    """Route based on runtime errors: loop back to backend_actor or END."""
    if state.get("runtime_errors") and state.get("runtime_retry_count", 0) < MAX_RUNTIME_RETRIES:
        print(f"[Runtime Router] Runtime crash detected. Routing back to backend_actor (retry {state.get('runtime_retry_count', 0)}/{MAX_RUNTIME_RETRIES})")
        return "backend_actor"
    
    if state.get("runtime_errors"):
        print("[Runtime Router] Max runtime retries reached. Exiting with runtime failures.")
    else:
        print("[Runtime Router] All clear. Pipeline complete.")
    return END


# ============================================================================
# 7. BUILD AND COMPILE GRAPH
# ============================================================================
def build_orchestrator() -> StateGraph:
    workflow = StateGraph(OrchestratorState)
    
    # 1. Mind Nodes
    workflow.add_node("human_node", human_node)
    workflow.add_node("discovery_node", discovery_node)
    workflow.add_node("planning_node", planning_node)
    workflow.add_node("validate_ocl_node", validate_ocl_node)
    workflow.add_node("fanout_node", fanout_node)
    
    # 2. Worker Nodes
    workflow.add_node("frontend_actor", frontend_actor)
    workflow.add_node("backend_actor", backend_actor)
    workflow.add_node("frontend_critic", frontend_critic)
    workflow.add_node("backend_critic", backend_critic)
    workflow.add_node("routing_node", routing_node)
    workflow.add_node("documentation_node", documentation_node)
    workflow.add_node("runtime_execution_node", runtime_execution_node)
    
    # --- MIND ROUTING ---
    workflow.set_entry_point("human_node")
    workflow.add_edge("human_node", "discovery_node")
    
    workflow.add_conditional_edges("discovery_node", router_discovery, {
        "human_node": "human_node",
        "planning_node": "planning_node"
    })
    
    workflow.add_edge("planning_node", "validate_ocl_node")
    workflow.add_conditional_edges("validate_ocl_node", router_ocl, {
        "planning_node": "planning_node",
        "fanout_node": "fanout_node"
    })
    
    # --- WORKER ROUTING ---
    workflow.add_edge("fanout_node", "frontend_actor")
    workflow.add_edge("fanout_node", "backend_actor")
    
    workflow.add_edge("frontend_actor", "frontend_critic")
    workflow.add_edge("backend_actor", "backend_critic")
    
    workflow.add_edge("frontend_critic", "routing_node")
    workflow.add_edge("backend_critic", "routing_node")
    
    workflow.add_conditional_edges(
        "routing_node",
        conditional_router,
        {
            "frontend_actor": "frontend_actor",
            "backend_actor": "backend_actor",
            "documentation_node": "documentation_node",
            END: END
        }
    )
    
    # --- RUNTIME SELF-HEALING ---
    workflow.add_edge("documentation_node", "runtime_execution_node")
    
    workflow.add_conditional_edges(
        "runtime_execution_node",
        runtime_router,
        {
            "backend_actor": "backend_actor",
            END: END,
        }
    )
    
    return workflow.compile()


# ============================================================================
# EXECUTION ENTRYPOINT
# ============================================================================
def start_interactive_session():
    print("=====================================================")
    print("      SwarmDev End-to-End Orchestrator (LangGraph)   ")
    print("=====================================================")
    print("Modello Mind:", mind_model_name)
    print("Modello Worker:", llm_model)
    print("=====================================================")
    
    orchestrator = build_orchestrator()
    
    initial_state = {
        "chat_history": [],
        "design_doc": None,
        "ocl_errors": None,
        "json_contract": None,
        "retry_count": 0,
        "ocl_retry_count": 0,
        "total_tokens": 0,
        "frontend_code": None,
        "backend_code": None,
        "frontend_errors": None,
        "backend_errors": None,
        "documentation_ready": False,
        "documentation_path": None,
        # ACI Artifacts
        "uml_diagram_path": None,
        "uml_diagram_error": None,
        # ACI Kanban
        "kanban_frontend_issue_id": None,
        "kanban_backend_issue_id": None,
        "kanban_error": None,
        # RAG Memory
        "frontend_rag_context": None,
        "backend_rag_context": None,
        # Runtime Self-Healing
        "runtime_errors": None,
        "runtime_retry_count": 0,
    }
    
    print(f"\n🚀 Avviando l'esecuzione del DAG...")
    
    # Esegue il grafo fino all'END
    # Grazie al nodo human_node, il grafo si bloccherà ad attendere l'input usando la funzione input() standard.
    final_state = orchestrator.invoke(initial_state)
    
    final_retries = final_state.get("retry_count", 0)
    ocl_retries = final_state.get("ocl_retry_count", 0)
    total_tokens = final_state.get("total_tokens", 0)
    is_failed = bool(final_state.get("frontend_errors") or final_state.get("backend_errors"))
    pass_at_1 = not is_failed and final_retries == 0
    
    metrics = {
        "retry_count": final_retries,
        "ocl_retry_count": ocl_retries,
        "total_tokens": total_tokens,
        "pass_at_1": pass_at_1,
        "status": "FAILED" if is_failed else "SUCCESS"
    }
    
    print("\n📊 --- ACADEMIC METRICS LOG ---")
    print(json.dumps(metrics, indent=2))
    print("--------------------------------\n")
    
    if is_failed:
        print("❌ Esecuzione fallita dopo i retry massimi.")
    else:
        print("✅ Esecuzione completata con successo.")


if __name__ == "__main__":
    start_interactive_session()
