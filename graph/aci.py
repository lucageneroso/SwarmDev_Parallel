"""
graph.aci — ACI (CLI-Anything) Safe Invocation Layer
======================================================
Tutte le utility per l'integrazione con tool CLI esterni:
  - safe_cli_invoke()    — wrapper sicuro per subprocess
  - Mermaid UML          — rendering diagrammi
  - SeaClip Kanban       — gestione issue
  - ChromaDB RAG         — memoria errore→fix
  - PM2 Runtime          — self-healing del backend

Estratto da graph_orchestrator.py righe 138-461.
"""

import os
import sys
import json
import subprocess
import logging
from typing import Optional

from graph.state import PROJECT_ROOT, CHROMADB_COLLECTION

logger = logging.getLogger("swarmdev.aci")

# ============================================================================
# CLI SAFE INVOCATION
# ============================================================================
CLI_TIMEOUT_SECONDS = 30


def safe_cli_invoke(
    cmd: list[str],
    cwd: Optional[str] = None,
    timeout: int = CLI_TIMEOUT_SECONDS,
    parse_json: bool = False,
    env: Optional[dict] = None,
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
            env=env,
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


# ============================================================================
# ACI/MERMAID — UML Diagram Rendering
# ============================================================================
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


# ============================================================================
# ACI/SEACLIP — Kanban Issue Management
# ============================================================================
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


# ============================================================================
# ACI/CHROMADB — RAG Memory (Error → Fix Pairs)
# ============================================================================
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


def _chromadb_query_raw(error_text: str, n_results: int = 3) -> Optional[dict]:
    """Query RAG memory for past solutions and return the raw parsed result."""
    if not error_text:
        return None
    import requests
    import litellm
    try:
        emb_res = litellm.embedding(model="openrouter/openai/text-embedding-ada-002", input=[error_text[:500]])
        vector = emb_res.data[0]["embedding"]
        
        url_base = "http://localhost:8000/api/v2/tenants/default_tenant/databases/default_database/collections"
        col_res = requests.get(f"{url_base}/{CHROMADB_COLLECTION}")
        if col_res.status_code != 200:
            return None
        col_id = col_res.json().get("id")
        
        payload = {
            "query_embeddings": [vector],
            "n_results": n_results
        }
        query_res = requests.post(f"{url_base}/{col_id}/query", json=payload)
        if query_res.status_code == 200:
            return query_res.json()
    except Exception as e:
        logger.error(f"[ChromaDB] Query failed: {e}")
    return None


def _chromadb_query(error_text: str, n_results: int = 3) -> Optional[str]:
    """Query RAG memory for past solutions to a given error. Returns formatted context or None."""
    parsed = _chromadb_query_raw(error_text, n_results)
    if not parsed:
        return None
        
    from datetime import datetime, timezone
    docs = parsed.get("documents", [[]])[0] if isinstance(parsed.get("documents"), list) else []
    metadatas = parsed.get("metadatas", [[]])[0] if isinstance(parsed.get("metadatas"), list) else []
    distances = parsed.get("distances", [[]])[0] if isinstance(parsed.get("distances"), list) else []
    
    valid_docs = []
    for i, doc in enumerate(docs):
        meta = metadatas[i] if i < len(metadatas) else {}
        dist = distances[i] if i < len(distances) else 0.0
        
        # Decay / Oblio logic
        if meta and "timestamp" in meta:
            try:
                dt = datetime.fromisoformat(meta["timestamp"].replace("Z", "+00:00"))
                age_days = (datetime.now(timezone.utc) - dt).days
                
                # Se il ricordo è più vecchio di 30 giorni ed ha una similarità debole (distanza > 0.6), lo dimentica
                if age_days > 30 and dist > 0.6:
                    print(f"[RAG/Decay] Memory {meta.get('id', 'unknown')} forgotten (age: {age_days} days, distance: {dist})")
                    continue
            except Exception as e:
                print(f"[RAG/Decay] Warning parsing timestamp: {e}")
                
        valid_docs.append(doc)
        
    if valid_docs:
        return "\n---\n".join(valid_docs[:n_results])
    return None


def _chromadb_get_by_id(doc_id: str) -> Optional[dict]:
    """Get a document and its metadata from ChromaDB by exact ID."""
    cli_bin = _resolve_cli_binary("cli-anything-chromadb")
    result = safe_cli_invoke([
        cli_bin, "--json", "document", "get",
        "--collection", CHROMADB_COLLECTION,
        "--id", doc_id
    ], parse_json=True)
    if result["success"] and result.get("parsed"):
        parsed = result["parsed"]
        ids = parsed.get("ids", [])
        if ids and doc_id in ids:
            idx = ids.index(doc_id)
            documents = parsed.get("documents", [])
            metadatas = parsed.get("metadatas", [])
            
            doc_text = documents[idx] if idx < len(documents) else ""
            doc_meta = metadatas[idx] if idx < len(metadatas) else {}
            
            return {
                "id": doc_id,
                "document": doc_text,
                "metadata": doc_meta
            }
    return None


def _chromadb_delete(doc_id: str) -> bool:
    """Delete a document from ChromaDB by ID."""
    cli_bin = _resolve_cli_binary("cli-anything-chromadb")
    result = safe_cli_invoke([
        cli_bin, "--json", "document", "delete",
        "--collection", CHROMADB_COLLECTION,
        "--id", doc_id
    ])
    return result["success"]


def _chromadb_add_fix(error: str, solution_summary: str, metadata: Optional[dict] = None) -> bool:
    """Store a successful error->fix pair in RAG memory with timestamp metadata (upsert style)."""
    import hashlib
    import json
    import requests
    import litellm
    from datetime import datetime, timezone
    
    doc_id = "fix_" + hashlib.md5(error.encode()).hexdigest()[:12]
    text = f"ERRORE: {error[:200]}\nSOLUZIONE: {solution_summary[:500]}"
    
    # Prepara i metadati
    meta_dict = metadata.copy() if metadata else {}
    if "timestamp" not in meta_dict:
        meta_dict["timestamp"] = datetime.now(timezone.utc).isoformat()
    if "uses_count" not in meta_dict:
        meta_dict["uses_count"] = 0
    if "failures_count" not in meta_dict:
        meta_dict["failures_count"] = 0
    if "id" not in meta_dict:
        meta_dict["id"] = doc_id
        
    # Delete first to prevent duplicate errors
    _chromadb_delete(doc_id)
    
    try:
        emb_res = litellm.embedding(model="openrouter/openai/text-embedding-ada-002", input=[text])
        vector = emb_res.data[0]["embedding"]
        
        url_base = "http://localhost:8000/api/v2/tenants/default_tenant/databases/default_database/collections"
        col_res = requests.get(f"{url_base}/{CHROMADB_COLLECTION}")
        if col_res.status_code != 200:
            return False
        col_id = col_res.json().get("id")
        
        payload = {
            "ids": [doc_id],
            "documents": [text],
            "metadatas": [meta_dict],
            "embeddings": [vector]
        }
        add_res = requests.post(f"{url_base}/{col_id}/add", json=payload)
        return add_res.status_code in (200, 201)
    except Exception as e:
        logger.error(f"[ChromaDB] Add fix failed: {e}")
        return False


# ============================================================================
# ACI/PM2 — Runtime Process Management
# ============================================================================
def _pm2_start(script_path: str, name: str = "swarmdev_backend", interpreter: str = None, cwd: Optional[str] = None, env: Optional[dict] = None) -> bool:
    """Start a process via PM2. Cleans up any previous instance first.
    
    Args:
        interpreter: Path to the Python interpreter to use (e.g. sys.executable).
                     When provided, creates an ephemeral Node.js launcher that
                     PM2 executes natively, which spawns the correct Python process.
    """
    cli_bin = _resolve_cli_binary("cli-anything-pm2")
    # Cleanup previous instance (ignore errors)
    safe_cli_invoke([cli_bin, "--json", "lifecycle", "delete", name], timeout=10)
    
    # PM2 is a Node.js process manager — it executes .js files natively.
    # To run Python with the correct venv interpreter, we generate an
    # ephemeral .js launcher that uses child_process.spawn.
    launch_target = script_path
    if interpreter:
        script_dir = os.path.dirname(os.path.abspath(script_path))
        launcher = os.path.join(script_dir, "_pm2_launcher.js")
        abs_script = os.path.abspath(script_path).replace("\\", "\\\\")
        abs_interp = interpreter.replace("\\", "\\\\")
        
        # Ensure spawn gets the cwd if provided
        if cwd:
            cwd_str = cwd.replace("\\", "\\\\")
            cwd_prop = f', cwd: "{cwd_str}"'
        else:
            cwd_prop = ""
            
        # Ensure spawn gets the env if provided
        if env:
            env_json = json.dumps(env)
            env_prop = f', env: Object.assign({{}}, process.env, {env_json})'
        else:
            env_prop = ""
        
        with open(launcher, "w", encoding="utf-8") as f:
            f.write(
                f'const {{ spawn }} = require("child_process");\n'
                f'const p = spawn("{abs_interp}", ["{abs_script}"], {{ stdio: "inherit"{cwd_prop}{env_prop} }});\n'
                f'p.on("exit", (code) => process.exit(code || 0));\n'
            )
        launch_target = launcher
        print(f"[PM2] Created Node.js launcher: {launcher}")
    
    result = safe_cli_invoke([
        cli_bin, "--json", "lifecycle", "start", launch_target,
        "--name", name,
    ], timeout=15, cwd=cwd, env=env)
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
