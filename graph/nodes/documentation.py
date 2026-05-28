"""Documentation node – generates the GitHub-ready workspace output.

Writes frontend, backend and test artefacts to disk, generates a README,
runs CodeGraph for architectural diagrams, and moves Kanban tickets to Done.
"""

import os
import subprocess
import shutil
import json
from datetime import datetime

from langchain_core.messages import SystemMessage, HumanMessage

from graph.state import OrchestratorState, PROJECT_ROOT
from graph.context import mind_llm
from graph.aci import _seaclip_move_issue
from graph.utils import parse_xml_files, write_project_to_dir, extract_code
from swarm_mind import EpisodicBuffer

# Initialize episodic buffer
episodic_buffer = EpisodicBuffer()


def documentation_node(state: OrchestratorState):
    print("[Documentation Node] Creating GitHub-ready workspace...")
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    workspace_root = os.path.join(PROJECT_ROOT, "workspace", f"project_{timestamp}")
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
        
    # --- Salva Unit Tests ---
    t_files = state.get("test_files", {})
    if t_files:
        write_project_to_dir(t_files, backend_dir)
        print(f"[Documentation Node] ✅ Unit Tests: {len(t_files)} file(s) scritti in {backend_dir}")
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
    
    # Salva REQUIREMENTS.json
    if state.get("requirements_json"):
        with open(os.path.join(workspace_root, "REQUIREMENTS.json"), "w", encoding="utf-8") as f:
            f.write(state["requirements_json"])
            
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
        if state.get("requirements_json"):
            f.write("  REQUIREMENTS.json # Software Requirements (FR & NFR)\n")
        if has_uml:
            f.write("  architecture_uml.png  # ACI-generated UML diagram\n")
        f.write("  CODEGRAPH_ARCHITECTURE.md # Diagramma generato via CodeGraph\n")
        f.write("```\n")
        
    # ── CodeGraph Architecture Generation ──
    print("[Documentation Node] Running CodeGraph to generate architectural overview...")
    npx = "npx.cmd" if os.name == "nt" else "npx"
    try:
        subprocess.run([npx, "--yes", "@colbymchenry/codegraph", "init", ".", "--index"], cwd=workspace_root, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        res_files = subprocess.run([npx, "--yes", "@colbymchenry/codegraph", "files"], cwd=workspace_root, capture_output=True, text=True)
        res_ctx = subprocess.run([npx, "--yes", "@colbymchenry/codegraph", "context", "Explain project architecture"], cwd=workspace_root, capture_output=True, text=True)
        
        cg_output = f"Files:\n{res_files.stdout}\n\nContext:\n{res_ctx.stdout}"
        sys_msg = SystemMessage(content="You are an expert software architect. Given the following CodeGraph output of a project, generate a Mermaid class diagram or flowchart summarizing the architecture. Output ONLY the raw markdown with ```mermaid ... ``` without other text.")
        hum_msg = HumanMessage(content=cg_output)
        
        cg_resp = mind_llm.invoke([sys_msg, hum_msg])
        mermaid_code = extract_code(cg_resp.content)
        
        if mermaid_code:
            with open(os.path.join(workspace_root, "CODEGRAPH_ARCHITECTURE.md"), "w", encoding="utf-8") as f:
                f.write(f"# CodeGraph Architectural Map\n\n```mermaid\n{mermaid_code}\n```\n")
            print("[Documentation Node] ✅ CodeGraph architecture diagram generated in CODEGRAPH_ARCHITECTURE.md")
    except Exception as e:
        print(f"[Documentation Node] ⚠️ Failed to generate CodeGraph architecture: {e}")
    
    # ── ACI/Seaclip: Move both tickets to Done ──
    _seaclip_move_issue(state.get("kanban_frontend_issue_id"), "Done")
    _seaclip_move_issue(state.get("kanban_backend_issue_id"), "Done")
    print("[Documentation Node] 📋 Kanban: Both tickets moved to Done")
    
    print(f"\n[Documentation Node] Workspace pronto: {workspace_root}")
    
    # Record episode
    episodic_buffer.record(
        task_id=state.get("task_id"),
        node_name="documentation_node",
        input_data={
            "frontend_code_len": len(f_raw),
            "backend_code_len": len(b_raw),
            "test_files_count": len(t_files)
        },
        output_data={
            "workspace_root": workspace_root,
            "documentation_ready": True
        }
    )
    
    return {"documentation_path": workspace_root, "documentation_ready": True}
