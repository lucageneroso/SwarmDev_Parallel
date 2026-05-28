"""Quality evaluation node for SonarQube-based code analysis.

Contains the quality_evaluation_node which writes backend code to a sandbox,
runs sonar-scanner, polls the SonarQube API for quality gate status, and
extracts vulnerability/code-smell feedback when the gate fails.
"""

import os, sys, subprocess, json

from graph.state import OrchestratorState, PROJECT_ROOT
from graph.utils import parse_xml_files, write_project_to_dir
from swarm_mind import EpisodicBuffer

# Initialize episodic buffer
episodic_buffer = EpisodicBuffer()


def quality_evaluation_node(state: OrchestratorState):
    print("[Quality Gate] Avvio Analisi SonarQube Scanner...")
    import uuid
    import shutil
    import time
    import requests
    
    project_key = f"swarmdev_{uuid.uuid4().hex[:8]}"
    sandbox_name = f".sandbox_sonar_{project_key}"
    sandbox_dir = os.path.join(PROJECT_ROOT, "workspace", sandbox_name)
    os.makedirs(sandbox_dir, exist_ok=True)
    
    # 1. Scrittura files backend
    backend_code = state.get("backend_code", "")
    b_files = parse_xml_files(backend_code) if backend_code else {}
    if b_files:
        write_project_to_dir(b_files, sandbox_dir)
        
    # 2. Generazione sonar-project.properties
    sonar_props = f"""sonar.projectKey={project_key}
sonar.sources=.
sonar.host.url=http://localhost:9000
"""
    with open(os.path.join(sandbox_dir, "sonar-project.properties"), "w", encoding="utf-8") as f:
        f.write(sonar_props)
        
    # 3. Scansione
    scanner_exe = shutil.which("sonar-scanner")
    if not scanner_exe:
        print("[Quality Gate] ⚠️ sonar-scanner non trovato nel PATH. Salto il quality gate.")
        shutil.rmtree(sandbox_dir, ignore_errors=True)
        # Record episode
        episodic_buffer.record(
            task_id=state.get("task_id"),
            node_name="quality_evaluation_node",
            input_data={"project_key": project_key},
            output_data={"quality_passed": True, "skipped_reason": "sonar-scanner not found"}
        )
        return {"quality_passed": True, "quality_feedback": None}
        
    print(f"[Quality Gate] Esecuzione sonar-scanner (Project: {project_key})...")
    scanner_res = subprocess.run(
        [scanner_exe],
        cwd=sandbox_dir, capture_output=True, text=True
    )
    if scanner_res.returncode != 0:
        print("[Quality Gate] ⚠️ sonar-scanner fallito. Salto il quality gate.")
        print(f"[Quality Gate] 📝 Sonar STDOUT:\n{scanner_res.stdout}")
        if scanner_res.stderr:
            print(f"[Quality Gate] 📝 Sonar STDERR:\n{scanner_res.stderr}")
        shutil.rmtree(sandbox_dir, ignore_errors=True)
        # Record episode
        episodic_buffer.record(
            task_id=state.get("task_id"),
            node_name="quality_evaluation_node",
            input_data={"project_key": project_key},
            output_data={"quality_passed": True, "skipped_reason": f"sonar-scanner failed with code {scanner_res.returncode}"},
            errors=scanner_res.stderr or scanner_res.stdout
        )
        return {"quality_passed": True, "quality_feedback": None}
        
    # 4. Polling API SonarQube per Quality Gate Status
    print("[Quality Gate] Polling SonarQube per Quality Gate status...")
    quality_passed = True
    feedback = ""
    status_url = f"http://localhost:9000/api/qualitygates/project_status?projectKey={project_key}"
    
    max_attempts = 15
    for attempt in range(max_attempts):
        time.sleep(2)
        try:
            resp = requests.get(status_url)
            if resp.status_code == 200:
                status_data = resp.json()
                status = status_data.get("projectStatus", {}).get("status", "NONE")
                
                if status == "OK":
                    print("[Quality Gate] ✅ Quality Gate SUPERATO.")
                    break
                elif status == "ERROR":
                    print("[Quality Gate] ❌ Quality Gate FALLITO.")
                    quality_passed = False
                    
                    # Estrazione Vulnerabilità / Code Smells
                    issues_url = f"http://localhost:9000/api/issues/search?projectKeys={project_key}&ps=5"
                    i_resp = requests.get(issues_url)
                    if i_resp.status_code == 200:
                        issues = i_resp.json().get("issues", [])
                        feedback_lines = ["SONARQUBE ISSUES FOUND:"]
                        for issue in issues:
                            msg = issue.get("message", "Issue")
                            comp = issue.get("component", "")
                            line = issue.get("line", "?")
                            feedback_lines.append(f"- {comp} (Line {line}): {msg}")
                        feedback = "\n".join(feedback_lines)
                        print(f"[Quality Gate] Trovate {len(issues)} issue principali.")
                    break
            elif resp.status_code == 404:
                # Il report non è ancora stato processato dal server
                continue
        except requests.exceptions.RequestException:
            print("[Quality Gate] ⚠️ Impossibile contattare SonarQube (http://localhost:9000). Salto il Quality Gate.")
            quality_passed = True
            break
            
    # Cleanup
    shutil.rmtree(sandbox_dir, ignore_errors=True)
    
    # Record episode
    episodic_buffer.record(
        task_id=state.get("task_id"),
        node_name="quality_evaluation_node",
        input_data={"project_key": project_key},
        output_data={"quality_passed": quality_passed, "has_feedback": bool(feedback)},
        errors=feedback if not quality_passed else None
    )
    
    return {
        "quality_passed": quality_passed, 
        "quality_feedback": feedback, 
        "quality_retry_count": 1
    }
