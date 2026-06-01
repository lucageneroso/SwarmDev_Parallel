import os
import warnings
from dotenv import load_dotenv
from langchain_core.messages import HumanMessage

# Ignoriamo i warning noiosi di LiteLLM
warnings.filterwarnings("ignore", message=".*ChatLiteLLM.*")
from langchain_community.chat_models import ChatLiteLLM

def test_swarmdev_llm():
    # 1. Carica le variabili dal file .env
    load_dotenv()
    
    # 2. Legge il modello esattamente come fa il tuo orchestratore
    model_name = os.getenv("LLM_MODEL", "gpt-4o")
    print(f"🔄 Inizializzazione di ChatLiteLLM con il modello: {model_name}")
    
    try:
        # 3. Istanzia l'LLM
        llm = ChatLiteLLM(
            model=model_name,
            max_retries=2,
            temperature=0.1
        )
        
        print("🚀 Invio di un messaggio di test tramite LangChain/LiteLLM...")
        # Usiamo HumanMessage, che è il formato nativo che si aspetta LangGraph
        messaggio = [HumanMessage(content="Ciao! Rispondi solo con questa frase esatta: 'Test OpenRouter superato con successo'.")]
        
        # 4. Invocazione (il momento della verità)
        risposta = llm.invoke(messaggio)
        
        print(f"\n✅ RISPOSTA DAL PROVIDER:\n{risposta.content}")
        print("\n🎉 IL TUO SETUP E' PERFETTO! L'orchestratore funzionerà senza problemi.")
        
    except Exception as e:
        print(f"\n❌ ERRORE: La chiamata ha fallito. Dettagli dell'errore:\n{e}")
        print("\nSuggerimento: Controlla che OPENROUTER_API_KEY sia corretta e di avere credito (se usi un modello a pagamento).")

if __name__ == "__main__":
    test_swarmdev_llm()
