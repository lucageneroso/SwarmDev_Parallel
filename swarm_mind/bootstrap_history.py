import sys
import os
# Aggiunge la root del progetto al path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
from graph.aci import _chromadb_add_fix, _chromadb_ensure_collection


def bootstrap_historical_projects():
    print("[Swarm Mind/Bootstrap] Avvio caricamento dei progetti storici in ChromaDB...")
    
    # Assicura che la collezione esista
    _chromadb_ensure_collection()
    
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(current_dir)
    workspace_dir = os.path.join(project_root, "workspace")
    
    if not os.path.exists(workspace_dir):
        print(f"[Swarm Mind/Bootstrap] Cartella workspace non trovata a: {workspace_dir}")
        return
        
    project_dirs = []
    for item in os.listdir(workspace_dir):
        item_path = os.path.join(workspace_dir, item)
        if os.path.isdir(item_path):
            # Esclude cartelle di sistema o nascoste
            if item.startswith(".") or item in ["memory", "codegraph_repo", "__pycache__"]:
                continue
            if os.path.exists(os.path.join(item_path, "DESIGN.md")):
                project_dirs.append(item_path)
                
    print(f"[Swarm Mind/Bootstrap] Trovati {len(project_dirs)} progetti candidati per il bootstrap.")
    
    success_count = 0
    for p_dir in project_dirs:
        p_name = os.path.basename(p_dir)
        try:
            # Legge DESIGN.md
            design_path = os.path.join(p_dir, "DESIGN.md")
            with open(design_path, "r", encoding="utf-8") as f:
                design_content = f.read().strip()
                
            # Legge CONTRACT.json
            contract_path = os.path.join(p_dir, "CONTRACT.json")
            contract_summary = ""
            if os.path.exists(contract_path):
                with open(contract_path, "r", encoding="utf-8") as f:
                    try:
                        contract_data = json.load(f)
                        fe_req = contract_data.get("frontend_requirements", "")
                        be_req = contract_data.get("backend_requirements", "")
                        ocl = contract_data.get("a2a_ocl_constraints", [])
                        
                        contract_summary = f"Frontend: {fe_req[:200]}...\nBackend: {be_req[:200]}...\nOCL: {', '.join(ocl)[:200]}"
                    except Exception:
                        f.seek(0)
                        contract_summary = f.read()[:500]
            else:
                contract_summary = "Soluzione di design completata con successo."
                
            # Formatta per ChromaDB
            error_trigger = f"Requisiti di Design per {p_name}:\n{design_content[:300]}"
            solution = f"Soluzione architetturale stabilita:\n{contract_summary}"
            
            # Metadati per il record storico
            metadata = {
                "source": "historical_bootstrap",
                "project_name": p_name,
                "uses_count": 1,
                "failures_count": 0,
            }
            
            saved = _chromadb_add_fix(error_trigger, solution, metadata=metadata)
            if saved:
                success_count += 1
                print(f"[Swarm Mind/Bootstrap] [OK] Progetto '{p_name}' importato con successo.")
            else:
                print(f"[Swarm Mind/Bootstrap] [ERRORE] Errore durante l'importazione di '{p_name}'.")
                
        except Exception as e:
            print(f"[Swarm Mind/Bootstrap] [ECCEZIONE] Eccezione nell'importazione di '{p_name}': {e}")
            
    print(f"[Swarm Mind/Bootstrap] Completato! Importati {success_count}/{len(project_dirs)} progetti in ChromaDB.")


if __name__ == "__main__":
    bootstrap_historical_projects()
