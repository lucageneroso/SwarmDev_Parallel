"""
graph.utils — Text Parsing & File Writing Utilities
=====================================================
Helper functions for extracting code from LLM output,
parsing XML file tags, and writing multi-file projects to disk.

Estratto da graph_orchestrator.py righe 462-487.
"""

import os
import re


def extract_code(text: str) -> str:
    """Estrae il contenuto da un blocco di codice Markdown (```...```)."""
    match = re.search(r"```[a-zA-Z]*\n?(.*?)```", text, re.DOTALL)
    if match:
        return match.group(1).strip()
    return text.strip()


def parse_xml_files(text: str) -> dict[str, str]:
    """Estrae i tag <file path="...">...</file> dall'output dell'LLM."""
    pattern = re.compile(r'<file\s+path=["\']([^"\']+)["\']\s*>([\s\S]*?)</file>', re.MULTILINE)
    files = {}
    for match in pattern.finditer(text):
        path = match.group(1).strip()
        content = match.group(2).strip()
        files[path] = content
    return files


def write_project_to_dir(files: dict[str, str], base_dir: str):
    """Scrive i file parsati su disco ricreando le sottocartelle."""
    os.makedirs(base_dir, exist_ok=True)
    for rel_path, content in files.items():
        full_path = os.path.join(base_dir, rel_path.lstrip("/"))
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        with open(full_path, "w", encoding="utf-8") as f:
            f.write(content)
    return base_dir
