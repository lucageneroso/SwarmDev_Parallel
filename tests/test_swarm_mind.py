import os
import unittest
import sqlite3
import tempfile
from swarm_mind import EpisodicBuffer


class TestEpisodicBuffer(unittest.TestCase):
    def setUp(self):
        # Crea file temporanei per i database di test
        self.active_fd, self.active_path = tempfile.mkstemp(suffix=".db")
        self.archive_fd, self.archive_path = tempfile.mkstemp(suffix=".db")
        
        # Inizializza il buffer con i file temporanei
        self.buffer = EpisodicBuffer(
            active_db_path=self.active_path,
            archive_db_path=self.archive_path
        )

    def tearDown(self):
        # Chiude i file descriptor temporanei e cancella i file
        os.close(self.active_fd)
        os.close(self.archive_fd)
        try:
            os.remove(self.active_path)
        except OSError:
            pass
        try:
            os.remove(self.archive_path)
        except OSError:
            pass

    def test_record_and_query(self):
        task_id = "test_run_123"
        node_name = "test_node"
        input_data = {"key": "val", "list": [1, 2, 3]}
        output_data = "Success"
        errors = "None"
        metadata = {"tokens": 120}
        
        # Registra un record
        inserted_id = self.buffer.record(
            task_id=task_id,
            node_name=node_name,
            input_data=input_data,
            output_data=output_data,
            errors=errors,
            metadata=metadata
        )
        self.assertGreater(inserted_id, 0)
        
        # Recupera gli episodi attivi
        episodes = self.buffer.get_active_episodes(task_id)
        self.assertEqual(len(episodes), 1)
        
        ep = episodes[0]
        self.assertEqual(ep["id"], inserted_id)
        self.assertEqual(ep["task_id"], task_id)
        self.assertEqual(ep["node_name"], node_name)
        
        # Verifica la corretta deserializzazione/preservazione dei tipi JSON
        import json
        retrieved_input = json.loads(ep["input_data"])
        self.assertEqual(retrieved_input["key"], "val")
        self.assertEqual(retrieved_input["list"], [1, 2, 3])
        
        self.assertEqual(ep["output_data"], "Success")
        self.assertEqual(ep["errors"], errors)
        
        retrieved_metadata = json.loads(ep["metadata"])
        self.assertEqual(retrieved_metadata["tokens"], 120)

    def test_archive_and_clear(self):
        task_id_1 = "task_A"
        task_id_2 = "task_B"
        
        # Registra per task_A
        self.buffer.record(task_id_1, "node_1", {"in": 1}, {"out": 1})
        self.buffer.record(task_id_1, "node_2", {"in": 2}, {"out": 2})
        
        # Registra per task_B
        self.buffer.record(task_id_2, "node_1", {"in": 3}, {"out": 3})
        
        # Verifica totale attivi
        all_active = self.buffer.get_active_episodes()
        self.assertEqual(len(all_active), 3)
        
        # Archivia task_A
        success = self.buffer.archive_and_clear(task_id_1)
        self.assertTrue(success)
        
        # Verifica che task_A sia vuoto nell'attivo, ma task_B sia ancora presente
        active_A = self.buffer.get_active_episodes(task_id_1)
        active_B = self.buffer.get_active_episodes(task_id_2)
        self.assertEqual(len(active_A), 0)
        self.assertEqual(len(active_B), 1)
        
        # Verifica che task_A sia presente nell'archivio storicizzato
        conn_arch = sqlite3.connect(self.archive_path)
        cursor = conn_arch.cursor()
        cursor.execute("SELECT COUNT(*) FROM episodes WHERE task_id = ?", (task_id_1,))
        count_arch_A = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM episodes WHERE task_id = ?", (task_id_2,))
        count_arch_B = cursor.fetchone()[0]
        conn_arch.close()
        
        self.assertEqual(count_arch_A, 2)
        self.assertEqual(count_arch_B, 0)


if __name__ == "__main__":
    unittest.main()
