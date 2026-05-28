"""
graph.nodes — LangGraph Node Definitions
==========================================
Ogni modulo contiene i nodi di una fase specifica del DAG:
  mind.py          — Discovery, Planning, OCL, Requirements, Fanout
  actors.py        — Frontend/Backend code generation
  critics.py       — Frontend/Backend static analysis
  testing.py       — Test writer + pytest evaluator
  quality.py       — SonarQube quality gate
  documentation.py — Workspace assembly
  runtime.py       — PM2 runtime self-healing
"""
