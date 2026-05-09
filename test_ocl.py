import os
import sys

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(CURRENT_DIR)
if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)

from quality_gate.ocl_evaluator import A2AOCLValidator

GRAMMAR_PATH = os.path.join(PROJECT_ROOT, "core", "grammar", "a2a_ocl.lark")
validator = A2AOCLValidator(grammar_path=GRAMMAR_PATH)

expr1 = "context Prenotazione inv: self.numero_persone <= self.tavolo.numero_posti"
expr2 = "context Prenotazione inv: self.tavolo.prenotazioni->forAll(p | p.data_ora != self.data_ora or p.id = self.id)"

print(validator.validate_expression(expr1))
print(validator.validate_expression(expr2))
