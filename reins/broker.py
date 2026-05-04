# reins/broker.py
import pika
import json
from typing import Callable, Any
import os

class RabbitMQBroker:
    def __init__(self, host='localhost', port=5672):
        # Allow override from env
        self.host = os.environ.get('RABBITMQ_HOST', host)
        self.port = int(os.environ.get('RABBITMQ_PORT', port))
        
        # Le 3 code principali del Paradigma della Carrozza
        self.QUEUES = {
            'contract_queue': 'Coda per i Contratti JSON da eseguire (Mind -> Arm)',
            'validation_queue': 'Coda per il Codice Generato da validare (Arm -> Quality Gate)',
            'refine_queue': 'Coda per i Delta Errore in caso di fallimento (Quality Gate -> Arm/Mind)',
            'release_queue': 'Coda per il Codice approvato (Quality Gate -> Release)'
        }
        self.connection = None
        self.channel = None

    def connect(self):
        try:
            self.connection = pika.BlockingConnection(
                pika.ConnectionParameters(host=self.host, port=self.port, heartbeat=0)
            )
            self.channel = self.connection.channel()
            
            # Dichiariamo tutte le code in modo che esistano a prescindere da chi parte prima
            for queue_name in self.QUEUES.keys():
                self.channel.queue_declare(queue=queue_name, durable=True)
                
            print(f"✅ Connesso a RabbitMQ su {self.host}:{self.port}")
        except Exception as e:
            print(f"❌ Errore connessione a RabbitMQ: {e}")
            raise

    def publish(self, queue_name: str, message: dict):
        if not self.channel or self.channel.is_closed:
            self.connect()
            
        try:
            self.channel.basic_publish(
                exchange='',
                routing_key=queue_name,
                body=json.dumps(message),
                properties=pika.BasicProperties(
                    delivery_mode=pika.DeliveryMode.Persistent
                )
            )
        except Exception as e:
            print(f"⚠️ [Broker] Errore di publish ({e}), forzo la riconnessione...")
            self.connect()
            self.channel.basic_publish(
                exchange='',
                routing_key=queue_name,
                body=json.dumps(message),
                properties=pika.BasicProperties(
                    delivery_mode=pika.DeliveryMode.Persistent
                )
            )
        print(f"📤 [Broker] Messaggio pubblicato su '{queue_name}'")

    def consume(self, queue_name: str, callback: Callable[[dict], None]):
        if not self.channel:
            self.connect()

        def internal_callback(ch, method, properties, body):
            try:
                data = json.loads(body)
                callback(data)
                ch.basic_ack(delivery_tag=method.delivery_tag)
            except Exception as e:
                print(f"❌ [Broker] Errore nel processing del messaggio su '{queue_name}': {e}")
                # Potremmo implementare NACK o DLX (Dead Letter Exchange) qui
                ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)

        # QoS per non sovraccaricare il worker: 1 messaggio alla volta
        self.channel.basic_qos(prefetch_count=1)
        self.channel.basic_consume(queue=queue_name, on_message_callback=internal_callback)
        
        print(f"🎧 [Broker] In ascolto su '{queue_name}'...")
        try:
            self.channel.start_consuming()
        except KeyboardInterrupt:
            self.channel.stop_consuming()
            
    def close(self):
        if self.connection and self.connection.is_open:
            self.connection.close()
