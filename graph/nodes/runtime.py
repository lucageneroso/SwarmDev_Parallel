"""Runtime self-healing node – launches the generated backend via PM2.

Installs dependencies, starts the backend process through PM2, waits for it
to stabilise, inspects logs for runtime crashes, and feeds errors back into
the retry loop when needed.
"""

import os
import sys
import subprocess

from graph.state import OrchestratorState, RUNTIME_WAIT_SECONDS
from graph.aci import _seaclip_move_issue, _pm2_start, _pm2_get_logs, _pm2_stop, _extract_runtime_errors
from swarm_mind import EpisodicBuffer

# Initialize episodic buffer
episodic_buffer = EpisodicBuffer()


def runtime_execution_node(state: OrchestratorState):
    """Launch the generated backend via PM2, check logs for runtime crashes."""
    print("[Runtime Node] Launching backend via PM2 for runtime validation...")
    
    # ACI/Seaclip: Move backend ticket to Testing
    _seaclip_move_issue(state.get("kanban_backend_issue_id"), "Testing")
    
    doc_path = state.get("documentation_path", "")
    if not doc_path:
        print("[Runtime Node] No documentation_path, skipping runtime check")
        episodic_buffer.record(
            task_id=state.get("task_id"),
            node_name="runtime_execution_node",
            input_data={},
            output_data={"runtime_errors": None},
            metadata={"skipped_no_doc_path": True}
        )
        return {"runtime_errors": None}
    
    backend_dir = os.path.join(doc_path, "backend")
    
    # Zero Trust: LLM might put main.py in root or in app/
    main_py = os.path.join(backend_dir, "main.py")
    if not os.path.exists(main_py):
        main_py = os.path.join(backend_dir, "app", "main.py")
    
    if not os.path.exists(main_py):
        print(f"[Runtime Node] Entry point non trovato in {backend_dir} o {os.path.join(backend_dir, 'app')}, skippando runtime check")
        episodic_buffer.record(
            task_id=state.get("task_id"),
            node_name="runtime_execution_node",
            input_data={"backend_dir": backend_dir},
            output_data={"runtime_errors": None},
            metadata={"skipped_no_entrypoint": True}
        )
        return {"runtime_errors": None}
        
    # Iniezione PYTHONPATH a livello OS per risolvere from app.routes
    os.environ["PYTHONPATH"] = backend_dir
    
    # Step 1: Ephemeral Environment Provisioning (pip install)
    requirements_txt = os.path.join(backend_dir, "requirements.txt")
    if os.path.exists(requirements_txt):
        print("[Runtime Node] 📦 Installing dependencies from requirements.txt...")
        pip_result = subprocess.run(
            [sys.executable, "-m", "pip", "install", "-r", requirements_txt, "--quiet"],
            capture_output=True, text=True, timeout=120,
        )
        if pip_result.returncode != 0:
            pip_error = pip_result.stderr.strip() or pip_result.stdout.strip()
            print(f"[Runtime Node] ❌ Pip install FAILED:\n{pip_error[:300]}")
            episodic_buffer.record(
                task_id=state.get("task_id"),
                node_name="runtime_execution_node",
                input_data={"main_py": main_py},
                output_data={
                    "runtime_errors": pip_error,
                    "backend_errors": f"DEPENDENCY INSTALL FAILED (pip):\n{pip_error}"
                },
                errors=pip_error
            )
            return {
                "runtime_errors": pip_error,
                "backend_errors": f"DEPENDENCY INSTALL FAILED (pip):\n{pip_error}",
                "runtime_retry_count": 1,
            }
        print("[Runtime Node] ✅ Dependencies installed successfully")
    else:
        print("[Runtime Node] ⚠️ No requirements.txt found — skipping pip install")
    
    # Prepare environment with PYTHONPATH for absolute imports
    env = os.environ.copy()
    env["PYTHONPATH"] = backend_dir
    
    pm2_name = f"backend_{os.path.basename(doc_path)}"
    
    # Step 2: Start the process via PM2 (with venv interpreter)
    started = _pm2_start(
        main_py,
        name=pm2_name,
        interpreter=sys.executable,
        cwd=backend_dir,
        env=env
    )
    if not started:
        print("[Runtime Node] PM2 start failed (non-blocking, PM2 may not be installed)")
        episodic_buffer.record(
            task_id=state.get("task_id"),
            node_name="runtime_execution_node",
            input_data={"main_py": main_py},
            output_data={"runtime_errors": None},
            metadata={"pm2_start_failed": True}
        )
        return {"runtime_errors": None}
    
    # Step 3: Wait for the server to stabilize
    import time
    print(f"[Runtime Node] Waiting {RUNTIME_WAIT_SECONDS}s for process to stabilize...")
    time.sleep(RUNTIME_WAIT_SECONDS)
    
    # Step 3: Read logs
    logs = _pm2_get_logs(pm2_name, lines=30)
    
    # Step 4: Analyze for runtime errors
    if logs:
        runtime_errs = _extract_runtime_errors(logs)
        if runtime_errs:
            print(f"[Runtime Node] Runtime errors detected:\n{runtime_errs[:300]}")
            _pm2_stop(pm2_name)
            episodic_buffer.record(
                task_id=state.get("task_id"),
                node_name="runtime_execution_node",
                input_data={"main_py": main_py},
                output_data={
                    "runtime_errors": runtime_errs,
                    "backend_errors": f"RUNTIME CRASH (from PM2 logs):\n{runtime_errs}"
                },
                errors=runtime_errs
            )
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
    _pm2_stop(pm2_name)
    
    # ACI/Seaclip: Move backend ticket to Done (runtime passed)
    _seaclip_move_issue(state.get("kanban_backend_issue_id"), "Done")
    print("[Runtime Node] Runtime validation PASSED")
    episodic_buffer.record(
        task_id=state.get("task_id"),
        node_name="runtime_execution_node",
        input_data={"main_py": main_py},
        output_data={"runtime_errors": None}
    )
    return {"runtime_errors": None}
