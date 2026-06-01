"""
SwarmDev Parallel — Valutatore Agnostico Indipendente
=====================================================
Runs the full SwarmDev pipeline end-to-end on a DevEval PRD,
then evaluates the *generated* project using:
  1. Self-Testing  — runs the tests SwarmDev itself wrote (pytest)
  2. Static Analysis — Cyclomatic Complexity & Maintainability Index (radon)
  3. Cognitive Metrics — tokens, OCL retries, ChromaDB hits
"""

import os
import sys
import json
import csv
import glob
import subprocess
import argparse
from datetime import datetime
from typing import Optional

# ── Force UTF-8 on Windows ──────────────────────────────────────────────────
if sys.stdout.encoding != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except AttributeError:
        pass
if sys.stderr.encoding != "utf-8":
    try:
        sys.stderr.reconfigure(encoding="utf-8")
    except AttributeError:
        pass
os.environ["PYTHONIOENCODING"] = "utf-8"
os.environ["PYTHONUTF8"] = "1"

# ── Project root ─────────────────────────────────────────────────────────────
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from dotenv import load_dotenv
load_dotenv()

# ═══════════════════════════════════════════════════════════════════════════════
# 1. CHROMADB TRACKER
# ═══════════════════════════════════════════════════════════════════════════════
class ChromaDBTracker:
    queries_count = 0
    hits_count = 0

    @classmethod
    def reset(cls):
        cls.queries_count = 0
        cls.hits_count = 0


def _mocked_chromadb_query_raw(error_text: str, n_results: int = 3) -> Optional[dict]:
    ChromaDBTracker.queries_count += 1
    res = _original_chromadb_query_raw(error_text, n_results)
    if res and "documents" in res and res["documents"]:
        docs = res["documents"][0] if isinstance(res["documents"], list) else []
        distances = res.get("distances", [[]])[0] if isinstance(res.get("distances"), list) else []
        for i, doc in enumerate(docs):
            dist = distances[i] if i < len(distances) else 0.0
            if dist < 0.5:
                ChromaDBTracker.hits_count += 1
    return res


import graph.aci
import graph.nodes.familiarity
_original_chromadb_query_raw = graph.aci._chromadb_query_raw
graph.aci._chromadb_query_raw = _mocked_chromadb_query_raw
graph.nodes.familiarity._chromadb_query_raw = _mocked_chromadb_query_raw

# ═══════════════════════════════════════════════════════════════════════════════
# 2. AUTO-CLIENT PRODUCT OWNER
# ═══════════════════════════════════════════════════════════════════════════════
AUTO_CLIENT_SYSTEM_PROMPT = """\
You are an automated 'Auto-Client' acting as a Product Owner for a software development task.
Your role is to answer questions posed by the development team (an autonomous swarm) to clarify the project requirements.

You MUST base your answers strictly and exclusively on the specifications written in the provided Product Requirement Document (PRD).

Guidelines:
1. Consult the PRD to answer any detail, constraint, API requirement, CLI argument, output formatting, or business logic.
2. If the swarm asks for specific details, implementation choices, or architectural designs that are NOT defined or present in the PRD, you must explicitly state that the detail is not specified in the PRD and that the swarm is free to choose the best architectural/implementation path according to the swarm's best practices.
3. Keep your answers brief, concise, and focused. Do not invent details or assume constraints not present in the PRD.
4. CRITICAL: NEVER engage in polite small talk, farewells, or thank you loops. If the swarm thanks you, ignore it or say "Proceed."
5. CRITICAL: When the swarm proposes a design or implementation plan that looks good, you MUST explicitly command them to approve it by saying exactly: "I explicitly approve this design. Please proceed immediately to emit the DESIGN_APPROVED trigger and move to the next phase."

Here is the PRD for the project:
=== PRD.md ===
{prd_content}
==============
"""


class AutoClientPO:
    def __init__(self, prd_content: str, model: str):
        from langchain_litellm import ChatLiteLLM
        from langchain_core.messages import SystemMessage
        self.llm = ChatLiteLLM(model=model, max_retries=3, temperature=0.1)
        self.system_message = SystemMessage(
            content=AUTO_CLIENT_SYSTEM_PROMPT.format(prd_content=prd_content)
        )
        self.chat_history = []

    def answer_question(self, question: str) -> str:
        from langchain_core.messages import HumanMessage
        messages = [self.system_message] + self.chat_history + [HumanMessage(content=question)]
        response = self.llm.invoke(messages)
        answer = response.content.strip()
        self.chat_history.append(HumanMessage(content=question))
        self.chat_history.append(response)
        return answer


# ═══════════════════════════════════════════════════════════════════════════════
# 3. GOALS EXTRACTION
# ═══════════════════════════════════════════════════════════════════════════════
def extract_goals_from_prd(prd_path: str) -> str:
    if not os.path.exists(prd_path):
        raise FileNotFoundError(f"PRD not found at {prd_path}")
    with open(prd_path, "r", encoding="utf-8") as f:
        content = f.read()
    lines = content.splitlines()
    goals = []
    in_goals = False
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("#"):
            header = stripped.lstrip("#").strip().lower()
            if header == "goals":
                in_goals = True
                continue
            elif in_goals:
                break
        if in_goals:
            goals.append(line)
    goals_text = "\n".join(goals).strip()
    if not goals_text:
        goals_text = "I want to implement this project based on the PRD."
    return goals_text


# ═══════════════════════════════════════════════════════════════════════════════
# 4. HUMAN_NODE MONKEYPATCH (Auto-Client drives Discovery)
# ═══════════════════════════════════════════════════════════════════════════════
import graph.nodes.mind
from langchain_core.messages import HumanMessage

prd_path_global = ""
auto_client_global: Optional[AutoClientPO] = None


def _mocked_human_node(state):
    history = state.get("chat_history", [])
    if not history:
        goals = extract_goals_from_prd(prd_path_global)
        print(f"\n[Auto-Client PO Initial Prompt]: {goals}\n")
        user_input = goals
    else:
        last_message = history[-1]
        question = last_message.content
        print(f"\n[Swarm Question]: {question}\n")
        if auto_client_global:
            user_input = auto_client_global.answer_question(question)
        else:
            user_input = "continue"
        print(f"\n[Auto-Client PO Answer]: {user_input}\n")
    history.append(HumanMessage(content=user_input))
    graph.nodes.mind.episodic_buffer.record(
        task_id=state.get("task_id"),
        node_name="human_node",
        input_data={"chat_history_len": len(history) - 1},
        output_data={"user_input": user_input},
    )
    return {"chat_history": history}


# Apply patch BEFORE importing orchestrator
graph.nodes.mind.human_node = _mocked_human_node

from graph_orchestrator import build_orchestrator, ensure_services_running
from graph.context import mind_model_name


# ═══════════════════════════════════════════════════════════════════════════════
# 5. SELF-TESTING — run SwarmDev's own pytest suite
# ═══════════════════════════════════════════════════════════════════════════════
def run_self_tests(backend_dir: str) -> dict:
    """Run pytest on the tests SwarmDev generated inside `backend_dir`.
    Returns dict with passed, failed, errors, total, pass_rate."""
    result = {
        "passed": 0, "failed": 0, "errors": 0,
        "total": 0, "pass_rate": 0.0, "output": "",
    }

    # Check if there are any test files at all
    test_files = (
        glob.glob(os.path.join(backend_dir, "tests", "test_*.py"))
        + glob.glob(os.path.join(backend_dir, "tests", "**", "test_*.py"), recursive=True)
        + glob.glob(os.path.join(backend_dir, "test_*.py"))
    )
    if not test_files:
        print("[Self-Test] No test files found in backend directory.")
        return result

    # Install backend deps if requirements.txt exists
    req_path = os.path.join(backend_dir, "requirements.txt")
    if os.path.exists(req_path):
        print(f"[Self-Test] Installing backend dependencies from {req_path}...")
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "-r", req_path, "--quiet"],
            cwd=backend_dir, capture_output=True, text=True,
        )

    # Also install common test deps
    subprocess.run(
        [sys.executable, "-m", "pip", "install", "pytest", "pytest-asyncio",
         "pytest-mock", "pytest-json-report", "--quiet"],
        capture_output=True, text=True,
    )

    report_path = os.path.join(backend_dir, "_self_test_report.json")

    cmd = [
        sys.executable, "-m", "pytest",
        "--json-report", f"--json-report-file={report_path}",
        "--tb=short", "-q",
    ]

    print(f"[Self-Test] Running: {' '.join(cmd)}")
    proc = subprocess.run(cmd, cwd=backend_dir, capture_output=True, text=True, timeout=120)
    result["output"] = proc.stdout + "\n" + proc.stderr

    if os.path.exists(report_path):
        with open(report_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        summary = data.get("summary", {})
        result["passed"] = summary.get("passed", 0)
        result["failed"] = summary.get("failed", 0)
        result["errors"] = summary.get("error", 0)
        result["total"] = summary.get("total", 0)
    else:
        # Fallback: parse exit code
        print(f"[Self-Test] JSON report not found, parsing exit code ({proc.returncode})")
        if proc.returncode == 0:
            result["passed"] = 1
            result["total"] = 1
        else:
            result["failed"] = 1
            result["total"] = 1

    if result["total"] > 0:
        result["pass_rate"] = round(result["passed"] / result["total"] * 100, 2)

    print(f"[Self-Test] Results: {result['passed']}/{result['total']} passed "
          f"({result['pass_rate']}%)")
    return result


# ═══════════════════════════════════════════════════════════════════════════════
# 6. STATIC ANALYSIS — Radon CC + MI
# ═══════════════════════════════════════════════════════════════════════════════
def run_radon_analysis(backend_dir: str) -> dict:
    """Run radon cc and radon mi on all .py files in backend_dir.
    Returns dict with avg_cc, avg_mi, details."""
    result = {"avg_cc": 0.0, "avg_mi": 0.0, "cc_details": [], "mi_details": []}

    py_files = glob.glob(os.path.join(backend_dir, "**", "*.py"), recursive=True)
    # Exclude test files, __pycache__, and hidden dirs
    py_files = [
        f for f in py_files
        if "__pycache__" not in f
        and not os.path.basename(f).startswith("test_")
        and not f.endswith("_pm2_launcher.js")
    ]
    if not py_files:
        print("[Radon] No Python source files found for analysis.")
        return result

    # ── Cyclomatic Complexity ────────────────────────────────────────────────
    try:
        cc_cmd = [sys.executable, "-m", "radon", "cc", "-j", "-a"] + py_files
        cc_proc = subprocess.run(cc_cmd, capture_output=True, text=True, timeout=60)
        if cc_proc.returncode == 0 and cc_proc.stdout.strip():
            cc_data = json.loads(cc_proc.stdout)
            all_cc = []
            for filepath, blocks in cc_data.items():
                for block in blocks:
                    complexity = block.get("complexity", 0)
                    all_cc.append(complexity)
                    result["cc_details"].append({
                        "file": os.path.basename(filepath),
                        "name": block.get("name", "?"),
                        "type": block.get("type", "?"),
                        "complexity": complexity,
                        "rank": block.get("rank", "?"),
                    })
            if all_cc:
                result["avg_cc"] = round(sum(all_cc) / len(all_cc), 2)
        print(f"[Radon] Cyclomatic Complexity — avg: {result['avg_cc']} "
              f"({len(result['cc_details'])} blocks analyzed)")
    except Exception as e:
        print(f"[Radon] CC analysis failed: {e}")

    # ── Maintainability Index ────────────────────────────────────────────────
    try:
        mi_cmd = [sys.executable, "-m", "radon", "mi", "-j"] + py_files
        mi_proc = subprocess.run(mi_cmd, capture_output=True, text=True, timeout=60)
        if mi_proc.returncode == 0 and mi_proc.stdout.strip():
            mi_data = json.loads(mi_proc.stdout)
            all_mi = []
            for filepath, mi_val in mi_data.items():
                # radon mi -j returns either a float or {"mi": float, "rank": str}
                if isinstance(mi_val, dict):
                    score = mi_val.get("mi", 0.0)
                elif isinstance(mi_val, (int, float)):
                    score = mi_val
                else:
                    continue
                all_mi.append(score)
                result["mi_details"].append({
                    "file": os.path.basename(filepath),
                    "mi": round(score, 2),
                })
            if all_mi:
                result["avg_mi"] = round(sum(all_mi) / len(all_mi), 2)
        print(f"[Radon] Maintainability Index — avg: {result['avg_mi']} "
              f"({len(result['mi_details'])} files analyzed)")
    except Exception as e:
        print(f"[Radon] MI analysis failed: {e}")

    return result


# ═══════════════════════════════════════════════════════════════════════════════
# 7. METRICS PERSISTENCE
# ═══════════════════════════════════════════════════════════════════════════════
CSV_HEADERS = [
    "timestamp", "project_name", "total_tokens", "ocl_retry_count",
    "self_test_pass_rate", "avg_cc", "avg_mi", "chromadb_hits",
]


def save_metrics(
    project_name: str,
    total_tokens: int,
    ocl_retry_count: int,
    self_test_pass_rate: float,
    avg_cc: float,
    avg_mi: float,
    chromadb_hits: int,
    extra: Optional[dict] = None,
):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    metrics = {
        "timestamp": timestamp,
        "project_name": project_name,
        "total_tokens": total_tokens,
        "ocl_retry_count": ocl_retry_count,
        "self_test_pass_rate": self_test_pass_rate,
        "avg_cc": avg_cc,
        "avg_mi": avg_mi,
        "chromadb_hits": chromadb_hits,
    }
    if extra:
        metrics["extra"] = extra

    # ── JSON report ──────────────────────────────────────────────────────────
    reports_dir = os.path.join(PROJECT_ROOT, "workspace", "deveval_reports")
    os.makedirs(reports_dir, exist_ok=True)
    safe_name = project_name.replace("/", "_").replace("\\", "_")
    json_path = os.path.join(
        reports_dir, f"{safe_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    )
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(metrics, f, indent=2)
    print(f"[Metrics] Saved JSON report: {json_path}")

    # ── CSV summary ──────────────────────────────────────────────────────────
    workspace_dir = os.path.join(PROJECT_ROOT, "workspace")
    csv_path = os.path.join(workspace_dir, "deveval_summary_run3.csv")
    file_exists = os.path.exists(csv_path)
    with open(csv_path, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(CSV_HEADERS)
        writer.writerow([
            timestamp, project_name, total_tokens, ocl_retry_count,
            self_test_pass_rate, avg_cc, avg_mi, chromadb_hits,
        ])
    print(f"[Metrics] Updated CSV summary: {csv_path}")


# ═══════════════════════════════════════════════════════════════════════════════
# 8. MAIN
# ═══════════════════════════════════════════════════════════════════════════════
def main():
    parser = argparse.ArgumentParser(
        description="SwarmDev Parallel — Valutatore Agnostico Indipendente"
    )
    parser.add_argument(
        "--project", type=str, default="ArXiv_digest",
        help="DevEval project name (used to locate the PRD)",
    )
    parser.add_argument(
        "--language", type=str, default="python",
        help="Project programming language",
    )
    parser.add_argument(
        "--auto-client-model", type=str, default=None,
        help="LLM model name for Auto-Client PO (defaults to Mind model)",
    )
    args = parser.parse_args()

    global prd_path_global, auto_client_global

    # ── Locate PRD ───────────────────────────────────────────────────────────
    deveval_dir = os.path.join(PROJECT_ROOT, "DevEval")
    project_dir = os.path.join(deveval_dir, "benchmark_data", args.language, args.project)
    if not os.path.exists(project_dir):
        print(f"[Error] Project directory not found: {project_dir}")
        sys.exit(1)

    # Try common PRD locations
    for prd_candidate in ["docs/PRD.md", "PRD.md"]:
        candidate = os.path.join(project_dir, prd_candidate)
        if os.path.exists(candidate):
            prd_path_global = candidate
            break
    if not prd_path_global:
        print(f"[Error] PRD.md not found in {project_dir}")
        sys.exit(1)

    print(f"[Benchmark] PRD: {prd_path_global}")
    with open(prd_path_global, "r", encoding="utf-8") as f:
        prd_content = f.read()

    # ── Init Auto-Client ─────────────────────────────────────────────────────
    ac_model = args.auto_client_model or mind_model_name
    print(f"[Benchmark] Auto-Client model: {ac_model}")
    auto_client_global = AutoClientPO(prd_content, ac_model)

    # ── Start services ───────────────────────────────────────────────────────
    ensure_services_running()

    # ── Build & run orchestrator ─────────────────────────────────────────────
    orchestrator = build_orchestrator()

    import uuid
    task_id = f"task_{uuid.uuid4().hex[:12]}"
    initial_state = {
        "task_id": task_id,
        "chat_history": [],
        "design_doc": None,
        "ocl_errors": None,
        "json_contract": None,
        "retry_count": 0,
        "ocl_retry_count": 0,
        "total_tokens": 0,
        "frontend_code": None,
        "backend_code": None,
        "frontend_errors": None,
        "backend_errors": None,
        "documentation_ready": False,
        "documentation_path": None,
        "uml_diagram_path": None,
        "uml_diagram_error": None,
        "kanban_frontend_issue_id": None,
        "kanban_backend_issue_id": None,
        "kanban_error": None,
        "frontend_rag_context": None,
        "backend_rag_context": None,
        "runtime_errors": None,
        "runtime_retry_count": 0,
    }

    ChromaDBTracker.reset()
    print(f"\n{'='*60}")
    print(f"  SwarmDev DAG — {args.project}")
    print(f"{'='*60}\n")

    try:
        final_state = orchestrator.invoke(initial_state)
        print("\n[Benchmark] SwarmDev DAG execution completed.")
    except Exception as e:
        print(f"\n[Benchmark] SwarmDev DAG failed: {e}")
        save_metrics(
            project_name=args.project,
            total_tokens=0, ocl_retry_count=0,
            self_test_pass_rate=0.0, avg_cc=0.0, avg_mi=0.0,
            chromadb_hits=0, extra={"status": "DAG_FAILURE", "error": str(e)},
        )
        sys.exit(1)

    # ── Extract SwarmDev metrics ─────────────────────────────────────────────
    total_tokens = final_state.get("total_tokens", 0)
    ocl_retry_count = final_state.get("ocl_retry_count", 0)
    doc_path = final_state.get("documentation_path")

    if not doc_path or not os.path.exists(doc_path):
        print("[Benchmark] No documentation_path found. Searching latest workspace...")
        workspace_base = os.path.join(PROJECT_ROOT, "workspace")
        candidates = sorted(
            glob.glob(os.path.join(workspace_base, "project_*")),
            key=os.path.getmtime, reverse=True,
        )
        if candidates:
            doc_path = candidates[0]
            print(f"[Benchmark] Using latest workspace: {doc_path}")
        else:
            print("[Benchmark] No workspace found!")
            save_metrics(
                project_name=args.project,
                total_tokens=total_tokens, ocl_retry_count=ocl_retry_count,
                self_test_pass_rate=0.0, avg_cc=0.0, avg_mi=0.0,
                chromadb_hits=ChromaDBTracker.hits_count,
                extra={"status": "NO_WORKSPACE"},
            )
            sys.exit(0)

    backend_dir = os.path.join(doc_path, "backend")
    if not os.path.exists(backend_dir):
        print(f"[Benchmark] Backend directory not found at {backend_dir}")
        save_metrics(
            project_name=args.project,
            total_tokens=total_tokens, ocl_retry_count=ocl_retry_count,
            self_test_pass_rate=0.0, avg_cc=0.0, avg_mi=0.0,
            chromadb_hits=ChromaDBTracker.hits_count,
            extra={"status": "NO_BACKEND_DIR"},
        )
        sys.exit(0)

    print(f"\n[Benchmark] Evaluating workspace: {doc_path}")
    print(f"[Benchmark] Backend directory: {backend_dir}")

    # ── METRICA 1: Self-Testing ──────────────────────────────────────────────
    print(f"\n{'─'*60}")
    print("  METRICA 1: Self-Testing (pytest sui test generati dallo Swarm)")
    print(f"{'─'*60}")
    test_results = run_self_tests(backend_dir)

    # ── METRICA 2: Static Analysis (Radon) ───────────────────────────────────
    print(f"\n{'─'*60}")
    print("  METRICA 2: Analisi Statica (Radon CC + MI)")
    print(f"{'─'*60}")
    radon_results = run_radon_analysis(backend_dir)

    # ── Save all metrics ─────────────────────────────────────────────────────
    print(f"\n{'='*60}")
    print("  REPORT FINALE")
    print(f"{'='*60}")
    print(f"  Project:              {args.project}")
    print(f"  Total Tokens:         {total_tokens}")
    print(f"  OCL Retry Count:      {ocl_retry_count}")
    print(f"  Self-Test Pass Rate:  {test_results['pass_rate']}%")
    print(f"  Avg CC:               {radon_results['avg_cc']}")
    print(f"  Avg MI:               {radon_results['avg_mi']}")
    print(f"  ChromaDB Hits:        {ChromaDBTracker.hits_count}")
    print(f"{'='*60}\n")

    save_metrics(
        project_name=args.project,
        total_tokens=total_tokens,
        ocl_retry_count=ocl_retry_count,
        self_test_pass_rate=test_results["pass_rate"],
        avg_cc=radon_results["avg_cc"],
        avg_mi=radon_results["avg_mi"],
        chromadb_hits=ChromaDBTracker.hits_count,
        extra={
            "status": "COMPLETED",
            "workspace": doc_path,
            "self_test_details": {
                "passed": test_results["passed"],
                "failed": test_results["failed"],
                "errors": test_results["errors"],
                "total": test_results["total"],
            },
            "radon_cc_details": radon_results["cc_details"],
            "radon_mi_details": radon_results["mi_details"],
            "chromadb_queries": ChromaDBTracker.queries_count,
        },
    )


if __name__ == "__main__":
    main()
