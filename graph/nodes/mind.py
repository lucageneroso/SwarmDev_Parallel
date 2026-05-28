"""Mind-layer graph nodes: discovery, planning, OCL validation, requirements, and fanout."""

import os
import json

from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from llm_wiki import load_sop

from graph.state import OrchestratorState, PROJECT_ROOT
from graph.context import mind_llm, load_superpowers
from graph.aci import _render_uml_diagram, _seaclip_health_check, _seaclip_create_issue
from graph.utils import extract_code
from swarm_mind import EpisodicBuffer

# Initialize episodic buffer
episodic_buffer = EpisodicBuffer()


def human_node(state: OrchestratorState):
    history = state.get("chat_history", [])
    if not history:
        # Initial prompt
        user_input = input("\n[System] Inserisci la tua richiesta iniziale per SwarmDev:\n> ")
    else:
        user_input = input("\n> ")
        
    if user_input.strip() == "":
        user_input = "continue"
        
    history.append(HumanMessage(content=user_input))
    
    # Record episode
    episodic_buffer.record(
        task_id=state.get("task_id"),
        node_name="human_node",
        input_data={"chat_history_len": len(history) - 1},
        output_data={"user_input": user_input}
    )
    
    return {"chat_history": history}

def discovery_node(state: OrchestratorState):
    history = state.get("chat_history", [])
    brainstorming_skill = load_superpowers()
    
    sys_msg = SystemMessage(
        content=load_sop("mind_discovery", brainstorming_skill=brainstorming_skill)
    )
    
    print("[Mind] Thinking...")
    response = mind_llm.invoke([sys_msg] + history)
    
    # Extract token usage
    tokens = 0
    if hasattr(response, 'usage_metadata') and response.usage_metadata:
        tokens = response.usage_metadata.get('total_tokens', 0)
        
    content = response.content
    
    # Normalizzazione per catturare varianti prodotte dall'LLM come "### DESIGN APPROVED:" o "DESIGN APPROVED:"
    normalized_content = content.replace("DESIGN APPROVED:", "DESIGN_APPROVED:")
    
    if "DESIGN_APPROVED:" in normalized_content:
        parts = normalized_content.split("DESIGN_APPROVED:")
        msg = parts[0].strip()
        
        # Pulisci eventuali hash o backtick rimasti prima del payload del design doc
        raw_design = parts[1].strip() if len(parts) > 1 else "Design Doc Generato."
        design_doc = raw_design.lstrip("# \n") # rimuove markdown sporco all'inizio
        
        if msg:
            print(f"\n[Mind]: {msg}\n")
        print(f"\n[Mind]: ✅ Design approvato e salvato in memoria.")
        
        history.append(AIMessage(content=msg + "\n[DESIGN APPROVED]"))
        
        # Record episode
        episodic_buffer.record(
            task_id=state.get("task_id"),
            node_name="discovery_node",
            input_data={"last_user_message": history[-2].content if len(history) >= 2 else None},
            output_data={"message": msg, "design_doc": design_doc, "design_approved": True},
            metadata={"total_tokens": tokens}
        )
        
        return {"chat_history": history, "design_doc": design_doc, "total_tokens": tokens}
    else:
        print(f"\n[Mind]: {content}\n")
        history.append(response)
        
        # Record episode
        episodic_buffer.record(
            task_id=state.get("task_id"),
            node_name="discovery_node",
            input_data={"last_user_message": history[-2].content if len(history) >= 2 else None},
            output_data={"message": content, "design_approved": False},
            metadata={"total_tokens": tokens}
        )
        
        return {"chat_history": history, "total_tokens": tokens}

def planning_node(state: OrchestratorState):
    print("\n[Mind] Planning & Contract Generation...")
    design = state.get("design_doc", "")
    errors = state.get("ocl_errors", "")
    design_rag_context = state.get("design_rag_context", "")
    
    sys_msg = SystemMessage(content=load_sop("mind_planning"))
    
    hum_msg_content = f"DESIGN:\n{design}\n"
    if design_rag_context:
        hum_msg_content += f"\n{design_rag_context}\n"
    if errors:
        hum_msg_content += f"\nCRITICAL OCL SYNTAX ERROR in previous attempt:\n{errors}\nFix the OCL expressions immediately."
        
    hum_msg = HumanMessage(content=hum_msg_content)
    response = mind_llm.invoke([sys_msg, hum_msg])
    
    tokens = 0
    if hasattr(response, 'usage_metadata') and response.usage_metadata:
        tokens = response.usage_metadata.get('total_tokens', 0)
        
    json_str = extract_code(response.content)
    
    # ── ACI: Render UML diagram from mermaid_syntax in contract (best-effort) ──
    uml_path = None
    uml_error = None
    
    try:
        contract_data = json.loads(json_str)
        mermaid_syntax = contract_data.get("mermaid_syntax", "")
    except (json.JSONDecodeError, AttributeError):
        mermaid_syntax = ""
    
    if mermaid_syntax:
        workspace_dir = os.path.join(PROJECT_ROOT, "mind_workspace")
        print("[Mind/ACI] 🎨 Generating UML diagram via cli-anything-mermaid...")
        uml_path, uml_error = _render_uml_diagram(mermaid_syntax, workspace_dir)
        
        if uml_path:
            print(f"[Mind/ACI] ✅ UML Diagram rendered: {uml_path}")
        else:
            print(f"[Mind/ACI] ⚠️ UML generation failed (non-blocking): {uml_error}")
    else:
        uml_error = "[ACI/Mermaid] No mermaid_syntax key in contract (skipped)"
        print(f"[Mind/ACI] ⚠️ {uml_error}")
    
    # ── ACI/Seaclip: Create Kanban issues (best-effort) ──
    fe_issue_id = None
    be_issue_id = None
    kanban_err = None

    if _seaclip_health_check():
        print("[Mind/ACI] 📋 SeaClip backend online. Creating Kanban issues...")
        fe_issue_id = _seaclip_create_issue(
            title="Frontend: React App",
            description=f"Build frontend per: {design[:200]}...",
            priority="high",
        )
        be_issue_id = _seaclip_create_issue(
            title="Backend: Python API",
            description=f"Build backend per: {design[:200]}...",
            priority="high",
        )
        if fe_issue_id and be_issue_id:
            print(f"[Mind/ACI] ✅ Kanban: Frontend={fe_issue_id[:8]}... Backend={be_issue_id[:8]}...")
        else:
            kanban_err = "[ACI/Seaclip] Failed to create one or both issues"
            print(f"[Mind/ACI] ⚠️ {kanban_err}")
    else:
        kanban_err = "[ACI/Seaclip] Backend not reachable at localhost:5200 (skipped)"
        print(f"[Mind/ACI] ⚠️ {kanban_err}")

    # Record episode
    episodic_buffer.record(
        task_id=state.get("task_id"),
        node_name="planning_node",
        input_data={"design_doc": design, "ocl_errors": errors, "design_rag_context": design_rag_context},
        output_data={
            "json_contract": json_str,
            "uml_diagram_path": uml_path,
            "kanban_frontend_issue_id": fe_issue_id,
            "kanban_backend_issue_id": be_issue_id
        },
        errors=f"{uml_error or ''}\n{kanban_err or ''}".strip() or None,
        metadata={"total_tokens": tokens}
    )

    return {
        "json_contract": json_str,
        "total_tokens": tokens,
        "uml_diagram_path": uml_path,
        "uml_diagram_error": uml_error,
        "kanban_frontend_issue_id": fe_issue_id,
        "kanban_backend_issue_id": be_issue_id,
        "kanban_error": kanban_err,
    }

def validate_ocl_node(state: OrchestratorState):
    print("[Mind] Validating A2A-OCL Constraints...")
    from quality_gate.ocl_evaluator import A2AOCLValidator
    
    json_contract = state.get("json_contract", "{}")
    
    try:
        data = json.loads(json_contract)
        constraints = data.get("a2a_ocl_constraints", [])
    except Exception as e:
        print(f"[Mind] Errore di parsing JSON del contratto: {e}")
        # Record episode
        episodic_buffer.record(
            task_id=state.get("task_id"),
            node_name="validate_ocl_node",
            input_data={"json_contract": json_contract},
            output_data={"ocl_errors": f"JSON Parse Error: {e}"},
            errors=f"JSON Parse Error: {e}"
        )
        return {"ocl_errors": f"JSON Parse Error: {e}"}
        
    grammar_path = os.path.join(PROJECT_ROOT, "core", "grammar", "a2a_ocl.lark")
    validator = A2AOCLValidator(grammar_path=grammar_path)
    
    errors = []
    for c in constraints:
        res = validator.validate_expression(c)
        if not res["is_valid"]:
            errors.append(f"Expression '{c}': {res.get('error_delta', 'Sintassi invalida')}")
            
    if errors:
        error_log = "\n".join(errors)
        print(f"[Mind] ⚠️ Validazione OCL FALLITA. ({len(errors)} errori):")
        for e in errors:
            print(f"       ❌ {e}")
        # Record episode
        episodic_buffer.record(
            task_id=state.get("task_id"),
            node_name="validate_ocl_node",
            input_data={"json_contract": json_contract},
            output_data={"ocl_errors": error_log},
            errors=error_log
        )
        return {"ocl_errors": error_log, "ocl_retry_count": 1}
        
    print("[Mind] ✅ Validazione OCL SUPERATA. Passo il contratto ai Worker.")
    # Record episode
    episodic_buffer.record(
        task_id=state.get("task_id"),
        node_name="validate_ocl_node",
        input_data={"json_contract": json_contract},
        output_data={"ocl_errors": None}
    )
    return {"ocl_errors": None}

def requirements_node(state: OrchestratorState):
    print("[Mind/Requirements] Estrazione requisiti dal Design Doc...")
    design_doc = state.get("design_doc", "")
    
    # Costruisci il prompt usando la nuova SOP
    sys_msg = SystemMessage(content=load_sop("requirements_engineer", design_doc=design_doc))
    
    print("[Mind/Requirements] Thinking...")
    # Using the same mind_llm used in other Mind nodes
    response = mind_llm.invoke([sys_msg])
    
    # Extract token usage
    tokens = 0
    if hasattr(response, 'usage_metadata') and response.usage_metadata:
        tokens = response.usage_metadata.get('total_tokens', 0)
        
    content = response.content.strip()
    
    # Rimuovi eventuali backticks markdown
    if content.startswith("```json"):
        content = content[7:]
    elif content.startswith("```"):
        content = content[3:]
        
    if content.endswith("```"):
        content = content[:-3]
        
    content = content.strip()
    
    print(f"[Mind/Requirements] ✅ Requisiti estratti correttamente.")
    # Record episode
    episodic_buffer.record(
        task_id=state.get("task_id"),
        node_name="requirements_node",
        input_data={"design_doc": design_doc},
        output_data={"requirements_json": content},
        metadata={"total_tokens": tokens}
    )
    return {"requirements_json": content, "total_tokens": tokens}

def fanout_node(state: OrchestratorState):
    print("\n[Orchestrator] Avvio esecuzione parallela dei Worker (Frontend & Backend)...")
    # Record episode
    episodic_buffer.record(
        task_id=state.get("task_id"),
        node_name="fanout_node",
        input_data={},
        output_data={}
    )
    return {}
