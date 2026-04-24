# orchestrator/validator_tool.py
import os
from lark import Lark
from lark.exceptions import LarkError

class A2AOCLValidator:
    def __init__(self, grammar_path="../core/grammar/a2a_ocl.lark"):
        """Inizializza il parser leggendo la grammatica EBNF dal file."""
        if not os.path.exists(grammar_path):
            raise FileNotFoundError(f"Il file di grammatica non è stato trovato in: {grammar_path}")

        with open(grammar_path, 'r') as file:
            grammar = file.read()

        # Inizializziamo il parser Lark con l'algoritmo LALR (deterministico e velocissimo)
        self.parser = Lark(grammar, start='constraint', parser='lalr')
        print("✅ Parser A2A-OCL inizializzato con successo.")

    def validate_expression(self, expression: str) -> dict:
        """
        Il cuore del Micro-Loop: riceve la stringa generata da Parlant e tenta
        di costruire l'Abstract Syntax Tree (AST).
        """
        try:
            # Tenta la validazione sintattica
            tree = self.parser.parse(expression)
            return {
                "status": "success",
                "is_valid": True,
                "message": "Validazione Superata: La sintassi A2A-OCL è conforme al contratto.",
                "error_delta": None
            }

        except LarkError as e:
            # Se Parlant compie un'allucinazione sintattica, intercettiamo l'errore
            # Estraiamo solo la riga principale dell'errore per dare un feedback chirurgico all'LLM
            error_msg = str(e).split('\n')[0]

            return {
                "status": "error",
                "is_valid": False,
                "message": "Quality Gate Fallito: Correggi la sintassi secondo la grammatica A2A-OCL.",
                "error_delta": f"Eccezione di Parsing: {error_msg}"
            }

# ==========================================
# ESECUZIONE DEI TEST LOCALI (DRY RUN)
# ==========================================
if __name__ == "__main__":
    # Assicurati che i path siano corretti rispetto a dove lanci lo script
    validator = A2AOCLValidator(grammar_path="../core/grammar/a2a_ocl.lark")

    print("\n--- TEST 1: Vincolo McCall (Corretto) ---")
    expr_ok = "context Code inv: self.cyclomatic_complexity <= 10"
    print(f"Input LLM: {expr_ok}")
    print("Risultato:", validator.validate_expression(expr_ok))

    print("\n--- TEST 2: Vincolo ARQ con Iteratore (Corretto) ---")
    expr_arq = "context Frontend inv: self.calls->forAll(c | API.endpoints->contains(c.endpoint))"
    print(f"Input LLM: {expr_arq}")
    print("Risultato:", validator.validate_expression(expr_arq))

    print("\n--- TEST 3: Allucinazione Sintattica (LLM inventa 'foreach') ---")
    # Qui simuliamo l'errore classico di un LLM che applica logica C# o PHP invece del nostro OCL
    expr_bad = "context Backend inv: self.models->foreach(m | m.is_valid = true)"
    print(f"Input LLM: {expr_bad}")
    print("Risultato:", validator.validate_expression(expr_bad))