import os
import sqlite3
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from graph.state import OrchestratorState
from graph.nodes.consolidation import consolidation_node
from swarm_mind import EpisodicBuffer


class TestConsolidation(unittest.TestCase):
    def setUp(self):
        # File temporanei per i DB
        self.active_fd, self.active_path = tempfile.mkstemp(suffix=".db")
        self.archive_fd, self.archive_path = tempfile.mkstemp(suffix=".db")
        
        # Crea il buffer temporaneo usando i file temporanei
        self.buffer = EpisodicBuffer(
            active_db_path=self.active_path,
            archive_db_path=self.archive_path
        )
        
        # Patch di EpisodicBuffer in consolidation.py per ritornare il nostro buffer di test
        self.patcher = patch("graph.nodes.consolidation.EpisodicBuffer", return_value=self.buffer)
        self.patcher.start()

    def tearDown(self):
        self.patcher.stop()
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

    @patch("graph.nodes.consolidation.mind_llm")
    @patch("graph.nodes.consolidation._chromadb_add_fix")
    def test_consolidation_with_errors(self, mock_add_fix, mock_llm):
        task_id = "run_errors_999"
        
        # Registra episodi nel DB attivo
        self.buffer.record(task_id, "node_A", "inputA", "outputA", errors="Critical error in compilation")
        self.buffer.record(task_id, "node_B", "inputB", "outputB", errors=None)
        
        # Mocking della risposta dell'LLM
        mock_response = MagicMock()
        mock_response.content = "ERRORE: Errore critico di compilazione nel backend\nSOLUZIONE: Correzione dell'entrypoint e delle dipendenze"
        mock_llm.invoke.return_value = mock_response
        
        # Mocking di chromadb
        mock_add_fix.return_value = True
        
        # Definisce lo stato
        state = {
            "task_id": task_id
        }
        
        # Esegue il consolidamento
        res = consolidation_node(state)
        
        # Verifica ritorno vuoto del nodo
        self.assertEqual(res, {})
        
        # Verifica invocazione LLM
        mock_llm.invoke.assert_called_once()
        
        # Verifica invocazione _chromadb_add_fix
        mock_add_fix.assert_called_once_with(
            "Errore critico di compilazione nel backend",
            "Correzione dell'entrypoint e delle dipendenze"
        )
        
        # Verifica che i log siano stati cancellati dal DB attivo
        active_episodes = self.buffer.get_active_episodes(task_id)
        self.assertEqual(len(active_episodes), 0)
        
        # Verifica che i log siano presenti nel DB di archivio
        conn_arch = sqlite3.connect(self.archive_path)
        cursor = conn_arch.cursor()
        cursor.execute("SELECT COUNT(*) FROM episodes WHERE task_id = ?", (task_id,))
        count = cursor.fetchone()[0]
        conn_arch.close()
        self.assertEqual(count, 2)

    @patch("graph.nodes.consolidation.mind_llm")
    @patch("graph.nodes.consolidation._chromadb_add_fix")
    def test_consolidation_no_errors(self, mock_add_fix, mock_llm):
        task_id = "run_clean_000"
        
        # Registra episodi puliti nel DB attivo
        self.buffer.record(task_id, "node_A", "inputA", "outputA", errors=None)
        
        # Stato
        state = {
            "task_id": task_id
        }
        
        # Esegue
        consolidation_node(state)
        
        # LLM e ChromaDB NON dovrebbero essere stati chiamati (poiché non c'erano errori da consolidare)
        mock_llm.invoke.assert_not_called()
        mock_add_fix.assert_not_called()
        
        # Ma il log grezzo dovrebbe comunque essere stato spostato nell'archivio storicizzato
        active_episodes = self.buffer.get_active_episodes(task_id)
        self.assertEqual(len(active_episodes), 0)
        
        conn_arch = sqlite3.connect(self.archive_path)
        cursor = conn_arch.cursor()
        cursor.execute("SELECT COUNT(*) FROM episodes WHERE task_id = ?", (task_id,))
        count = cursor.fetchone()[0]
        conn_arch.close()
        self.assertEqual(count, 1)


if __name__ == "__main__":
    unittest.main()
