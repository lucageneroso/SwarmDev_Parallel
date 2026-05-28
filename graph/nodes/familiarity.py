"""Familiarity check node — checks ChromaDB for similar past designs before planning."""

from graph.state import OrchestratorState
from graph.aci import _chromadb_query_raw
from swarm_mind import EpisodicBuffer

# Initialize episodic buffer
episodic_buffer = EpisodicBuffer()


def familiarity_check_node(state: OrchestratorState) -> dict:
    print("[Swarm Mind/Familiarity] Checking past experiences for similar designs...")
    
    design = state.get("design_doc", "")
    if not design:
        return {"design_rag_context": None, "retrieved_memories": []}
        
    parsed = _chromadb_query_raw(design, n_results=2)
    
    retrieved = []
    design_rag_context = ""
    
    if parsed:
        ids = parsed.get("ids", [[]])[0] if isinstance(parsed.get("ids"), list) else []
        documents = parsed.get("documents", [[]])[0] if isinstance(parsed.get("documents"), list) else []
        metadatas = parsed.get("metadatas", [[]])[0] if isinstance(parsed.get("metadatas"), list) else []
        distances = parsed.get("distances", [[]])[0] if isinstance(parsed.get("distances"), list) else []
        
        valid_docs = []
        for i, doc in enumerate(documents):
            dist = distances[i] if i < len(distances) else 0.0
            doc_id = ids[i] if i < len(ids) else "unknown"
            meta = metadatas[i] if i < len(metadatas) else {}
            
            # Soglia di confidenza: distanza < 0.5
            if dist < 0.5:
                valid_docs.append(doc)
                retrieved.append({
                    "id": doc_id,
                    "document": doc,
                    "metadata": meta,
                    "distance": dist
                })
                
        if valid_docs:
            design_rag_context = "[PAST SIMILAR EXPERIENCES / RAG HINT]\n" + "\n---\n".join(valid_docs)
            
    if design_rag_context:
        print(f"[Swarm Mind/Familiarity] Match ad alta confidenza trovato in memoria a lungo termine! ({len(retrieved)} ricordi)")
        # Record episode
        episodic_buffer.record(
            task_id=state.get("task_id"),
            node_name="familiarity_check_node",
            input_data={"design_doc_len": len(design)},
            output_data={"design_rag_context": design_rag_context, "match_found": True}
        )
        return {
            "design_rag_context": design_rag_context,
            "retrieved_memories": retrieved
        }
        
    print("[Swarm Mind/Familiarity] Nessuna esperienza passata rilevante trovata.")
    # Record episode
    episodic_buffer.record(
        task_id=state.get("task_id"),
        node_name="familiarity_check_node",
        input_data={"design_doc_len": len(design)},
        output_data={"design_rag_context": None, "match_found": False}
    )
    return {
        "design_rag_context": None,
        "retrieved_memories": []
    }
