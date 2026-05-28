import os
import json
import sqlite3
from datetime import datetime, timezone
from typing import Optional, Union, Any

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(CURRENT_DIR)


class EpisodicBuffer:
    """Diario di Bordo (Short-Term Memory / Episodic Buffer).
    
    Gestisce la registrazione delle transazioni dello swarm nel database attivo (SQLite)
    e l'archiviazione a freddo (cold storage) in un database storico di archivio.
    """
    
    def __init__(self, active_db_path: str = None, archive_db_path: str = None):
        # Definisce i percorsi di default
        if active_db_path is None:
            active_db_path = os.path.join(PROJECT_ROOT, "workspace", "memory", "episodic_active.db")
        if archive_db_path is None:
            archive_db_path = os.path.join(PROJECT_ROOT, "workspace", "memory", "episodic_archive.db")
            
        self.active_db_path = os.path.abspath(active_db_path)
        self.archive_db_path = os.path.abspath(archive_db_path)
        
        # Crea le cartelle se non esistono
        os.makedirs(os.path.dirname(self.active_db_path), exist_ok=True)
        os.makedirs(os.path.dirname(self.archive_db_path), exist_ok=True)
        
        # Inizializza gli schemi dei database
        self._init_db(self.active_db_path)
        self._init_db(self.archive_db_path)

    def _init_db(self, db_path: str):
        """Crea la tabella episodes se non esiste."""
        conn = sqlite3.connect(db_path)
        try:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS episodes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_id TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    node_name TEXT NOT NULL,
                    input_data TEXT,
                    output_data TEXT,
                    errors TEXT,
                    metadata TEXT
                );
            """)
            conn.commit()
        finally:
            conn.close()

    def _serialize(self, data: Any) -> Optional[str]:
        """Serializza in formato JSON o ritorna la stringa se già serializzato."""
        if data is None:
            return None
        if isinstance(data, (dict, list, tuple)):
            try:
                return json.dumps(data, ensure_ascii=False)
            except Exception:
                return str(data)
        return str(data)

    def record(
        self,
        task_id: str,
        node_name: str,
        input_data: Any,
        output_data: Any,
        errors: Optional[str] = None,
        metadata: Optional[dict] = None
    ) -> int:
        """Registra una transazione di un nodo nel database attivo."""
        if not task_id:
            task_id = "default_session"
            
        timestamp = datetime.now(timezone.utc).isoformat()
        input_str = self._serialize(input_data)
        output_str = self._serialize(output_data)
        metadata_str = self._serialize(metadata)
        
        conn = sqlite3.connect(self.active_db_path)
        try:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO episodes (task_id, timestamp, node_name, input_data, output_data, errors, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (task_id, timestamp, node_name, input_str, output_str, errors, metadata_str))
            conn.commit()
            inserted_id = cursor.lastrowid or -1
            print(f"[Episodic Buffer] Recorded episode for node '{node_name}' (ID: {inserted_id})")
            return inserted_id
        except Exception as e:
            print(f"[Episodic Buffer] Error recording episode for node '{node_name}': {e}")
            return -1
        finally:
            conn.close()

    def get_active_episodes(self, task_id: Optional[str] = None) -> list[dict]:
        """Recupera gli episodi registrati nel database attivo, opzionalmente per un certo task_id."""
        conn = sqlite3.connect(self.active_db_path)
        conn.row_factory = sqlite3.Row
        try:
            cursor = conn.cursor()
            if task_id:
                cursor.execute("""
                    SELECT id, task_id, timestamp, node_name, input_data, output_data, errors, metadata 
                    FROM episodes WHERE task_id = ? ORDER BY id ASC
                """, (task_id,))
            else:
                cursor.execute("""
                    SELECT id, task_id, timestamp, node_name, input_data, output_data, errors, metadata 
                    FROM episodes ORDER BY id ASC
                """)
                
            rows = cursor.fetchall()
            episodes = []
            for row in rows:
                episodes.append({
                    "id": row["id"],
                    "task_id": row["task_id"],
                    "timestamp": row["timestamp"],
                    "node_name": row["node_name"],
                    "input_data": row["input_data"],
                    "output_data": row["output_data"],
                    "errors": row["errors"],
                    "metadata": row["metadata"]
                })
            return episodes
        except Exception as e:
            print(f"[Episodic Buffer] Error querying active episodes: {e}")
            return []
        finally:
            conn.close()

    def archive_and_clear(self, task_id: str) -> bool:
        """Sposta tutti gli episodi del task specificato nel database di archivio e li cancella dal DB attivo."""
        if not task_id:
            return False
            
        active_episodes = self.get_active_episodes(task_id)
        if not active_episodes:
            print(f"[Episodic Buffer] No active episodes to archive for task '{task_id}'")
            return True
            
        # Scrive sul database di archivio
        conn_archive = sqlite3.connect(self.archive_db_path)
        try:
            cursor_arch = conn_archive.cursor()
            for ep in active_episodes:
                cursor_arch.execute("""
                    INSERT INTO episodes (task_id, timestamp, node_name, input_data, output_data, errors, metadata)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (ep["task_id"], ep["timestamp"], ep["node_name"], ep["input_data"], ep["output_data"], ep["errors"], ep["metadata"]))
            conn_archive.commit()
            print(f"[Episodic Buffer] Archived {len(active_episodes)} episodes for task '{task_id}'")
        except Exception as e:
            print(f"[Episodic Buffer] Error copying episodes to archive: {e}")
            return False
        finally:
            conn_archive.close()
            
        # Cancella dal database attivo
        conn_active = sqlite3.connect(self.active_db_path)
        try:
            cursor_act = conn_active.cursor()
            cursor_act.execute("DELETE FROM episodes WHERE task_id = ?", (task_id,))
            conn_active.commit()
            print(f"[Episodic Buffer] Cleared {len(active_episodes)} active episodes for task '{task_id}'")
            return True
        except Exception as e:
            print(f"[Episodic Buffer] Error clearing active episodes for task '{task_id}': {e}")
            return False
        finally:
            conn_active.close()
