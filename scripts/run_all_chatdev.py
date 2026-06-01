"""
Run the ChatDev Agnostic Evaluator across ALL DevEval Python projects.
Usage:
    .venv\\Scripts\\python scripts/run_all_chatdev.py
    .venv\\Scripts\\python scripts/run_all_chatdev.py --model GPT_4
"""
import os
import sys
import subprocess
import time

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEVEVAL_PYTHON_DIR = os.path.join(PROJECT_ROOT, "DevEval", "benchmark_data", "python")


def main():
    import argparse
    parser = argparse.ArgumentParser(
        description="Run ChatDev benchmark on all DevEval projects"
    )
    parser.add_argument(
        "--model", type=str, default="GPT_3_5_TURBO",
        help="LLM model for ChatDev (e.g., GPT_3_5_TURBO, GPT_4)",
    )
    args = parser.parse_args()

    if not os.path.exists(DEVEVAL_PYTHON_DIR):
        print(f"[Error] DevEval benchmark directory not found at {DEVEVAL_PYTHON_DIR}")
        sys.exit(1)

    projects = sorted([
        d for d in os.listdir(DEVEVAL_PYTHON_DIR)
        if os.path.isdir(os.path.join(DEVEVAL_PYTHON_DIR, d))
    ])

    if not projects:
        print("[Error] No projects found in the DevEval directory.")
        sys.exit(1)

    print(f"{'='*60}")
    print(f"  ChatDev Agnostic Evaluator — Full Benchmark Run")
    print(f"  Projects: {len(projects)}")
    print(f"  Model: {args.model}")
    print(f"{'='*60}\n")

    for i, project in enumerate(projects, 1):
        print(f"\n[{i}/{len(projects)}] >>> {project}")

        cmd = [
            sys.executable, "-u", "-X", "utf8",
            os.path.join(PROJECT_ROOT, "scripts", "run_chatdev_benchmark.py"),
            "--project", project,
            "--language", "python",
            "--model", args.model,
        ]

        try:
            subprocess.run(cmd, check=False)
            print(f"[{i}/{len(projects)}] <<< {project} done")
        except KeyboardInterrupt:
            print("\n[!] Interrupted by user. Exiting...")
            break
        except Exception as e:
            print(f"[{i}/{len(projects)}] <<< {project} ERROR: {e}")

        time.sleep(2)

    print(f"\n{'='*60}")
    print("  Benchmark Completato!")
    print(f"  Reports:  {os.path.join(PROJECT_ROOT, 'workspace', 'chatdev_reports')}")
    print(f"  CSV:      {os.path.join(PROJECT_ROOT, 'workspace', 'chatdev_summary.csv')}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
