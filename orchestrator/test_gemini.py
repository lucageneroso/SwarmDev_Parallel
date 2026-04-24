import os
from google import genai
from google.genai import errors

# Inserisci la tua chiave qui
os.environ["GEMINI_API_KEY"] = "AIzaSyDVOWDFnLA8tKiv2s071wAe97BKjbF3r-c"

print("📡 Contattando i server di Google Gemini...")

try:
    client = genai.Client()
    # Chiediamo a Google esattamente quello che gli chiede Parlant: un embedding
    response = client.models.embed_content(
        model='text-embedding-004',
        contents='Questo è un test di connessione.'
    )
    print("✅ SUCCESSO! Google ha risposto. Dimensioni vettore:", len(response.embeddings[0].values))
except errors.APIError as e:
    print(f"❌ ERRORE API GOOGLE: {e}")
except Exception as e:
    print(f"❌ ALTRO ERRORE: {e}")