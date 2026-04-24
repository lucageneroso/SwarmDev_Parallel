import os
import sys
from dotenv import load_dotenv

# Load .env file
load_dotenv()

api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    print("ERRORE: OPENAI_API_KEY non trovata nel file .env")
    sys.exit(1)

try:
    from openai import OpenAI
except ImportError:
    print("ERRORE: Modulo 'openai' non installato.")
    sys.exit(1)

client = OpenAI(api_key=api_key)

print("Tentativo di connessione a OpenAI per generare un embedding di test...")
try:
    response = client.embeddings.create(
        input="Questo è un test",
        model="text-embedding-3-small"
    )
    print("✅ Connessione riuscita! Embeddings generati correttamente.")
    print("Lunghezza vettore:", len(response.data[0].embedding))
except Exception as e:
    print(f"❌ ERRORE RESTITUITO DA OPENAI:\n{e}")
