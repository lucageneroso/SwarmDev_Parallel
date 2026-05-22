"""
LLM Wiki — Prompt-as-Code Module
=================================
Carica le Standard Operating Procedures (SOP) dal filesystem
e le inietta come System Prompt a runtime nel DAG LangGraph.

Pattern:  White-box Memory / Prompt-as-Code
Thesis:   Separation of Concerns — il codice Python è logica pura,
          i prompt sono documenti Markdown versionati via Git.
"""

import os
from functools import lru_cache

_SOPS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sops")


@lru_cache(maxsize=32)
def _load_sop_template(sop_name: str) -> str:
    """
    Carica il template Markdown grezzo da disco.
    Risultato cachato in memoria per evitare I/O ripetuto.
    """
    path = os.path.join(_SOPS_DIR, f"{sop_name}.md")
    if not os.path.exists(path):
        raise FileNotFoundError(
            f"[LLM Wiki] SOP not found: {path}\n"
            f"Available SOPs: {', '.join(_list_available_sops())}"
        )
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def load_sop(sop_name: str, **kwargs) -> str:
    """
    Carica una SOP per nome e applica i placeholder opzionali.

    Args:
        sop_name: Nome della SOP senza estensione (es. 'mind_discovery')
        **kwargs: Placeholder da iniettare nel template (es. brainstorming_skill=...)

    Returns:
        Il contenuto della SOP con i placeholder sostituiti.

    Raises:
        FileNotFoundError: Se la SOP non esiste in llm_wiki/sops/

    Example:
        >>> prompt = load_sop("mind_discovery", brainstorming_skill="...")
        >>> sys_msg = SystemMessage(content=prompt)
    """
    template = _load_sop_template(sop_name)
    if kwargs:
        return template.format(**kwargs)
    return template


def _list_available_sops() -> list[str]:
    """Elenca le SOP disponibili nella directory sops/."""
    if not os.path.isdir(_SOPS_DIR):
        return []
    return [
        f.replace(".md", "")
        for f in os.listdir(_SOPS_DIR)
        if f.endswith(".md")
    ]


def invalidate_cache():
    """Invalida la cache dei template — utile per la coevoluzione runtime."""
    _load_sop_template.cache_clear()
