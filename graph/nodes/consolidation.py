"""Consolidation node — performs memory consolidation at the end of the DAG execution.

It distills active episodic logs into semantic memories (Error-Fix pairs),
saves them to ChromaDB (Strato C), and archives the raw logs to episodic_archive.db.
"""

import json
from langchain_core.messages import SystemMessage, HumanMessage
from graph.state import OrchestratorState
from graph.context import mind_llm
from graph.aci import _chromadb_add_fix, _chromadb_get_by_id, _chromadb_delete
from swarm_mind import EpisodicBuffer
from llm_wiki import load_sop


def consolidation_node(state: OrchestratorState) -> dict:
    print("\n[Swarm Mind] Avvio Consolidamento della Memoria...")
    
    task_id = state.get("task_id")
    if not task_id:
        print("[Swarm Mind] Nessun task_id nello stato. Salto il consolidamento.")
        return {}
        
    buffer = EpisodicBuffer()
    
    # ── LTP / LTD Synaptic Feedback Loop ──
    retrieved_memories = state.get("retrieved_memories", [])
    if retrieved_memories:
        print(f"[Swarm Mind] Elaborazione feedback sinaptico (LTP/LTD) per {len(retrieved_memories)} ricordi recuperati...")
        
        # Verifica se ci sono stati tentativi di retry in qualsiasi fase del run
        has_retries = (
            state.get("retry_count", 0) > 0 or
            state.get("ocl_retry_count", 0) > 0 or
            state.get("runtime_retry_count", 0) > 0 or
            state.get("test_retry_count", 0) > 0 or
            state.get("quality_retry_count", 0) > 0
        )
        
        from datetime import datetime, timezone
        
        for mem in retrieved_memories:
            doc_id = mem.get("id")
            if not doc_id or doc_id == "unknown":
                continue
                
            try:
                # Recupera la versione aggiornata da ChromaDB
                existing = _chromadb_get_by_id(doc_id)
                if not existing:
                    existing = mem
                    
                meta = existing.get("metadata") or {}
                uses_count = int(meta.get("uses_count", 0))
                failures_count = int(meta.get("failures_count", 0))
                
                doc_text = existing.get("document", "")
                error_txt = ""
                solution_txt = ""
                
                if "ERRORE:" in doc_text and "SOLUZIONE:" in doc_text:
                    parts = doc_text.split("SOLUZIONE:")
                    error_txt = parts[0].replace("ERRORE:", "").strip()
                    solution_txt = parts[1].strip()
                else:
                    error_txt = doc_text or "Errore sconosciuto"
                    solution_txt = "Soluzione di backup"
                
                if not has_retries:
                    # LTP: Rinforza
                    uses_count += 1
                    failures_count = max(0, failures_count - 1)
                    meta["uses_count"] = uses_count
                    meta["failures_count"] = failures_count
                    meta["timestamp"] = datetime.now(timezone.utc).isoformat()
                    
                    saved = _chromadb_add_fix(error_txt, solution_txt, metadata=meta)
                    if saved:
                        print(f"[Swarm Mind/LTP] Rinforzo sinaptico per la memoria '{doc_id}' (uses: {uses_count}, failures: {failures_count})")
                    else:
                        print(f"[Swarm Mind/LTP] ⚠️ Fallito il salvataggio del rinforzo per '{doc_id}' in ChromaDB.")
                else:
                    # LTD: Depreca
                    failures_count += 1
                    meta["failures_count"] = failures_count
                    
                    if failures_count >= 3:
                        # Pruning: cancella
                        deleted = _chromadb_delete(doc_id)
                        if deleted:
                            print(f"[Swarm Mind/LTD] Memoria '{doc_id}' rimossa/dimenticata dopo {failures_count} fallimenti persistenti.")
                        else:
                            print(f"[Swarm Mind/LTD] ⚠️ Fallita la rimozione della memoria '{doc_id}' da ChromaDB.")
                    else:
                        saved = _chromadb_add_fix(error_txt, solution_txt, metadata=meta)
                        if saved:
                            print(f"[Swarm Mind/LTD] Memoria '{doc_id}' penalizzata (uses: {uses_count}, failures: {failures_count})")
                        else:
                            print(f"[Swarm Mind/LTD] ⚠️ Fallito l'aggiornamento della penalità per '{doc_id}' in ChromaDB.")
                            
            except Exception as e:
                print(f"[Swarm Mind] ⚠️ Errore durante l'elaborazione del feedback per la memoria '{doc_id}': {e}")
                
    episodes = buffer.get_active_episodes(task_id)
    
    if not episodes:
        print(f"[Swarm Mind] Nessun log attivo trovato per il task '{task_id}'.")
        return {}
        
    # Verifica se ci sono stati errori nel run
    has_errors = False
    timeline = []
    
    for ep in episodes:
        node = ep["node_name"]
        inp = ep["input_data"]
        out = ep["output_data"]
        err = ep["errors"]
        
        if err:
            has_errors = True
            
        timeline.append(
            f"Nodo: {node}\n"
            f"Input: {inp[:200] if inp else 'None'}\n"
            f"Output: {out[:200] if out else 'None'}\n"
            f"Errori: {err if err else 'Nessuno'}\n"
            f"---"
        )
        
    if has_errors:
        print("[Swarm Mind] Trovati errori durante il run. Distillazione cognitiva in corso...")
        timeline_str = "\n".join(timeline)
        
        sys_prompt = load_sop("mind_consolidation")
        hum_prompt = f"Diario di Bordo del Run '{task_id}':\n{timeline_str}"
        
        try:
            response = mind_llm.invoke([SystemMessage(content=sys_prompt), HumanMessage(content=hum_prompt)])
            content = response.content.strip()
            
            error_part = ""
            solution_part = ""
            
            if "ERRORE:" in content and "SOLUZIONE:" in content:
                parts = content.split("SOLUZIONE:")
                error_part = parts[0].replace("ERRORE:", "").strip()
                solution_part = parts[1].strip()
            else:
                error_part = "Errore generico riscontrato nel run"
                solution_part = content
                
            if error_part and solution_part:
                print(f"[Swarm Mind] Consolidamento completato:\n  - Errore: {error_part[:100]}...\n  - Soluzione: {solution_part[:100]}...")
                # Scrittura in memoria semantica (ChromaDB)
                saved = _chromadb_add_fix(error_part, solution_part)
                if saved:
                    print("[Swarm Mind] ✅ Memoria consolidata salvata in ChromaDB.")
                else:
                    print("[Swarm Mind] ⚠️ Fallito il salvataggio in ChromaDB (non-blocking).")
        except Exception as e:
            print(f"[Swarm Mind] ⚠️ Errore durante il consolidamento con LLM: {e}")
    else:
        print("[Swarm Mind] Nessun errore rilevato in questo run. Nessuna memoria semantica da consolidare.")
        
    # Archiviazione a freddo e pulizia dei log grezzi
    archived = buffer.archive_and_clear(task_id)
    if archived:
        print(f"[Swarm Mind] ✅ Diario di Bordo del task '{task_id}' spostato in Cold Storage.")
    else:
        print(f"[Swarm Mind] ⚠️ Errore durante lo spostamento del Diario di Bordo in Cold Storage.")
        
    return {}
