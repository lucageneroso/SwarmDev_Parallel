import os
import unittest
from unittest.mock import MagicMock, patch

from graph.state import OrchestratorState
from graph.nodes.familiarity import familiarity_check_node
from graph.nodes.mind import planning_node
from graph.nodes.consolidation import consolidation_node


class TestMetaMemory(unittest.TestCase):

    @patch("graph.nodes.familiarity._chromadb_query_raw")
    @patch("graph.nodes.familiarity.episodic_buffer")
    def test_familiarity_check_node_match(self, mock_buffer, mock_query_raw):
        # Configura mock per query che ritorna match con distanza < 0.5
        mock_query_raw.return_value = {
            "ids": [["fix_123"]],
            "documents": [["ERRORE: Test error\nSOLUZIONE: Test solution"]],
            "metadatas": [[{"timestamp": "2026-05-28T00:00:00Z", "uses_count": 1, "failures_count": 0}]],
            "distances": [[0.35]]  # Alta confidenza (< 0.5)
        }
        
        state: OrchestratorState = {
            "task_id": "test_familiarity_1",
            "design_doc": "Create a dummy feature",
            "design_rag_context": None,
            "retrieved_memories": []
        }
        
        res = familiarity_check_node(state)
        
        # Verifica che il RAG context sia popolato
        self.assertIsNotNone(res.get("design_rag_context"))
        self.assertIn("PAST SIMILAR EXPERIENCES", res["design_rag_context"])
        self.assertEqual(len(res["retrieved_memories"]), 1)
        self.assertEqual(res["retrieved_memories"][0]["id"], "fix_123")
        self.assertEqual(res["retrieved_memories"][0]["distance"], 0.35)
        
        # Verifica il corretto log nel buffer
        mock_buffer.record.assert_called_once()

    @patch("graph.nodes.familiarity._chromadb_query_raw")
    @patch("graph.nodes.familiarity.episodic_buffer")
    def test_familiarity_check_node_low_confidence(self, mock_buffer, mock_query_raw):
        # Configura mock per query con distanza >= 0.5 (bassa confidenza)
        mock_query_raw.return_value = {
            "ids": [["fix_456"]],
            "documents": [["ERRORE: Other error\nSOLUZIONE: Other solution"]],
            "metadatas": [[{}]],
            "distances": [[0.75]]  # Bassa confidenza (>= 0.5)
        }
        
        state: OrchestratorState = {
            "task_id": "test_familiarity_2",
            "design_doc": "Create another feature",
            "design_rag_context": None,
            "retrieved_memories": []
        }
        
        res = familiarity_check_node(state)
        
        # Non deve popolare design_rag_context né retrieved_memories poiché la distanza è > 0.5
        self.assertIsNone(res.get("design_rag_context"))
        self.assertEqual(len(res["retrieved_memories"]), 0)

    @patch("graph.nodes.mind.mind_llm")
    @patch("graph.nodes.mind.episodic_buffer")
    @patch("graph.nodes.mind._render_uml_diagram")
    @patch("graph.nodes.mind._seaclip_health_check")
    def test_planning_node_context_injection(self, mock_seaclip_hc, mock_uml, mock_buffer, mock_llm):
        mock_seaclip_hc.return_value = False
        mock_uml.return_value = (None, None)
        
        # Mocking LLM response
        mock_response = MagicMock()
        mock_response.content = "```json\n{\"mermaid_syntax\": \"\"}\n```"
        mock_llm.invoke.return_value = mock_response
        
        state: OrchestratorState = {
            "task_id": "test_planning_1",
            "design_doc": "My design document",
            "design_rag_context": "[PAST SIMILAR EXPERIENCES / RAG HINT]\nDo not make error X",
            "ocl_errors": None,
            "json_contract": None,
            "retry_count": 0
        }
        
        planning_node(state)
        
        # Verifica che l'LLM sia stato invocato con il RAG context nel prompt
        args, kwargs = mock_llm.invoke.call_args
        hum_msg = args[0][1]  # SystemMessage è al 0, HumanMessage è al 1
        
        self.assertIn("Do not make error X", hum_msg.content)
        self.assertIn("My design document", hum_msg.content)

    @patch("graph.nodes.consolidation.EpisodicBuffer")
    @patch("graph.nodes.consolidation._chromadb_get_by_id")
    @patch("graph.nodes.consolidation._chromadb_add_fix")
    @patch("graph.nodes.consolidation._chromadb_delete")
    def test_consolidation_ltp_reinforcement(self, mock_delete, mock_add_fix, mock_get_by_id, mock_buffer_cls):
        # Simula un run di successo (nessun retry)
        state: OrchestratorState = {
            "task_id": "test_ltp_1",
            "retry_count": 0,
            "ocl_retry_count": 0,
            "runtime_retry_count": 0,
            "test_retry_count": 0,
            "quality_retry_count": 0,
            "retrieved_memories": [
                {
                    "id": "fix_999",
                    "document": "ERRORE: old error\nSOLUZIONE: old solution",
                    "metadata": {"uses_count": 2, "failures_count": 0, "timestamp": "2026-05-28T00:00:00Z"}
                }
            ]
        }
        
        # Mock buffer
        mock_buffer = MagicMock()
        mock_buffer.get_active_episodes.return_value = []
        mock_buffer_cls.return_value = mock_buffer
        
        # Mock get_by_id
        mock_get_by_id.return_value = state["retrieved_memories"][0]
        mock_add_fix.return_value = True
        
        consolidation_node(state)
        
        # Deve rinforzare la memoria: uses_count deve incrementarsi, failures_count a 0
        mock_add_fix.assert_called_once()
        args, kwargs = mock_add_fix.call_args
        self.assertEqual(args[0], "old error")
        self.assertEqual(args[1], "old solution")
        
        updated_meta = kwargs.get("metadata")
        if not updated_meta and len(args) > 2:
            updated_meta = args[2]
        self.assertIsNotNone(updated_meta)
        self.assertEqual(updated_meta["uses_count"], 3)
        self.assertEqual(updated_meta["failures_count"], 0)
        self.assertNotEqual(updated_meta["timestamp"], "2026-05-28T00:00:00Z") # deve essersi aggiornato

    @patch("graph.nodes.consolidation.EpisodicBuffer")
    @patch("graph.nodes.consolidation._chromadb_get_by_id")
    @patch("graph.nodes.consolidation._chromadb_add_fix")
    @patch("graph.nodes.consolidation._chromadb_delete")
    def test_consolidation_ltd_penalize(self, mock_delete, mock_add_fix, mock_get_by_id, mock_buffer_cls):
        # Simula un run con errori (retry_count > 0)
        state: OrchestratorState = {
            "task_id": "test_ltd_1",
            "retry_count": 1,  # C'è stato un retry!
            "ocl_retry_count": 0,
            "runtime_retry_count": 0,
            "test_retry_count": 0,
            "quality_retry_count": 0,
            "retrieved_memories": [
                {
                    "id": "fix_999",
                    "document": "ERRORE: old error\nSOLUZIONE: old solution",
                    "metadata": {"uses_count": 0, "failures_count": 1}
                }
            ]
        }
        
        # Mock buffer
        mock_buffer = MagicMock()
        mock_buffer.get_active_episodes.return_value = []
        mock_buffer_cls.return_value = mock_buffer
        
        # Mock get_by_id
        mock_get_by_id.return_value = state["retrieved_memories"][0]
        mock_add_fix.return_value = True
        
        consolidation_node(state)
        
        # Deve penalizzare la memoria: failures_count si incrementa a 2 (sotto la soglia di pruning di 3)
        mock_add_fix.assert_called_once()
        args, kwargs = mock_add_fix.call_args
        updated_meta = kwargs.get("metadata")
        self.assertEqual(updated_meta["failures_count"], 2)
        mock_delete.assert_not_called()

    @patch("graph.nodes.consolidation.EpisodicBuffer")
    @patch("graph.nodes.consolidation._chromadb_get_by_id")
    @patch("graph.nodes.consolidation._chromadb_add_fix")
    @patch("graph.nodes.consolidation._chromadb_delete")
    def test_consolidation_ltd_pruning(self, mock_delete, mock_add_fix, mock_get_by_id, mock_buffer_cls):
        # Simula un run con errori dove la memoria ha già 2 fallimenti precedenti
        state: OrchestratorState = {
            "task_id": "test_ltd_prune",
            "retry_count": 1,
            "ocl_retry_count": 0,
            "runtime_retry_count": 0,
            "test_retry_count": 0,
            "quality_retry_count": 0,
            "retrieved_memories": [
                {
                    "id": "fix_prune",
                    "document": "ERRORE: fail error\nSOLUZIONE: fail solution",
                    "metadata": {"uses_count": 0, "failures_count": 2}
                }
            ]
        }
        
        # Mock buffer
        mock_buffer = MagicMock()
        mock_buffer.get_active_episodes.return_value = []
        mock_buffer_cls.return_value = mock_buffer
        
        # Mock get_by_id
        mock_get_by_id.return_value = state["retrieved_memories"][0]
        mock_delete.return_value = True
        
        consolidation_node(state)
        
        # Il conteggio sale a 3 fallimenti, quindi deve eliminare (prune) il documento da ChromaDB!
        mock_delete.assert_called_once_with("fix_prune")
        mock_add_fix.assert_not_called()

    @patch("swarm_mind.bootstrap_history.os.listdir")
    @patch("swarm_mind.bootstrap_history.os.path.isdir")
    @patch("swarm_mind.bootstrap_history.os.path.exists")
    @patch("swarm_mind.bootstrap_history.open")
    @patch("swarm_mind.bootstrap_history._chromadb_add_fix")
    @patch("swarm_mind.bootstrap_history._chromadb_ensure_collection")
    def test_bootstrap_historical_projects(self, mock_ensure, mock_add_fix, mock_open, mock_exists, mock_isdir, mock_listdir):
        # Setup mock file list and directory status
        mock_listdir.return_value = ["proj1", "proj2", "memory"]
        
        # Controllo dei tipi di cartelle
        def isdir_mock(path):
            return "memory" not in path
        mock_isdir.side_effect = isdir_mock
        
        # Esistenza dei file DESIGN.md e CONTRACT.json e cartella workspace
        def exists_mock(path):
            return "DESIGN.md" in path or "CONTRACT.json" in path or "workspace" in path
        mock_exists.side_effect = exists_mock
        
        # Mock file contents
        mock_file = MagicMock()
        mock_file.read.side_effect = [
            "# Design Requirements for Proj1", 
            '{"frontend_requirements": "build FE", "backend_requirements": "build BE"}',
            "# Design Requirements for Proj2", 
            'invalid JSON',
            'invalid JSON'  # fallback per la lettura dopo seek(0)
        ]
        mock_open.return_value.__enter__.return_value = mock_file
        
        mock_add_fix.return_value = True
        
        from swarm_mind.bootstrap_history import bootstrap_historical_projects
        bootstrap_historical_projects()
        
        # Deve assicurarsi che la collezione esista
        mock_ensure.assert_called_once()
        # Deve invocare add_fix per i 2 progetti trovati
        self.assertEqual(mock_add_fix.call_count, 2)
        
        # Verifica dettagli prima chiamata
        args, kwargs = mock_add_fix.call_args_list[0]
        self.assertIn("proj1", args[0])
        self.assertIn("Frontend: build FE", args[1])


if __name__ == "__main__":
    unittest.main()
