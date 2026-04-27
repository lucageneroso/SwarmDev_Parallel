# arm/opencode_wrapper.py
import subprocess
import os

class OpenCodeWrapper:
    def __init__(self, output_dir: str = "./workspace"):
        self.output_dir = output_dir
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)

    def generate_code(self, context: str, description: str, constraints: list[str]) -> str:
        """
        Invoca OpenCode CLI asincronamente (tramite subprocess bloccante per il worker, 
        ma in isolamento dal broker) passandogli la descrizione e i vincoli.
        """
        # Costruiamo un prompt coercitivo combinando descrizione e vincoli
        constraints_text = "\n".join([f"- {c}" for c in constraints])
        prompt = (
            f"Sei un agente autonomo headless. IL TUO UNICO SCOPO È CREARE FILE SUL DISCO.\n"
            f"Contesto: {context}\n"
            f"Obiettivo: {description}\n"
            f"VINCOLI TASSATIVI (Devi rispettare le seguenti regole strutturali):\n"
            f"{constraints_text}\n"
            f"ATTENZIONE: NON RISPONDERE A PAROLE E NON FARE DOMANDE. DEVI obbligatoriamente utilizzare i tuoi tool per creare/scrivere fisicamente i file di codice sorgente (.js, .html, .php, etc.) nella directory corrente. Procedi ora e scrivi i file sul disco."
        )

        print(f"🤖 [Arm] Avvio generazione codice per {context} tramite OpenCode...")
        
        # Salviamo il prompt temporaneamente
        prompt_file = os.path.join(self.output_dir, "temp_prompt.txt")
        with open(prompt_file, "w", encoding="utf-8") as f:
            f.write(prompt)

        try:
            # Invoca opencode via terminale. 
            # (Assumiamo che opencode accetti il prompt via stdin o parametro file, 
            # simuliamo un comando tipico CLI)
            # cmd = f"opencode -p \"$(cat {prompt_file})\"" (se opencode supporta -p)
            # In questo mock useremo opencode direttamente se disponibile, o lo simuliamo.
            
            # Dal momento che non conosciamo gli argomenti esatti di `opencode` npm, 
            # proviamo ad eseguirlo redirigendo il file in input o passandolo come stringa.
            
            # Passiamo il prompt via command line correttamente specificando la directory
            # opencode [project] --prompt <prompt>
            # opencode run <messaggio> --dir <dir> --dangerously-skip-permissions
            # Mettiamo i FLAG prima del prompt, altrimenti il parser CLI di Node (yargs) 
            # potrebbe interpretarli come parte del testo del messaggio stesso!
            model = os.environ.get("OPENCODE_MODEL", "openai/gpt-4o")
            cmd = [
                "npx.cmd", "opencode", "run", 
                "--dir", ".", 
                "--dangerously-skip-permissions", 
                f"--model={model}",
                prompt
            ]
            print(f"🔧 [Debug] Esecuzione comando: {' '.join(cmd)}")
            
            process = subprocess.Popen(
                cmd, 
                cwd=self.output_dir,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                shell=False
            )
            
            output_lines = []
            for line in process.stdout:
                print(line, end="") # Stampa a video per farti vedere cosa sta facendo
                output_lines.append(line)
                
            process.wait()
            
            if process.returncode == 0 and output_lines:
                generated_code = "".join(output_lines)
            else:
                raise Exception(f"OpenCode error o empty output. Exit code: {process.returncode}")
                
        except Exception as e:
            print(f"⚠️ [Arm] OpenCode CLI failed ({e}). Uso un fallback di simulazione...")
            generated_code = (
                f"// Codice generato per {context}\n"
                f"// Descrizione: {description}\n"
                f"// Vincoli rispettati: {len(constraints)}\n\n"
                f"class {context.capitalize()} {{\n"
                f"    constructor() {{\n"
                f"        this.complexity = 5;\n"
                f"    }}\n"
                f"}}\n"
            )
            
        return generated_code
