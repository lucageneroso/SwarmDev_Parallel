"""Graph routing functions – pure logic that inspects state and returns next-node names.

Each function is used as a LangGraph conditional edge or routing node.
They never modify state, only read it and return destination strings.
"""

from typing import Sequence

from langgraph.graph import END

from graph.state import (
    OrchestratorState,
    MAX_RETRIES,
    MAX_OCL_RETRIES,
    MAX_RUNTIME_RETRIES,
    MAX_TEST_RETRIES,
    MAX_QUALITY_RETRIES,
)


def router_discovery(state: OrchestratorState):
    if state.get("design_doc"):
        return "planning_node"
    return "human_node"


def router_ocl(state: OrchestratorState):
    ocl_retries = state.get("ocl_retry_count", 0)
    if state.get("ocl_errors"):
        if ocl_retries >= MAX_OCL_RETRIES:
            print(f"[Mind] ⚠️ Max OCL retries ({MAX_OCL_RETRIES}) raggiunto. Procedo con vincoli NON validati.")
            return "fanout_node"
        print(f"[Mind] Micro-Loop retry {ocl_retries}/{MAX_OCL_RETRIES}...")
        return "planning_node"
    return "fanout_node"


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
        return ["consolidation_node"]
        
    next_nodes = []
    if f_err:
        print(f"[RETRY] Routing back to Frontend Actor. Linter Errors:\n{f_err}")
        next_nodes.append("frontend_actor")
    if b_err:
        print(f"[RETRY] Routing back to Backend Actor. Linter Errors:\n{b_err}")
        next_nodes.append("backend_actor")
        
    return next_nodes


def test_router(state: OrchestratorState) -> str:
    cov = state.get("test_coverage", 0)
    retries = state.get("test_retry_count", 0)
    
    if cov < 85 and retries < MAX_TEST_RETRIES:
        print(f"[Testing Swarm] Coverage {cov}% < 85% (Retry {retries}/{MAX_TEST_RETRIES}). Micro-Loop per generare test mancanti.")
        return "test_writer_actor"
        
    if cov < 85:
        print(f"[Testing Swarm] Coverage {cov}% < 85% ma MAX_TEST_RETRIES raggiunto. Procedo.")
    else:
        print(f"[Testing Swarm] Coverage {cov}% >= 85%. Passaggio al Quality Gate.")
        
    return "quality_evaluation_node"


def quality_router(state: OrchestratorState) -> str:
    passed = state.get("quality_passed", True)
    retries = state.get("quality_retry_count", 0)
    
    if not passed and retries < MAX_QUALITY_RETRIES:
        print(f"[Quality Gate] Quality Gate fallito (Retry {retries}/{MAX_QUALITY_RETRIES}). Routing a backend_actor per refactoring.")
        return "backend_actor"
        
    if not passed:
        print(f"[Quality Gate] Quality Gate fallito ma MAX_QUALITY_RETRIES raggiunto. Procedo.")
        
    print("[Quality Gate] Passaggio a Documentation Node.")
    return "documentation_node"


def runtime_router(state: OrchestratorState) -> str:
    """Route based on runtime errors: loop back to backend_actor or END."""
    if state.get("runtime_errors") and state.get("runtime_retry_count", 0) < MAX_RUNTIME_RETRIES:
        print(f"[Runtime Router] Runtime crash detected. Routing back to backend_actor (retry {state.get('runtime_retry_count', 0)}/{MAX_RUNTIME_RETRIES})")
        return "backend_actor"
    
    if state.get("runtime_errors"):
        print("[Runtime Router] Max runtime retries reached. Exiting with runtime failures.")
    else:
        print("[Runtime Router] All clear. Pipeline complete.")
    return "consolidation_node"
