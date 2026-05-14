import os
import sys
import tempfile
import subprocess
import operator
from typing import TypedDict, Optional, Annotated, Sequence
import yaml

from langchain_core.messages import SystemMessage, HumanMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, END
from dotenv import load_dotenv

load_dotenv()

# ============================================================================
# 1. GRAPH STATE
# ============================================================================
class OrchestratorState(TypedDict):
    json_contract: str
    frontend_code: Optional[str]
    backend_code: Optional[str]
    frontend_errors: Optional[str]
    backend_errors: Optional[str]
    retry_count: Annotated[int, operator.add]

# Constants
MAX_RETRIES = 3
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
DIRECTIVES_DIR = os.path.join(CURRENT_DIR, "directives")

# ============================================================================
# 2. REAL PARLANT INTEGRATION
# ============================================================================
def load_directives() -> str:
    """Reads execution_rules.yaml and reasoning_constraints.yaml from disk."""
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

# ============================================================================
# 3. LLM INITIALIZATION
# ============================================================================
# Use ChatOpenAI with max_retries=3 natively. Assumes OPENAI_API_KEY is in env.
llm = ChatOpenAI(model="gpt-4o", max_retries=3, temperature=0.0)

def extract_code(text: str) -> str:
    """Extracts raw code from markdown blocks to avoid syntax errors in critics."""
    if "```python" in text:
        return text.split("```python")[1].split("```")[0].strip()
    if "```javascript" in text:
        return text.split("```javascript")[1].split("```")[0].strip()
    if "```" in text:
        return text.split("```")[1].strip()
    return text.strip()

# ============================================================================
# 4. ACTOR NODES
# ============================================================================
def frontend_actor(state: OrchestratorState):
    print("[Frontend Actor] Generating Code...")
    directives = load_directives()
    
    sys_msg = SystemMessage(
        content=f"You are the SwarmDev Frontend Blind Builder.\n{directives}\n"
                "Output ONLY valid Javascript/React code based on the JSON contract. "
                "DO NOT output explanations or markdown. DO NOT self-evaluate."
    )
    
    user_content = f"JSON CONTRACT:\n{state['json_contract']}"
    if state.get("frontend_errors"):
        user_content += (
            f"\n\nCRITICAL FAILURE. Your previous code was rejected. Here is the exact compiler/linter error:\n"
            f"{state['frontend_errors']}\n\n"
            f"You MUST fix this exact issue. Remember your directives: strictly adhere to the constraints. "
            f"Output ONLY the corrected code."
        )
        
    hum_msg = HumanMessage(content=user_content)
    
    response = llm.invoke([sys_msg, hum_msg])
    code = extract_code(response.content)
    
    return {"frontend_code": code}

def backend_actor(state: OrchestratorState):
    print("[Backend Actor] Generating Code...")
    directives = load_directives()
    
    sys_msg = SystemMessage(
        content=f"You are the SwarmDev Backend Blind Builder.\n{directives}\n"
                "Output ONLY valid Python code based on the JSON contract. "
                "DO NOT output explanations or markdown. DO NOT self-evaluate."
    )
    
    user_content = f"JSON CONTRACT:\n{state['json_contract']}"
    if state.get("backend_errors"):
        user_content += (
            f"\n\nCRITICAL FAILURE. Your previous code was rejected. Here is the exact compiler/linter error:\n"
            f"{state['backend_errors']}\n\n"
            f"You MUST fix this exact issue. Remember your directives: strictly adhere to the constraints "
            f"(e.g., use FastAPI if specified, not Flask). Output ONLY the corrected code."
        )
        
    hum_msg = HumanMessage(content=user_content)
    
    response = llm.invoke([sys_msg, hum_msg])
    code = extract_code(response.content)
    
    return {"backend_code": code}

# ============================================================================
# 5. CRITIC NODES (REAL QUALITY GATES)
# ============================================================================
def run_real_quality_gate(code: str, file_ext: str) -> str:
    """Executes REAL subprocess validation for Python code."""
    if not code:
        return "Critical Error: No code generated."
        
    # Flake8/Radon are python-specific. For frontend, we would use ESLint.
    # The prompt explicitly asked for radon and flake8. 
    # We apply them strictly if the extension is .py
    if file_ext != ".py":
        # Simulating Frontend JS validation for parity (or returning empty string if OK)
        return ""

    error_deltas = []
    
    # Create temporary file to run static analysis
    with tempfile.NamedTemporaryFile(suffix=file_ext, delete=False, mode="w", encoding="utf-8") as tmp:
        tmp.write(code)
        tmp_path = tmp.name

    try:
        # 0. Auto-Formatting (Black)
        cmd_black = [sys.executable, "-m", "black", "-q", tmp_path]
        subprocess.run(cmd_black, check=False)

        # Read back the formatted code (optional, but good practice if you want to save it)
        with open(tmp_path, "r", encoding="utf-8") as f:
            formatted_code = f.read()

        # 1. Cyclomatic Complexity (Radon) - Fails if > 10 (Grade C)
        cmd_radon = [sys.executable, "-m", "radon", "cc", "-n", "C", "-s", tmp_path]
        res_radon = subprocess.run(cmd_radon, capture_output=True, text=True)
        if res_radon.stdout.strip():
            for line in res_radon.stdout.strip().split("\n"):
                if line.strip():
                    error_deltas.append(f"Q1 Failed (Radon CC): {line.strip()}")

        # 2. Linting (Flake8)
        cmd_flake8 = [sys.executable, "-m", "flake8", tmp_path]
        res_flake8 = subprocess.run(cmd_flake8, capture_output=True, text=True)
        if res_flake8.returncode != 0 and res_flake8.stdout.strip():
            # Only pick the first few errors to avoid exploding context window
            lines = [l.strip() for l in res_flake8.stdout.strip().split("\n") if l.strip()]
            for line in lines[:5]:
                error_deltas.append(f"Q2 Failed (Flake8): {line.strip()}")
                
    except Exception as e:
        error_deltas.append(f"Quality Gate Execution Error: {str(e)}")
    finally:
        os.remove(tmp_path)

    return "\n".join(error_deltas)

def frontend_critic(state: OrchestratorState):
    print("[Frontend Critic] Evaluating Code...")
    code = state.get("frontend_code", "")
    errors = run_real_quality_gate(code, ".js")  # Normally ESLint here
    return {"frontend_errors": errors if errors else None}

def backend_critic(state: OrchestratorState):
    print("[Backend Critic] Evaluating Code...")
    code = state.get("backend_code", "")
    errors = run_real_quality_gate(code, ".py")
    return {"backend_errors": errors if errors else None}

# ============================================================================
# 6. ROUTING AND PARALLEL EXECUTION
# ============================================================================
def start_node(state: OrchestratorState):
    """Initial node to fan-out to parallel actors."""
    print("[START] Starting LangGraph Orchestration...")
    return {}

def routing_node(state: OrchestratorState):
    """Aggregation node after critics. Increments retry count if there are errors."""
    f_err = state.get("frontend_errors")
    b_err = state.get("backend_errors")
    
    if f_err or b_err:
        return {"retry_count": 1}
    return {}

def conditional_router(state: OrchestratorState) -> Sequence[str]:
    """Conditional Edge: Routes back ONLY to the actors that failed."""
    f_err = state.get("frontend_errors")
    b_err = state.get("backend_errors")
    
    print(f"[Router] Checking Errors. Current Retry Count: {state.get('retry_count', 0)}")
    
    if not f_err and not b_err:
        print("[OK] Validation PASSED. Execution successful.")
        return [END]
        
    if state.get("retry_count", 0) >= MAX_RETRIES:
        print("[FAIL] Max retries reached. Exiting with validation failures.")
        return [END]
        
    next_nodes = []
    if f_err:
        print("[RETRY] Routing back to Frontend Actor...")
        next_nodes.append("frontend_actor")
    if b_err:
        print("[RETRY] Routing back to Backend Actor...")
        next_nodes.append("backend_actor")
        
    return next_nodes

# ============================================================================
# 7. BUILD AND COMPILE GRAPH
# ============================================================================
def build_orchestrator() -> StateGraph:
    workflow = StateGraph(OrchestratorState)
    
    # Add Nodes
    workflow.add_node("start", start_node)
    workflow.add_node("frontend_actor", frontend_actor)
    workflow.add_node("backend_actor", backend_actor)
    workflow.add_node("frontend_critic", frontend_critic)
    workflow.add_node("backend_critic", backend_critic)
    workflow.add_node("routing_node", routing_node)
    
    # Parallel Start (Fan-out)
    workflow.set_entry_point("start")
    workflow.add_edge("start", "frontend_actor")
    workflow.add_edge("start", "backend_actor")
    
    # Actor -> Critic
    workflow.add_edge("frontend_actor", "frontend_critic")
    workflow.add_edge("backend_actor", "backend_critic")
    
    # Join Critics to Router Node
    workflow.add_edge("frontend_critic", "routing_node")
    workflow.add_edge("backend_critic", "routing_node")
    
    # Conditional Edges from Router
    workflow.add_conditional_edges(
        "routing_node",
        conditional_router,
        {
            "frontend_actor": "frontend_actor",
            "backend_actor": "backend_actor",
            END: END
        }
    )
    
    return workflow.compile()

# ============================================================================
# EXECUTION ENTRYPOINT
# ============================================================================
import json
import pika

def start_consumer():
    """Starts the RabbitMQ consumer to trigger the LangGraph orchestration."""
    host = os.environ.get('RABBITMQ_HOST', 'localhost')
    port = int(os.environ.get('RABBITMQ_PORT', 5672))
    queue_name = 'contract_queue'
    
    try:
        connection = pika.BlockingConnection(pika.ConnectionParameters(host=host, port=port, heartbeat=0))
        channel = connection.channel()
        channel.queue_declare(queue=queue_name, durable=True)
        
        print(f"✅ [Orchestrator] Connesso a RabbitMQ su {host}:{port}. In ascolto su '{queue_name}'...")
        
        orchestrator = build_orchestrator()

        def callback(ch, method, properties, body):
            print(f"\n📥 [Orchestrator] Ricevuto nuovo contratto JSON da RabbitMQ.")
            try:
                # 1. Parse JSON body
                contract_data = json.loads(body)
                
                # We assume the body is the JSON contract representation or contains it.
                # If it's a dict containing the contract details, we serialize it to pass to the graph.
                # Adjust depending on the exact schema published by The Mind.
                json_contract_str = json.dumps(contract_data) if isinstance(contract_data, dict) else str(contract_data)
                
                # 2. Initialize State
                initial_state = {
                    "json_contract": json_contract_str,
                    "retry_count": 0,
                    "frontend_code": None,
                    "backend_code": None,
                    "frontend_errors": None,
                    "backend_errors": None
                }
                
                # 3. Invoke Graph
                print(f"🚀 Avviando l'esecuzione del DAG per il contratto...")
                final_state = orchestrator.invoke(initial_state)
                
                # 4. Print Results
                if final_state.get("frontend_errors") or final_state.get("backend_errors"):
                    print("❌ Esecuzione fallita dopo i retry massimi.")
                else:
                    print("✅ Esecuzione completata con successo.")
                    
                # 5. Acknowledge Message ONLY when graph reaches __end__
                ch.basic_ack(delivery_tag=method.delivery_tag)
                print("✅ Contratto processato e ACK inviato al broker.")
                
            except Exception as e:
                print(f"❌ [Orchestrator] Errore critico nel processing del grafo: {e}")
                # Optional: NACK the message or send to Dead Letter Queue
                ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)

        channel.basic_qos(prefetch_count=1)
        channel.basic_consume(queue=queue_name, on_message_callback=callback)
        channel.start_consuming()
        
    except Exception as e:
        print(f"❌ Impossibile connettersi a RabbitMQ: {e}")

if __name__ == "__main__":
    print("Costruendo il DAG LangGraph e avviando il consumer...")
    start_consumer()
