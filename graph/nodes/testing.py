"""Testing nodes for unit test generation and sandbox evaluation.

Contains the test_writer_actor (LLM-based test generation) and
test_evaluator_node (pytest sandbox execution with coverage reporting).
"""

import os, sys, subprocess, json

from langchain_core.messages import SystemMessage
from llm_wiki import load_sop
from graph.state import OrchestratorState, PROJECT_ROOT
from graph.context import worker_llm
from graph.utils import parse_xml_files, write_project_to_dir
from swarm_mind import EpisodicBuffer

# Initialize episodic buffer
episodic_buffer = EpisodicBuffer()


def test_writer_actor(state: OrchestratorState):
    print("[Testing Swarm] Generazione Unit Tests...")
    backend_code = state.get("backend_code", "")
    requirements = state.get("requirements_json", "")
    feedback = state.get("test_feedback", "")
    
    sys_msg = SystemMessage(content=load_sop(
        "test_writer_actor", 
        backend_code=backend_code, 
        requirements=requirements,
        test_feedback=feedback
    ))
    
    response = worker_llm.invoke([sys_msg])
    
    tokens = 0
    if hasattr(response, 'usage_metadata') and response.usage_metadata:
        tokens = response.usage_metadata.get('total_tokens', 0)
        
    test_files = parse_xml_files(response.content)
    if not test_files:
        print("[Testing Swarm] ⚠️ Nessun file XML di test generato dall'LLM.")
        
    print(f"[Testing Swarm] ✅ Generati {len(test_files)} file di test.")
    
    # Record episode
    episodic_buffer.record(
        task_id=state.get("task_id"),
        node_name="test_writer_actor",
        input_data={"has_feedback": bool(feedback)},
        output_data={"test_files_count": len(test_files)},
        metadata={"total_tokens": tokens}
    )
    
    return {"test_files": test_files, "total_tokens": tokens}

def test_evaluator_node(state: OrchestratorState):
    print("[Testing Swarm] Esecuzione Sandbox Pytest --cov...")
    import uuid
    import shutil
    
    sandbox_name = f".sandbox_test_{uuid.uuid4().hex[:8]}"
    sandbox_dir = os.path.join(PROJECT_ROOT, "workspace", sandbox_name)
    os.makedirs(sandbox_dir, exist_ok=True)
    
    # 1. Scrittura files backend e test
    backend_code = state.get("backend_code", "")
    b_files = parse_xml_files(backend_code) if backend_code else {}
    test_files = state.get("test_files", {})
    
    if b_files:
        write_project_to_dir(b_files, sandbox_dir)
    if test_files:
        write_project_to_dir(test_files, sandbox_dir)
        
    # 2. Installazione dipendenze
    req_path = os.path.join(sandbox_dir, "requirements.txt")
    if os.path.exists(req_path):
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "-r", req_path, "pytest", "pytest-cov", "httpx", "--quiet"],
            capture_output=True, timeout=120
        )
    else:
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "pytest", "pytest-cov", "httpx", "fastapi", "uvicorn", "--quiet"],
            capture_output=True, timeout=120
        )
        
    # 3. Esecuzione pytest con iniezione PYTHONPATH
    env = os.environ.copy()
    env["PYTHONPATH"] = sandbox_dir
    
    print("[Testing Swarm] Avvio pytest...")
    cov_target = "app" if os.path.exists(os.path.join(sandbox_dir, "app")) else "."
    
    pytest_res = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/", f"--cov={cov_target}", "--cov-report=json"],
        cwd=sandbox_dir, env=env, capture_output=True, text=True
    )
    
    coverage_val = 0.0
    feedback = ""
    
    # 4. Lettura coverage.json
    cov_file = os.path.join(sandbox_dir, "coverage.json")
    if os.path.exists(cov_file):
        try:
            with open(cov_file, "r", encoding="utf-8") as f:
                cov_data = json.load(f)
            coverage_val = cov_data.get("totals", {}).get("percent_covered_display", 0.0)
            coverage_val = float(coverage_val)
            
            # Extract uncovered files
            missing_files = []
            files = cov_data.get("files", {})
            for fname, fdata in files.items():
                missing = fdata.get("missing_lines", [])
                if missing:
                    missing_files.append(f"{fname}: missing lines {missing}")
            if missing_files:
                feedback = "Uncovered lines:\n" + "\n".join(missing_files)
        except Exception as e:
            print(f"[Testing Swarm] Errore lettura coverage.json: {e}")
            feedback = f"Pytest Output:\n{pytest_res.stdout}\n{pytest_res.stderr}"
    else:
        print("[Testing Swarm] ⚠️ coverage.json non generato. Pytest ha fallito la collection o l'import?")
        print(f"[Testing Swarm] 📝 Pytest STDOUT:\n{pytest_res.stdout}")
        if pytest_res.stderr:
            print(f"[Testing Swarm] 📝 Pytest STDERR:\n{pytest_res.stderr}")
        feedback = f"Pytest Output:\n{pytest_res.stdout}\n{pytest_res.stderr}"
        
    print(f"[Testing Swarm] Coverage calcolata: {coverage_val}%")
    
    # Effimero: eliminiamo la sandbox
    shutil.rmtree(sandbox_dir, ignore_errors=True)
    
    # Record episode
    episodic_buffer.record(
        task_id=state.get("task_id"),
        node_name="test_evaluator_node",
        input_data={"test_files_count": len(state.get("test_files", {}))},
        output_data={"test_coverage": coverage_val, "has_feedback": bool(feedback)},
        errors=feedback if coverage_val < 85 else None
    )
    
    return {"test_coverage": coverage_val, "test_feedback": feedback, "test_retry_count": 1}
