"""
ChatDev — Valutatore Agnostico Indipendente (Baseline di Confronto)
====================================================================
Runs the full ChatDev pipeline end-to-end on a DevEval PRD,
then evaluates the *generated* project using the SAME metrics
as SwarmDev's run_deveval_benchmark.py:

  1. Self-Testing  — runs pytest on the generated tests (if any)
  2. Static Analysis — Cyclomatic Complexity & Maintainability Index (radon)
  3. Cognitive Metrics — total tokens (from ChatDev logs)

This script enables an apples-to-apples comparison between SwarmDev and ChatDev.
"""

import os
import sys
import json
import csv
import glob
import re
import subprocess
import argparse
from datetime import datetime
from typing import Optional
from dotenv import load_dotenv

load_dotenv()  # Ensure .env variables are loaded

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
CHATDEV_ROOT = os.path.join(PROJECT_ROOT, "ChatDev")
DEVEVAL_DIR = os.path.join(PROJECT_ROOT, "DevEval", "benchmark_data", "python")


# ═══════════════════════════════════════════════════════════════════════════════
# 1. GOALS EXTRACTION (identical to SwarmDev's)
# ═══════════════════════════════════════════════════════════════════════════════
def extract_goals_from_prd(prd_path: str) -> str:
    """Extract the Goals section from a DevEval PRD.md."""
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


def build_task_prompt(prd_path: str) -> str:
    """Build the task prompt using ONLY the Goals section from the PRD
    to ensure a 1:1 identical comparison with SwarmDev's input.
    """
    goals = extract_goals_from_prd(prd_path)
    return goals


# ═══════════════════════════════════════════════════════════════════════════════
# 2. CHATDEV EXECUTION
# ═══════════════════════════════════════════════════════════════════════════════
def run_chatdev(
    task_prompt: str,
    project_name: str,
    model: str = "GPT_3_5_TURBO",
    org: str = "DevEvalBenchmark",
) -> Optional[str]:
    """Run ChatDev on a task and return the output directory path.
    
    ChatDev 2.0 uses YAML-based workflows and reads the task prompt via input().
    We pipe the prompt through stdin to run non-interactively.
    """
    
    run_py = os.path.join(CHATDEV_ROOT, "run.py")
    if not os.path.exists(run_py):
        print(f"[ChatDev] ERROR: run.py not found at {run_py}")
        return None

    # Use the ChatDev_v1.yaml workflow which emulates the classic pipeline
    workflow_path = os.path.join(
        CHATDEV_ROOT, "yaml_instance", "ChatDev_v1.yaml"
    )
    if not os.path.exists(workflow_path):
        print(f"[ChatDev] ERROR: ChatDev_v1.yaml not found at {workflow_path}")
        return None

    chatdev_python = os.path.join(CHATDEV_ROOT, ".venv", "Scripts", "python.exe")
    if not os.path.exists(chatdev_python):
        print(f"[ChatDev] ERROR: Python environment not found at {chatdev_python}. Please run 'python -m venv ChatDev\\.venv' and install requirements.")
        return None

    cmd = [
        chatdev_python, run_py,
        "--path", workflow_path,
        "--name", project_name,
    ]
    
    print(f"[ChatDev] Launching: python run.py --path ChatDev_v1.yaml --name \"{project_name}\"")
    print(f"[ChatDev] Task prompt length: {len(task_prompt)} chars")
    
    log_path = os.path.join(
        PROJECT_ROOT, "workspace", "chatdev_logs",
        f"{project_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
    )
    os.makedirs(os.path.dirname(log_path), exist_ok=True)

    # ChatDev_v1.yaml requires BASE_URL and API_KEY environment variables
    env = os.environ.copy()
    
    # ── Usa OpenRouter se configurato, altrimenti OpenAI di default ──
    if env.get("OPENROUTER_API_KEY"):
        env["BASE_URL"] = "https://openrouter.ai/api/v1"
        env["API_KEY"] = env.get("OPENROUTER_API_KEY")
        # Forza il modello OpenRouter se definito in .env
        env["MODEL_NAME"] = env.get("OPENROUTER_MODEL", model)
    else:
        env["BASE_URL"] = env.get("BASE_URL", "https://api.openai.com/v1")
        env["API_KEY"] = env.get("API_KEY", env.get("OPENAI_API_KEY", ""))
        env["MODEL_NAME"] = model

    try:
        with open(log_path, "w", encoding="utf-8") as log_file:
            proc = subprocess.run(
                cmd,
                cwd=CHATDEV_ROOT,
                env=env,
                input=task_prompt,  # Pipe the prompt to stdin (input())
                stdout=log_file,
                stderr=subprocess.STDOUT,
                timeout=1800,  # Increased to 30 min max per project
                text=True,
            )
        print(f"[ChatDev] Process exited with code {proc.returncode}")
        print(f"[ChatDev] Full log at: {log_path}")
    except subprocess.TimeoutExpired:
        print(f"[ChatDev] TIMEOUT after 1800s for project: {project_name}")
        return None
    except Exception as e:
        print(f"[ChatDev] EXCEPTION: {e}")
        return None
    
    # Find the output directory in WareHouse/
    warehouse = os.path.join(CHATDEV_ROOT, "WareHouse")
    if not os.path.exists(warehouse):
        print(f"[ChatDev] WareHouse directory not found at {warehouse}")
        return None
    
    # ChatDev 2.0 naming pattern: {name}_{timestamp} or {name}/
    candidates = sorted(
        [d for d in glob.glob(os.path.join(warehouse, f"{project_name}*"))
         if os.path.isdir(d)],
        key=os.path.getmtime,
        reverse=True,
    )
    
    if candidates:
        output_dir = candidates[0]
        print(f"[ChatDev] Output directory: {output_dir}")
        return output_dir
    
    print(f"[ChatDev] No output directory found in WareHouse for {project_name}")
    return None


# ═══════════════════════════════════════════════════════════════════════════════
# 3. TOKEN EXTRACTION (from ChatDev logs)
# ═══════════════════════════════════════════════════════════════════════════════
def extract_tokens_from_log(log_dir: str) -> int:
    """Extract total token usage from ChatDev's output directory.
    
    ChatDev 2.0 saves a structured JSON file: token_usage_{name}.json
    containing total_usage.total_tokens.
    Falls back to regex parsing of log files.
    """
    total_tokens = 0
    
    # ── PRIMARY: Read the structured token_usage JSON ────────────────────────
    token_files = glob.glob(os.path.join(log_dir, "token_usage_*.json"))
    for tf in token_files:
        try:
            with open(tf, "r", encoding="utf-8") as f:
                data = json.load(f)
            total_usage = data.get("total_usage", {})
            tokens = total_usage.get("total_tokens", 0)
            if tokens > 0:
                total_tokens = tokens
                print(f"[Tokens] From structured JSON: {total_tokens}")
                return total_tokens
        except Exception:
            continue
    
    # ── FALLBACK: Parse log files ────────────────────────────────────────────
    log_files = (
        glob.glob(os.path.join(log_dir, "*.log"))
        + glob.glob(os.path.join(log_dir, "execution_logs.json"))
    )
    
    for log_file in log_files:
        try:
            with open(log_file, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
            
            # Pattern: "total_tokens": NNNN
            token_matches = re.findall(r'"total_tokens"\s*:\s*(\d+)', content)
            if token_matches:
                total_tokens = sum(int(t) for t in token_matches)
        except Exception:
            continue
    
    # Also check the execution log directory
    parent_log_dir = os.path.join(PROJECT_ROOT, "workspace", "chatdev_logs")
    if os.path.exists(parent_log_dir):
        for log_file in sorted(
            glob.glob(os.path.join(parent_log_dir, "*.log")),
            key=os.path.getmtime, reverse=True
        ):
            try:
                with open(log_file, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
                matches = re.findall(r'"total_tokens"\s*:\s*(\d+)', content)
                if matches:
                    found = max(int(m) for m in matches)
                    total_tokens = max(total_tokens, found)
                    break  # Use the most recent log
            except Exception:
                continue
    
    print(f"[Tokens] Extracted total tokens: {total_tokens}")
    return total_tokens


# ═══════════════════════════════════════════════════════════════════════════════
# 4. SELF-TESTING — run pytest on generated tests
# ═══════════════════════════════════════════════════════════════════════════════
def run_self_tests(project_dir: str) -> dict:
    """Run pytest on any test files found in the project directory.
    Returns dict with passed, failed, errors, total, pass_rate."""
    result = {
        "passed": 0, "failed": 0, "errors": 0,
        "total": 0, "pass_rate": 0.0, "output": "",
    }

    # ChatDev outputs flat file structures — look for test files anywhere
    test_files = (
        glob.glob(os.path.join(project_dir, "test_*.py"))
        + glob.glob(os.path.join(project_dir, "tests", "test_*.py"))
        + glob.glob(os.path.join(project_dir, "tests", "**", "test_*.py"), recursive=True)
        + glob.glob(os.path.join(project_dir, "*test*.py"))
    )
    # Deduplicate
    test_files = list(set(test_files))

    if not test_files:
        print("[Self-Test] No test files found in ChatDev output.")
        return result

    print(f"[Self-Test] Found {len(test_files)} test file(s)")

    # Install project deps if requirements.txt exists
    req_path = os.path.join(project_dir, "requirements.txt")
    if os.path.exists(req_path):
        print(f"[Self-Test] Installing dependencies from {req_path}...")
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "-r", req_path, "--quiet"],
            cwd=project_dir, capture_output=True, text=True,
        )

    # Install test deps
    subprocess.run(
        [sys.executable, "-m", "pip", "install", "pytest", "pytest-asyncio",
         "pytest-mock", "pytest-json-report", "--quiet"],
        capture_output=True, text=True,
    )

    report_path = os.path.join(project_dir, "_self_test_report.json")

    cmd = [
        sys.executable, "-m", "pytest",
        "--json-report", f"--json-report-file={report_path}",
        "--tb=short", "-q",
    ]

    print(f"[Self-Test] Running: {' '.join(cmd)}")
    try:
        proc = subprocess.run(
            cmd, cwd=project_dir, capture_output=True, text=True, timeout=120
        )
        result["output"] = proc.stdout + "\n" + proc.stderr
    except subprocess.TimeoutExpired:
        print("[Self-Test] TIMEOUT after 120s")
        return result

    if os.path.exists(report_path):
        with open(report_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        summary = data.get("summary", {})
        result["passed"] = summary.get("passed", 0)
        result["failed"] = summary.get("failed", 0)
        result["errors"] = summary.get("error", 0)
        result["total"] = summary.get("total", 0)
    else:
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
# 5. STATIC ANALYSIS — Radon CC + MI (identical to SwarmDev's)
# ═══════════════════════════════════════════════════════════════════════════════
def run_radon_analysis(project_dir: str) -> dict:
    """Run radon cc and radon mi on all .py files in project_dir.
    Returns dict with avg_cc, avg_mi, details."""
    result = {"avg_cc": 0.0, "avg_mi": 0.0, "cc_details": [], "mi_details": []}

    py_files = glob.glob(os.path.join(project_dir, "**", "*.py"), recursive=True)
    py_files = [
        f for f in py_files
        if "__pycache__" not in f
        and not os.path.basename(f).startswith("test_")
    ]
    if not py_files:
        print("[Radon] No Python source files found for analysis.")
        return result

    # ── Rimuovi BOM (U+FEFF) generato da ChatDev su Windows ──────────────────
    for fpath in py_files:
        try:
            with open(fpath, "r", encoding="utf-8-sig") as f:
                content = f.read()
            with open(fpath, "w", encoding="utf-8") as f:
                f.write(content)
        except Exception:
            pass

    # ── Cyclomatic Complexity ────────────────────────────────────────────────
    try:
        cc_cmd = [sys.executable, "-m", "radon", "cc", "-j", "-a"] + py_files
        cc_proc = subprocess.run(cc_cmd, capture_output=True, text=True, timeout=60)
        if cc_proc.returncode == 0 and cc_proc.stdout.strip():
            cc_data = json.loads(cc_proc.stdout)
            all_cc = []
            for filepath, blocks in cc_data.items():
                if isinstance(blocks, dict) and "error" in blocks:
                    print(f"[Radon] CC Error in {filepath}: {blocks['error']}")
                    continue
                if isinstance(blocks, str):
                    continue
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
                if isinstance(mi_val, dict):
                    if "error" in mi_val:
                        print(f"[Radon] MI Error in {filepath}: {mi_val['error']}")
                        continue
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
# 6. METRICS PERSISTENCE (same CSV format as SwarmDev for easy comparison)
# ═══════════════════════════════════════════════════════════════════════════════
CSV_HEADERS = [
    "timestamp", "framework", "project_name", "total_tokens",
    "self_test_pass_rate", "avg_cc", "avg_mi",
]


def save_metrics(
    project_name: str,
    total_tokens: int,
    self_test_pass_rate: float,
    avg_cc: float,
    avg_mi: float,
    extra: Optional[dict] = None,
):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    metrics = {
        "timestamp": timestamp,
        "framework": "ChatDev",
        "project_name": project_name,
        "total_tokens": total_tokens,
        "self_test_pass_rate": self_test_pass_rate,
        "avg_cc": avg_cc,
        "avg_mi": avg_mi,
    }
    if extra:
        metrics["extra"] = extra

    # ── JSON report ──────────────────────────────────────────────────────────
    reports_dir = os.path.join(PROJECT_ROOT, "workspace", "chatdev_reports")
    os.makedirs(reports_dir, exist_ok=True)
    safe_name = project_name.replace("/", "_").replace("\\", "_")
    json_path = os.path.join(
        reports_dir, f"{safe_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    )
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(metrics, f, indent=2)
    print(f"[Metrics] Saved JSON report: {json_path}")

    # ── CSV summary ──────────────────────────────────────────────────────────
    csv_path = os.path.join(PROJECT_ROOT, "workspace", "chatdev_summary.csv")
    file_exists = os.path.exists(csv_path)
    with open(csv_path, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(CSV_HEADERS)
        writer.writerow([
            timestamp, "ChatDev", project_name, total_tokens,
            self_test_pass_rate, avg_cc, avg_mi,
        ])
    print(f"[Metrics] Updated CSV summary: {csv_path}")


# ═══════════════════════════════════════════════════════════════════════════════
# 7. MAIN
# ═══════════════════════════════════════════════════════════════════════════════
def main():
    parser = argparse.ArgumentParser(
        description="ChatDev — Valutatore Agnostico Indipendente (Baseline)"
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
        "--model", type=str, default="GPT_3_5_TURBO",
        help="LLM model for ChatDev (e.g., GPT_3_5_TURBO, GPT_4)",
    )
    args = parser.parse_args()

    # ── Locate PRD ───────────────────────────────────────────────────────────
    project_dir = os.path.join(DEVEVAL_DIR, args.project)
    if not os.path.exists(project_dir):
        print(f"[Error] Project directory not found: {project_dir}")
        sys.exit(1)

    prd_path = None
    for prd_candidate in ["docs/PRD.md", "PRD.md"]:
        candidate = os.path.join(project_dir, prd_candidate)
        if os.path.exists(candidate):
            prd_path = candidate
            break
    if not prd_path:
        print(f"[Error] PRD.md not found in {project_dir}")
        sys.exit(1)

    print(f"[Benchmark] PRD: {prd_path}")
    print(f"[Benchmark] Model: {args.model}")

    # ── Build task prompt ────────────────────────────────────────────────────
    task_prompt = build_task_prompt(prd_path)

    # ── Run ChatDev ──────────────────────────────────────────────────────────
    print(f"\n{'='*60}")
    print(f"  ChatDev Benchmark — {args.project}")
    print(f"{'='*60}\n")

    output_dir = run_chatdev(
        task_prompt=task_prompt,
        project_name=args.project,
        model=args.model,
    )

    if not output_dir:
        print("[Benchmark] ChatDev execution failed — no output directory.")
        save_metrics(
            project_name=args.project,
            total_tokens=0,
            self_test_pass_rate=0.0,
            avg_cc=0.0,
            avg_mi=0.0,
            extra={"status": "CHATDEV_FAILURE"},
        )
        sys.exit(1)

    # ── Extract tokens ───────────────────────────────────────────────────────
    total_tokens = extract_tokens_from_log(output_dir)

    # ── METRIC 1: Self-Testing ───────────────────────────────────────────────
    print(f"\n{'─'*60}")
    print("  METRICA 1: Self-Testing (pytest sui test generati da ChatDev)")
    print(f"{'─'*60}")
    test_results = run_self_tests(output_dir)

    # ── METRIC 2: Static Analysis (Radon) ────────────────────────────────────
    print(f"\n{'─'*60}")
    print("  METRICA 2: Analisi Statica (Radon CC + MI)")
    print(f"{'─'*60}")
    radon_results = run_radon_analysis(output_dir)

    # ── Save all metrics ─────────────────────────────────────────────────────
    print(f"\n{'='*60}")
    print("  REPORT FINALE (ChatDev)")
    print(f"{'='*60}")
    print(f"  Project:              {args.project}")
    print(f"  Total Tokens:         {total_tokens}")
    print(f"  Self-Test Pass Rate:  {test_results['pass_rate']}%")
    print(f"  Avg CC:               {radon_results['avg_cc']}")
    print(f"  Avg MI:               {radon_results['avg_mi']}")
    print(f"{'='*60}\n")

    save_metrics(
        project_name=args.project,
        total_tokens=total_tokens,
        self_test_pass_rate=test_results["pass_rate"],
        avg_cc=radon_results["avg_cc"],
        avg_mi=radon_results["avg_mi"],
        extra={
            "status": "COMPLETED",
            "output_dir": output_dir,
            "self_test_details": {
                "passed": test_results["passed"],
                "failed": test_results["failed"],
                "errors": test_results["errors"],
                "total": test_results["total"],
            },
            "radon_cc_details": radon_results["cc_details"],
            "radon_mi_details": radon_results["mi_details"],
        },
    )


if __name__ == "__main__":
    main()
