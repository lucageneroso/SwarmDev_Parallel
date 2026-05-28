import sys
import os
# Aggiunge la root del progetto al path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import argparse
import json
import sqlite3
from swarm_mind import EpisodicBuffer
from graph.aci import (
    _chromadb_query_raw,
    _chromadb_delete,
    CHROMADB_COLLECTION
)
from swarm_mind.bootstrap_history import bootstrap_historical_projects


def cmd_short_term(args):
    buffer = EpisodicBuffer()
    db = "archive" if args.archive else "active"
    db_path = buffer.archive_db_path if args.archive else buffer.active_db_path
    
    print(f"\n=== Short-Term Memory ({db.upper()}) ===")
    print(f"Database Path: {db_path}")
    
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        cursor = conn.cursor()
        if args.task_id:
            cursor.execute(
                "SELECT id, task_id, timestamp, node_name, input_data, output_data, errors, metadata FROM episodes WHERE task_id = ? ORDER BY id ASC",
                (args.task_id,)
            )
        else:
            cursor.execute(
                "SELECT id, task_id, timestamp, node_name, input_data, output_data, errors, metadata FROM episodes ORDER BY id ASC"
            )
        rows = cursor.fetchall()
        episodes = [dict(row) for row in rows]
    except Exception as e:
        print(f"⚠️ Errore di lettura dal database: {e}")
        return
    finally:
        conn.close()
        
    if not episodes:
        print("Nessun episodio trovato.")
        return
        
    print(f"Trovati {len(episodes)} episodi:")
    for ep in episodes[:args.limit]:
        print(f"\n[ID: {ep['id']}] | Task: {ep['task_id']} | Nodo: {ep['node_name']} | Timestamp: {ep['timestamp']}")
        if args.verbose:
            print(f"  Input: {ep['input_data']}")
            print(f"  Output: {ep['output_data']}")
            print(f"  Errori: {ep['errors']}")
            print(f"  Metadata: {ep['metadata']}")
        print("-" * 50)
            
    if len(episodes) > args.limit:
        print(f"\n... e altri {len(episodes) - args.limit} episodi (usa --limit per mostrarne di più).")


def cmd_long_term_list(args):
    print(f"\n=== Long-Term Memory (ChromaDB: {CHROMADB_COLLECTION}) ===")
    
    from graph.aci import _resolve_cli_binary, safe_cli_invoke
    try:
        cli_bin = _resolve_cli_binary("cli-anything-chromadb")
    except ValueError as e:
        print(f"⚠️ Errore CLI: {e}")
        return
        
    res = safe_cli_invoke([
        cli_bin, "--json", "document", "get",
        "--collection", CHROMADB_COLLECTION,
        "--limit", str(args.limit)
    ], parse_json=True)
    
    if res["success"] and res.get("parsed"):
        parsed = res["parsed"]
        ids = parsed.get("ids", [])
        if not ids:
            print("Nessuna memoria a lungo termine trovata.")
            return
            
        print(f"Trovate {len(ids)} memorie (limite impostato: {args.limit}):")
        documents = parsed.get("documents", [])
        metadatas = parsed.get("metadatas", [])
        
        for i, doc_id in enumerate(ids):
            doc_text = documents[i] if i < len(documents) else ""
            doc_meta = metadatas[i] if i < len(metadatas) else {}
            print(f"\n[ID: {doc_id}]")
            print(f"  Metadata: {doc_meta}")
            print(f"  Contenuto:\n{doc_text}")
            print("-" * 60)
    else:
        print("⚠️ Impossibile collegarsi a ChromaDB (assicurati che il server sia attivo).")


def cmd_long_term_query(args):
    print(f"\n=== Long-Term Memory Query: '{args.query}' ===")
    parsed = _chromadb_query_raw(args.query, n_results=args.limit)
    if not parsed:
        print("Nessun risultato trovato o server offline.")
        return
        
    ids = parsed.get("ids", [[]])[0] if isinstance(parsed.get("ids"), list) else []
    documents = parsed.get("documents", [[]])[0] if isinstance(parsed.get("documents"), list) else []
    metadatas = parsed.get("metadatas", [[]])[0] if isinstance(parsed.get("metadatas"), list) else []
    distances = parsed.get("distances", [[]])[0] if isinstance(parsed.get("distances"), list) else []
    
    if not ids:
        print("Nessun match trovato.")
        return
        
    print(f"Trovati {len(ids)} risultati simili:")
    for i, doc_id in enumerate(ids):
        doc_text = documents[i] if i < len(documents) else ""
        doc_meta = metadatas[i] if i < len(metadatas) else {}
        dist = distances[i] if i < len(distances) else 0.0
        print(f"\n[ID: {doc_id}] | Distanza (L2): {dist:.4f}")
        print(f"  Metadata: {doc_meta}")
        print(f"  Contenuto:\n{doc_text}")
        print("-" * 60)


def cmd_long_term_delete(args):
    print(f"\n=== Long-Term Memory Delete: ID '{args.id}' ===")
    success = _chromadb_delete(args.id)
    if success:
        print(f"✅ Memoria '{args.id}' rimossa con successo da ChromaDB.")
    else:
        print(f"⚠️ Impossibile rimuovere la memoria '{args.id}'.")


def cmd_bootstrap(args):
    bootstrap_historical_projects()


def main():
    parser = argparse.ArgumentParser(
        description="Swarm Mind CLI — Ispezione e Gestione della Memoria Biologica"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    
    # cmd: short-term
    p_st = subparsers.add_parser("short-term", help="Ispeziona il Diario di Bordo (Short-Term)")
    p_st.add_argument("--active", action="store_true", help="Mostra episodi attivi (default)")
    p_st.add_argument("--archive", action="store_true", help="Mostra episodi archiviati")
    p_st.add_argument("--task-id", type=str, help="Filtra per task specifico")
    p_st.add_argument("--limit", type=int, default=10, help="Limite di righe da mostrare")
    p_st.add_argument("--verbose", action="store_true", help="Mostra i dettagli completi degli input/output")
    p_st.set_defaults(func=cmd_short_term)
    
    # cmd: long-term-list
    p_lt_list = subparsers.add_parser("long-term-list", help="Elenca le memorie a lungo termine (ChromaDB)")
    p_lt_list.add_argument("--limit", type=int, default=20, help="Limite di righe da mostrare")
    p_lt_list.set_defaults(func=cmd_long_term_list)
    
    # cmd: long-term-query
    p_lt_query = subparsers.add_parser("long-term-query", help="Esegue una query semantica sulle memorie (ChromaDB)")
    p_lt_query.add_argument("query", type=str, help="La frase di ricerca semantica")
    p_lt_query.add_argument("--limit", type=int, default=3, help="Numero di risultati da ritornare")
    p_lt_query.set_defaults(func=cmd_long_term_query)
    
    # cmd: long-term-delete
    p_lt_del = subparsers.add_parser("long-term-delete", help="Rimuove una memoria tramite ID (ChromaDB)")
    p_lt_del.add_argument("id", type=str, help="ID della memoria da rimuovere (es: fix_abcdef123)")
    p_lt_del.set_defaults(func=cmd_long_term_delete)
    
    # cmd: bootstrap
    p_boot = subparsers.add_parser("bootstrap", help="Avvia il caricamento storico dei progetti in ChromaDB")
    p_boot.set_defaults(func=cmd_bootstrap)
    
    args = parser.parse_args()
    
    # Default behavior for short-term active/archive
    if args.command == "short-term" and not args.active and not args.archive:
        args.active = True
        
    args.func(args)


if __name__ == "__main__":
    main()
