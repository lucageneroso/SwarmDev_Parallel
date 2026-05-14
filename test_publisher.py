import json
import pika
import uuid
import os

def publish_test_contract():
    host = os.environ.get('RABBITMQ_HOST', 'localhost')
    port = int(os.environ.get('RABBITMQ_PORT', 5672))
    queue_name = 'contract_queue'
    
    contract_id = str(uuid.uuid4())
    
    # Esempio di Contratto JSON
    test_contract = {
        "id": contract_id,
        "context": "Backend_FastAPI",
        "description": (
            "Genera una singola API GET /status in FastAPI.\n"
            "Il codice DEVE avere errori di sintassi intenzionali o spazi sbagliati "
            "per testare se 'black' e 'flake8' intervengono e generano il Self-Refine Loop."
        ),
        "a2a_ocl_constraints": []
    }
    
    try:
        connection = pika.BlockingConnection(pika.ConnectionParameters(host=host, port=port))
        channel = connection.channel()
        channel.queue_declare(queue=queue_name, durable=True)
        
        channel.basic_publish(
            exchange='',
            routing_key=queue_name,
            body=json.dumps(test_contract),
            properties=pika.BasicProperties(
                delivery_mode=pika.DeliveryMode.Persistent
            )
        )
        print(f"✅ [Test] Contratto fittizio inviato su '{queue_name}': {contract_id}")
        connection.close()
    except Exception as e:
        print(f"❌ Errore durante l'invio del contratto: {e}")

if __name__ == '__main__':
    publish_test_contract()
