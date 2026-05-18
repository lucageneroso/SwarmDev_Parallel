import pika
import json

# 1. Definiamo il Contratto JSON (Semplice ma che attiva sia Frontend che Backend)
test_contract = {
    "task_id": "demo_001",
    "description": "Create a simple backend API with a '/ping' route that returns 'pong', and a frontend function that calls this API.",
    "technical_constraints": [
        "Backend must use FastAPI.",
        "Frontend must use JavaScript fetch API."
    ]
}

# 2. Connessione a RabbitMQ
connection = pika.BlockingConnection(pika.ConnectionParameters('localhost'))
channel = connection.channel()

# Assicuriamoci che la coda esista
channel.queue_declare(queue='contract_queue', durable=True)

# 3. Invio del messaggio
channel.basic_publish(
    exchange='',
    routing_key='contract_queue',
    body=json.dumps(test_contract),
    properties=pika.BasicProperties(
        delivery_mode=pika.DeliveryMode.Persistent
    )
)

print(f" [x] Inviato Contratto JSON a SwarmDev: {test_contract['task_id']}")
connection.close()