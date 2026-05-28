import os
import sys
import json
from dotenv import load_dotenv
from langgraph.graph import StateGraph, END

# Ensure current directory is in the path
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
if CURRENT_DIR not in sys.path:
    sys.path.append(CURRENT_DIR)

load_dotenv()

# Import state
from graph.state import OrchestratorState

# Import nodes
from graph.nodes.mind import (
    human_node,
    discovery_node,
    planning_node,
    validate_ocl_node,
    requirements_node,
    fanout_node,
)
from graph.nodes.actors import (
    frontend_actor,
    backend_actor,
)
from graph.nodes.critics import (
    frontend_critic,
    backend_critic,
)
from graph.nodes.testing import (
    test_writer_actor,
    test_evaluator_node,
)
from graph.nodes.quality import (
    quality_evaluation_node,
)
from graph.nodes.documentation import (
    documentation_node,
)
from graph.nodes.runtime import (
    runtime_execution_node,
)
from graph.nodes.consolidation import (
    consolidation_node,
)
from graph.nodes.familiarity import (
    familiarity_check_node,
)

# Import routers
from graph.routing import (
    router_discovery,
    router_ocl,
    routing_node,
    conditional_router,
    test_router,
    quality_router,
    runtime_router,
)
from graph.context import mind_model_name, llm_model


# ============================================================================
# BUILD AND COMPILE GRAPH
# ============================================================================
def build_orchestrator() -> StateGraph:
    workflow = StateGraph(OrchestratorState)
    
    # 1. Mind Nodes
    workflow.add_node("human_node", human_node)
    workflow.add_node("discovery_node", discovery_node)
    workflow.add_node("familiarity_check_node", familiarity_check_node)
    workflow.add_node("planning_node", planning_node)
    workflow.add_node("validate_ocl_node", validate_ocl_node)
    workflow.add_node("requirements_node", requirements_node) # V4.0
    workflow.add_node("fanout_node", fanout_node)
    
    # 2. Worker Nodes
    workflow.add_node("frontend_actor", frontend_actor)
    workflow.add_node("backend_actor", backend_actor)
    workflow.add_node("frontend_critic", frontend_critic)
    workflow.add_node("backend_critic", backend_critic)
    workflow.add_node("routing_node", routing_node)
    
    # 3. V4.0 CI/CD Nodes
    workflow.add_node("test_writer_actor", test_writer_actor)
    workflow.add_node("test_evaluator_node", test_evaluator_node)
    workflow.add_node("quality_evaluation_node", quality_evaluation_node)
    
    # 4. Post-Processing Nodes
    workflow.add_node("documentation_node", documentation_node)
    workflow.add_node("runtime_execution_node", runtime_execution_node)
    workflow.add_node("consolidation_node", consolidation_node)
    
    # --- MIND ROUTING ---
    workflow.set_entry_point("human_node")
    workflow.add_edge("human_node", "discovery_node")
    
    workflow.add_conditional_edges("discovery_node", router_discovery, {
        "human_node": "human_node",
        "planning_node": "familiarity_check_node"
    })
    
    workflow.add_edge("familiarity_check_node", "planning_node")
    
    workflow.add_edge("planning_node", "validate_ocl_node")
    workflow.add_conditional_edges("validate_ocl_node", router_ocl, {
        "planning_node": "planning_node",
        "fanout_node": "requirements_node" # V4.0 intercept
    })
    
    workflow.add_edge("requirements_node", "fanout_node") # V4.0
    
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
            "documentation_node": "test_writer_actor", # V4.0 intercept
            "consolidation_node": "consolidation_node"
        }
    )
    
    # --- V4.0 CI/CD ROUTING ---
    workflow.add_edge("test_writer_actor", "test_evaluator_node")
    workflow.add_conditional_edges(
        "test_evaluator_node",
        test_router,
        {
            "test_writer_actor": "test_writer_actor",
            "quality_evaluation_node": "quality_evaluation_node"
        }
    )
    
    workflow.add_conditional_edges(
        "quality_evaluation_node",
        quality_router,
        {
            "backend_actor": "backend_actor",
            "documentation_node": "documentation_node"
        }
    )
    
    # --- RUNTIME SELF-HEALING ---
    workflow.add_edge("documentation_node", "runtime_execution_node")
    
    workflow.add_conditional_edges(
        "runtime_execution_node",
        runtime_router,
        {
            "backend_actor": "backend_actor",
            "consolidation_node": "consolidation_node",
        }
    )
    
    workflow.add_edge("consolidation_node", END)
    
    return workflow.compile()


def ensure_services_running():
    import socket
    import subprocess
    import time
    
    print("\n" + "="*53)
    print("🚀 Verifica Servizi Infrastrutturali in corso...")
    print("="*53)

    def check_port(port: int, host="127.0.0.1") -> bool:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(1)
            return s.connect_ex((host, port)) == 0

    # 1. SeaClip
    if not check_port(5200):
        print("[-] Avvio SeaClip-Lite (Porta 5200)...")
        seaclip_script = os.path.join(CURRENT_DIR, "seaclip_server", "main.py")
        subprocess.Popen([sys.executable, seaclip_script], 
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(2)
        if check_port(5200):
            print("[✓] SeaClip-Lite avviato.")
        else:
            print("[!] Errore avvio SeaClip-Lite.")
    else:
        print("[✓] SeaClip-Lite già in esecuzione.")

    # 2. ChromaDB
    if not check_port(8000):
        print("[-] Avvio ChromaDB via Docker (Porta 8000)...")
        try:
            res = subprocess.run('docker ps -a -q --filter ancestor=chromadb/chroma', shell=True, capture_output=True, text=True)
            container_id = res.stdout.strip().split('\n')[0]
            if container_id:
                subprocess.run(['docker', 'start', container_id], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            else:
                subprocess.run(["docker", "run", "-d", "-p", "8000:8000", "chromadb/chroma"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            time.sleep(3)
        except Exception:
            pass
        if check_port(8000):
            print("[✓] ChromaDB avviato.")
        else:
            print("[!] Errore avvio ChromaDB.")
    else:
        print("[✓] ChromaDB già in esecuzione.")

    # 3. SonarQube
    if not check_port(9000):
        print("[-] Avvio SonarQube via Docker (Porta 9000)...")
        try:
            res = subprocess.run('docker ps -a -q --filter ancestor=sonarqube', shell=True, capture_output=True, text=True)
            container_id = res.stdout.strip().split('\n')[0]
            if container_id:
                subprocess.run(['docker', 'start', container_id], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            else:
                subprocess.run(["docker", "run", "-d", "-p", "9000:9000", "sonarqube:lts"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            
            print("[-] Attendo avvio SonarQube (potrebbe richiedere 10-15s)...")
            for _ in range(15):
                if check_port(9000): break
                time.sleep(1)
        except Exception:
            pass
        if check_port(9000):
            print("[✓] SonarQube avviato.")
        else:
            print("[!] Errore avvio SonarQube.")
    else:
        print("[✓] SonarQube già in esecuzione.")
    
    print("="*53 + "\n")


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
    
    ensure_services_running()
    
    orchestrator = build_orchestrator()
    
    import uuid
    task_id = f"task_{uuid.uuid4().hex[:12]}"
    
    initial_state = {
        "task_id": task_id,
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
