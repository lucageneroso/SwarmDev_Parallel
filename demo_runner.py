import pika
import json
import sys

def send_contract(contract_dict, queue_name='contract_queue'):
    try:
        connection = pika.BlockingConnection(pika.ConnectionParameters('localhost'))
        channel = connection.channel()
        channel.queue_declare(queue=queue_name, durable=True)
        
        channel.basic_publish(
            exchange='',
            routing_key=queue_name,
            body=json.dumps(contract_dict),
            properties=pika.BasicProperties(delivery_mode=pika.DeliveryMode.Persistent)
        )
        print(f"\n🚀 [SUCCESSO] Contratto '{contract_dict['task_id']}' inviato a SwarmDev!")
        connection.close()
    except Exception as e:
        print(f"\n❌ [ERRORE] Impossibile connettersi a RabbitMQ: {e}")

# ==========================================
# CONTRATTO 1: IL PERCORSO VELOCE
# ==========================================
contract_1 = {
    "task_id": "DEMO_01_HAPPY_PATH",
    "description": "Create a microservice architecture for a simple Calculator.",
    "frontend_requirements": "Write a clean JavaScript module with a function `calculate(a, b, operation)` that uses `fetch` to call the backend. Handle errors gracefully.",
    "backend_requirements": "Write a Python FastAPI application with a single POST endpoint `/calculate` that accepts two numbers and an operation (add, subtract). Return the result as JSON."
}

# ==========================================
# CONTRATTO 2: IL TEST DI RESILIENZA (Self-Refine)
# ==========================================
# Chiediamo un algoritmo volutamente verboso o complesso per cercare di innescare 
# i linter (ESLint per variabili non usate o Radon per complessità ciclomatica).
contract_2 = {
    "task_id": "DEMO_02_SELF_REFINE",
    "description": "Implement an Advanced Data Sorter and Analyzer.",
    "frontend_requirements": "Write a Node.js script that declares a complex nested JSON object of users. Create a function that sorts them by age, but purposely declare an unused variable named 'temp_buffer_unused' to see if the linter catches it.",
    "backend_requirements": "Write a Python FastAPI app with an endpoint `/analyze`. The function must contain a highly nested loop (at least 4 levels deep) to analyze a string character by character. This is intended to test cyclomatic complexity strictness."
}

def main():
    print("=============================================")
    print("🤖 SWARMDEV LAB DEMO - MISSION CONTROL 🤖")
    print("=============================================\n")
    print("Scegli quale contratto inviare a RabbitMQ:")
    print("1. [Happy Path] - Calcolatrice Base (Dimostra parallelismo e CodeWiki)")
    print("2. [Self-Refine] - Analizzatore Complesso (Dimostra i Quality Gates e il loop di correzione)")
    print("3. Esci")
    
    choice = input("\nScelta (1/2/3): ")
    
    if choice == '1':
        send_contract(contract_1)
    elif choice == '2':
        send_contract(contract_2)
    elif choice == '3':
        print("Uscita in corso...")
        sys.exit(0)
    else:
        print("Scelta non valida.")

if __name__ == "__main__":
    main()