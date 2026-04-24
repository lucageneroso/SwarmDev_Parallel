import os
from openai import OpenAI

# Inserisci la tua NUOVA chiave OpenAI qui
os.environ["OPENAI_API_KEY"] = "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"

print("📡 Contattando i server di OpenAI per gli embeddings...")

try:
    client = OpenAI()
    response = client.embeddings.create(
        model="text-embedding-3-small",
        input="Questo è un test per sbloccare la tesi."
    )
    print("✅ SUCCESSO! OpenAI ha risposto. Dimensione vettore:", len(response.data[0].embedding))
except Exception as e:
    print(f"❌ ERRORE OPENAI: {type(e).__name__} - {e}")