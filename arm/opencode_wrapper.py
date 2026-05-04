import subprocess
import os
import time
import re
from typing import List, Dict


class OpenCodeWrapper:
    def __init__(self, output_dir: str = "./workspace"):
        self.output_dir = output_dir
        os.makedirs(self.output_dir, exist_ok=True)



    def _sanitize_name(self, text: str) -> str:
        text = text.lower()
        text = re.sub(r"[<>:\"/\\|?*]", "", text)
        text = re.sub(r"[()]", "", text)
        text = re.sub(r"\s+", "_", text)
        text = re.sub(r"[^a-z0-9_]", "", text)
        return text[:80]

    # -----------------------------
    # PUBLIC API
    # -----------------------------
    def generate_code(self, context: str, contract_id: str, contract_json: str) -> tuple[List[Dict], str]:
        job_dir = self._create_job_dir(context)

        prompt = self._build_prompt(contract_id, contract_json)

        before = self._snapshot(job_dir)

        self._run_opencode(job_dir, prompt)

        after = self._snapshot(job_dir)

        changed_files = self._detect_changes(job_dir, before, after)

        if not changed_files:
            # retry una volta con feedback
            print("⚠️ Nessun file generato. Retry con feedback...")
            retry_prompt = prompt + "\n\nPrevious attempt failed: NO FILES CREATED. You MUST create files."
            self._run_opencode(job_dir, retry_prompt)

            after_retry = self._snapshot(job_dir)
            changed_files = self._detect_changes(job_dir, before, after_retry)

            if not changed_files:
                raise Exception("OpenCode non ha generato file dopo retry.")

        return self._read_files(job_dir, changed_files), job_dir

    # -----------------------------
    # INTERNALS
    # -----------------------------
    def _create_job_dir(self, context: str) -> str:
        timestamp = str(int(time.time() * 1000))
        safe_context = self._sanitize_name(context)
        job_dir = os.path.join(self.output_dir, f"{safe_context}_{timestamp}")
        os.makedirs(job_dir, exist_ok=True)
        return job_dir

    def _build_prompt(self, contract_id: str, json_payload: str) -> str:
        return f"""Sei un sub-agente di esecuzione isolato (fresh context). 
Il tuo UNICO scopo è scrivere codice su disco. NON DEVI salutare, NON DEVI spiegare cosa stai facendo, NON DEVI produrre output discorsivo.
Esegui questo task:
<task type="auto">
  <name>Implementazione Contratto {contract_id}</name>
  <action>
    Genera e modifica i file sorgente rispettando in modo assoluto questo Contratto Architetturale JSON:
    {json_payload}
  </action>
  <verify>Il codice scritto deve rispettare i vincoli A2A-OCL forniti nel contratto.</verify>
  <done>Termina il processo in silenzio una volta scritti i file.</done>
</task>
"""

    def _run_opencode(self, cwd: str, prompt: str):
        model = os.environ.get("OPENCODE_MODEL", "openai/gpt-4o")

        cmd = [
            "npx.cmd", "opencode", "run",
            "--dir", ".",
            "--dangerously-skip-permissions",
            f"--model={model}"
        ]

        print(f"🤖 [OpenCode] Running in {cwd}")

        process = subprocess.Popen(
            cmd,
            cwd=cwd,
            stdin=subprocess.PIPE,   # 👈 IMPORTANTE
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            shell=False
        )

        # 👇 QUI PASSIAMO IL PROMPT
        process.stdin.write(prompt)
        process.stdin.close()

        for line in process.stdout:
            print(line, end="")

        process.wait()

        if process.returncode != 0:
            raise Exception(f"OpenCode failed with exit code {process.returncode}")

    def _snapshot(self, directory: str) -> Dict[str, float]:
        snapshot = {}
        for root, _, files in os.walk(directory):
            for f in files:
                path = os.path.join(root, f)
                rel = os.path.relpath(path, directory)
                snapshot[rel] = os.path.getmtime(path)
        return snapshot

    def _detect_changes(self, directory: str, before: Dict, after: Dict) -> List[str]:
        changed = []

        for f, mtime in after.items():
            if f not in before:
                changed.append(f)
            elif before[f] != mtime:
                changed.append(f)

        return changed

    def _read_files(self, directory: str, files: List[str]) -> List[Dict]:
        result = []

        for f in files:
            full_path = os.path.join(directory, f)

            try:
                with open(full_path, "r", encoding="utf-8") as fp:
                    content = fp.read()

                if content.strip():
                    result.append({
                        "path": f,
                        "content": content
                    })
            except Exception as e:
                print(f"⚠️ Errore lettura file {f}: {e}")

        return result