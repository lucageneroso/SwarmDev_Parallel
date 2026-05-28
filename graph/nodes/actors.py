"""Worker actor nodes: frontend and backend code-generation actors."""

import json

from langchain_core.messages import SystemMessage, HumanMessage
from llm_wiki import load_sop

from graph.state import OrchestratorState
from graph.context import worker_llm, load_directives
from graph.aci import _seaclip_move_issue
from swarm_mind import EpisodicBuffer

# Initialize episodic buffer
episodic_buffer = EpisodicBuffer()


def frontend_actor(state: OrchestratorState):
    print("[Frontend Actor] Generating Code...")
    # ACI/Seaclip: Move ticket to In Progress
    _seaclip_move_issue(state.get("kanban_frontend_issue_id"), "In Progress")
    directives = load_directives()
    
    sys_msg = SystemMessage(content=load_sop("frontend_actor") + "\n" + directives)
    
    try:
        reqs = json.loads(state['json_contract']).get('frontend_requirements', state['json_contract'])
    except:
        reqs = state['json_contract']
        
    user_content = f"REQUIREMENTS:\n{reqs}"
    if state.get("frontend_errors") and state.get("frontend_code"):
        user_content += (
            f"\n\nYOUR PREVIOUS CODE:\n{state['frontend_code']}\n\n"
            f"CRITICAL FAILURE. Linter errors found:\n{state['frontend_errors']}\n\n"
            f"Fix ALL errors. Re-output the ENTIRE project using <file> tags."
        )
    # RAG: Inject past solutions if available
    if state.get("frontend_rag_context"):
        user_content += f"\n\n[RAG MEMORY - Past Solutions for Similar Errors]\n{state['frontend_rag_context']}"
        
    hum_msg = HumanMessage(content=user_content)
    response = worker_llm.invoke([sys_msg, hum_msg])
    
    tokens = 0
    if hasattr(response, 'usage_metadata') and response.usage_metadata:
        tokens = response.usage_metadata.get('total_tokens', 0)
    
    # Record episode
    episodic_buffer.record(
        task_id=state.get("task_id"),
        node_name="frontend_actor",
        input_data={
            "requirements": reqs,
            "has_previous_errors": bool(state.get("frontend_errors")),
            "has_rag_context": bool(state.get("frontend_rag_context"))
        },
        output_data={"frontend_code_len": len(response.content) if response.content else 0},
        metadata={"total_tokens": tokens}
    )
    
    return {"frontend_code": response.content, "total_tokens": tokens}

def backend_actor(state: OrchestratorState):
    print("[Backend Actor] Generating Code...")
    # ACI/Seaclip: Move ticket to In Progress
    _seaclip_move_issue(state.get("kanban_backend_issue_id"), "In Progress")
    directives = load_directives()
    
    sys_msg = SystemMessage(content=load_sop("backend_actor") + "\n" + directives)
    
    try:
        reqs = json.loads(state['json_contract']).get('backend_requirements', state['json_contract'])
    except:
        reqs = state['json_contract']
        
    user_content = f"REQUIREMENTS:\n{reqs}"
    if state.get("backend_errors") and state.get("backend_code"):
        user_content += (
            f"\n\nYOUR PREVIOUS CODE:\n{state['backend_code']}\n\n"
            f"CRITICAL FAILURE. Linter errors found:\n{state['backend_errors']}\n\n"
            f"Fix ALL errors. Re-output the ENTIRE project using <file> tags."
        )
    # RAG: Inject past solutions if available
    if state.get("backend_rag_context"):
        user_content += f"\n\n[RAG MEMORY - Past Solutions for Similar Errors]\n{state['backend_rag_context']}"
        
    hum_msg = HumanMessage(content=user_content)
    response = worker_llm.invoke([sys_msg, hum_msg])
    
    tokens = 0
    if hasattr(response, 'usage_metadata') and response.usage_metadata:
        tokens = response.usage_metadata.get('total_tokens', 0)
    
    # Record episode
    episodic_buffer.record(
        task_id=state.get("task_id"),
        node_name="backend_actor",
        input_data={
            "requirements": reqs,
            "has_previous_errors": bool(state.get("backend_errors")),
            "has_rag_context": bool(state.get("backend_rag_context"))
        },
        output_data={"backend_code_len": len(response.content) if response.content else 0},
        metadata={"total_tokens": tokens}
    )
    
    return {"backend_code": response.content, "total_tokens": tokens}
