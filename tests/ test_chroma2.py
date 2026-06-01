import os
import sys
# Aggiunge il path per i dotenv
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from dotenv import load_dotenv
load_dotenv()

import litellm
try:
    res = litellm.embedding(
        model="text-embedding-ada-002",
        input=["test text"]
    )
    print("Embedding dim:", len(res.data[0]['embedding']))
except Exception as e:
    print("LiteLLM Embedding Error:", e)
