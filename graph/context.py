"""
graph.context — LLM Initialization, Directives & Superpowers
==============================================================
Configura i modelli LLM (mind_llm, worker_llm) via LiteLLM
e carica le direttive YAML e le superpowers Markdown.

Estratto da graph_orchestrator.py righe 85-136.
"""

import os
import logging
import yaml
import warnings

warnings.filterwarnings("ignore", message=".*ChatLiteLLM.*")
from langchain_community.chat_models import ChatLiteLLM
from dotenv import load_dotenv

from graph.state import PROJECT_ROOT, DIRECTIVES_DIR, SUPERPOWERS_DIR

load_dotenv()

# ============================================================================
# DIRECTIVES & SUPERPOWERS LOADERS
# ============================================================================
def load_directives() -> str:
    """Carica execution rules e reasoning constraints dai file YAML."""
    e_path = os.path.join(DIRECTIVES_DIR, "execution_rules.yaml")
    r_path = os.path.join(DIRECTIVES_DIR, "reasoning_constraints.yaml")
    
    directives_content = "SWARMDEV DIRECTIVES:\n"
    try:
        if os.path.exists(e_path):
            with open(e_path, "r", encoding="utf-8") as f:
                e_data = yaml.safe_load(f)
                directives_content += "\nEXECUTION RULES (E):\n"
                for rule in e_data.get("rules", []):
                    directives_content += f"- [{rule['id']}] {rule['content']}\n"
                    
        if os.path.exists(r_path):
            with open(r_path, "r", encoding="utf-8") as f:
                r_data = yaml.safe_load(f)
                directives_content += "\nREASONING CONSTRAINTS (R):\n"
                for constr in r_data.get("constraints", []):
                    directives_content += f"- [{constr['id']}] {constr['content']}\n"
    except Exception as e:
        print(f"[WARN] Error reading Parlant Directives: {e}")
    return directives_content


def load_superpowers() -> str:
    """Carica SOLO la skill brainstorming per la fase di Discovery.
    Writing-plans NON viene caricata perché causerebbe allucinazioni di
    'subagenti' e 'piani' che l'LLM simulerebbe in chat invece di
    emettere il trigger DESIGN_APPROVED: e cedere il controllo al DAG."""
    bs_path = os.path.join(SUPERPOWERS_DIR, "brainstorming", "SKILL.md")
    content = ""
    try:
        if os.path.exists(bs_path):
            with open(bs_path, "r", encoding="utf-8") as f:
                content = f.read()
    except Exception as e:
        print(f"[WARN] Error reading Superpowers: {e}")
    return content


# ============================================================================
# LLM INITIALIZATION
# ============================================================================
llm_model = os.environ.get("LLM_MODEL", "gpt-4o-mini")
# We use a distinct model for Mind if specified
mind_model_name = os.environ.get("OPENROUTER_MODEL", llm_model)

mind_llm = ChatLiteLLM(model=mind_model_name, max_retries=3, temperature=0.2)
worker_llm = ChatLiteLLM(model=llm_model, max_retries=3, temperature=0.0)

# ============================================================================
# LOGGER
# ============================================================================
logger = logging.getLogger("swarmdev.aci")
