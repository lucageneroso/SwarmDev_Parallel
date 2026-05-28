"""Critic nodes for frontend and backend code quality evaluation.

Contains the directory-based quality gate runner (ESLint for JS, black/radon/flake8
for Python) and the frontend/backend critic nodes that orchestrate linting,
CodeGraph semantic analysis, and ChromaDB RAG memory read/write.
"""

import os, sys, subprocess, tempfile

from graph.state import OrchestratorState
from graph.aci import _seaclip_move_issue, _chromadb_query, _chromadb_add_fix
from graph.utils import parse_xml_files, write_project_to_dir
from swarm_mind import EpisodicBuffer

# Initialize episodic buffer
episodic_buffer = EpisodicBuffer()


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
        episodic_buffer.record(
            task_id=state.get("task_id"),
            node_name="frontend_critic",
            input_data={},
            output_data={"frontend_errors": "Critical Error: No code generated."},
            errors="Critical Error: No code generated."
        )
        return {"frontend_errors": "Critical Error: No code generated."}
    
    files = parse_xml_files(raw)
    if not files:
        # Fallback: nessun file XML trovato, considera errore non bloccante
        print("[Frontend Critic] ⚠️ Nessun tag <file> trovato. Skippo la validazione.")
        episodic_buffer.record(
            task_id=state.get("task_id"),
            node_name="frontend_critic",
            input_data={"frontend_code_len": len(raw)},
            output_data={"frontend_errors": None},
            metadata={"skipped_no_xml": True}
        )
        return {"frontend_errors": None}
    
    with tempfile.TemporaryDirectory() as tmp_dir:
        write_project_to_dir(files, tmp_dir)
        errors = run_quality_gate_on_dir(tmp_dir, "js")
        
        cg_context = ""
        if errors:
            print("[Frontend Critic] Costruzione Knowledge Graph (CodeGraph) per l'errore...")
            npx = "npx.cmd" if os.name == "nt" else "npx"
            try:
                subprocess.run([npx, "--yes", "@colbymchenry/codegraph", "init", ".", "--index"], cwd=tmp_dir, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                err_summary = errors.split("\n")[0][:100]
                cg_res = subprocess.run([npx, "--yes", "@colbymchenry/codegraph", "context", err_summary], cwd=tmp_dir, capture_output=True, text=True)
                if cg_res.stdout:
                    cg_context = f"\n\n[CODEGRAPH SEMANTIC CONTEXT]\n{cg_res.stdout}"
            except Exception as e:
                print(f"[Frontend Critic] ⚠️ CodeGraph query fallita: {e}")

    full_error = f"{errors}{cg_context}" if errors else None
    
    if full_error:
        # RAG READ: query ChromaDB for past solutions to these errors
        rag_hint = _chromadb_query(errors)
        
        # Record episode
        episodic_buffer.record(
            task_id=state.get("task_id"),
            node_name="frontend_critic",
            input_data={"frontend_code_len": len(raw)},
            output_data={"frontend_errors": full_error, "rag_hint": bool(rag_hint)},
            errors=errors
        )
        
        if rag_hint:
            print("[Frontend Critic/RAG] Found past solutions in memory")
            return {"frontend_errors": full_error, "frontend_rag_context": f"[RAG MEMORY - Past Solutions]\n{rag_hint}"}
        return {"frontend_errors": full_error, "frontend_rag_context": None}
    
    # RAG WRITE: if we fixed errors in a previous retry, save the solution
    if state.get("retry_count", 0) > 0 and state.get("frontend_errors"):
        prev_error = state["frontend_errors"]
        _chromadb_add_fix(prev_error, "Frontend code fixed after retry via linter feedback")
        print("[Frontend Critic/RAG] Fix saved to RAG memory")
    
    # Record episode
    episodic_buffer.record(
        task_id=state.get("task_id"),
        node_name="frontend_critic",
        input_data={"frontend_code_len": len(raw)},
        output_data={"frontend_errors": None}
    )
    
    return {"frontend_errors": None, "frontend_rag_context": None}

def backend_critic(state: OrchestratorState):
    print("[Backend Critic] Evaluating Code...")
    # ACI/Seaclip: Move ticket to Review
    _seaclip_move_issue(state.get("kanban_backend_issue_id"), "Review")
    raw = state.get("backend_code", "")
    if not raw:
        episodic_buffer.record(
            task_id=state.get("task_id"),
            node_name="backend_critic",
            input_data={},
            output_data={"backend_errors": "Critical Error: No code generated."},
            errors="Critical Error: No code generated."
        )
        return {"backend_errors": "Critical Error: No code generated."}
    
    files = parse_xml_files(raw)
    if not files:
        print("[Backend Critic] ⚠️ Nessun tag <file> trovato. Skippo la validazione.")
        episodic_buffer.record(
            task_id=state.get("task_id"),
            node_name="backend_critic",
            input_data={"backend_code_len": len(raw)},
            output_data={"backend_errors": None},
            metadata={"skipped_no_xml": True}
        )
        return {"backend_errors": None}
    
    # Escludi file non-Python dalla valutazione
    py_files = {k: v for k, v in files.items() if k.endswith(".py")}
    if not py_files:
        episodic_buffer.record(
            task_id=state.get("task_id"),
            node_name="backend_critic",
            input_data={"backend_code_len": len(raw)},
            output_data={"backend_errors": None},
            metadata={"skipped_no_python": True}
        )
        return {"backend_errors": None}
    
    with tempfile.TemporaryDirectory() as tmp_dir:
        write_project_to_dir(py_files, tmp_dir)
        errors = run_quality_gate_on_dir(tmp_dir, "py")
        
        cg_context = ""
        if errors:
            print("[Backend Critic] Costruzione Knowledge Graph (CodeGraph) per l'errore...")
            npx = "npx.cmd" if os.name == "nt" else "npx"
            try:
                subprocess.run([npx, "--yes", "@colbymchenry/codegraph", "init", ".", "--index"], cwd=tmp_dir, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                err_summary = errors.split("\n")[0][:100]
                cg_res = subprocess.run([npx, "--yes", "@colbymchenry/codegraph", "context", err_summary], cwd=tmp_dir, capture_output=True, text=True)
                if cg_res.stdout:
                    cg_context = f"\n\n[CODEGRAPH SEMANTIC CONTEXT]\n{cg_res.stdout}"
            except Exception as e:
                print(f"[Backend Critic] ⚠️ CodeGraph query fallita: {e}")

    full_error = f"{errors}{cg_context}" if errors else None
    
    if full_error:
        # RAG READ: query ChromaDB for past solutions to these errors
        rag_hint = _chromadb_query(errors)
        
        # Record episode
        episodic_buffer.record(
            task_id=state.get("task_id"),
            node_name="backend_critic",
            input_data={"backend_code_len": len(raw)},
            output_data={"backend_errors": full_error, "rag_hint": bool(rag_hint)},
            errors=errors
        )
        
        if rag_hint:
            print("[Backend Critic/RAG] Found past solutions in memory")
            return {"backend_errors": full_error, "backend_rag_context": f"[RAG MEMORY - Past Solutions]\n{rag_hint}"}
        return {"backend_errors": full_error, "backend_rag_context": None}
    
    # RAG WRITE: if we fixed errors in a previous retry, save the solution
    if state.get("retry_count", 0) > 0 and state.get("backend_errors"):
        prev_error = state["backend_errors"]
        _chromadb_add_fix(prev_error, "Backend code fixed after retry via linter feedback")
        print("[Backend Critic/RAG] Fix saved to RAG memory")
    
    # Record episode
    episodic_buffer.record(
        task_id=state.get("task_id"),
        node_name="backend_critic",
        input_data={"backend_code_len": len(raw)},
        output_data={"backend_errors": None}
    )
    
    return {"backend_errors": None, "backend_rag_context": None}
