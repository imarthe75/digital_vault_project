# backend/file_processor_service.py
import os
import json
from confluent_kafka import Consumer, KafkaException, KafkaError
import sys
import logging

# Configuración de logging para ver la salida
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- Configuración de Kafka Consumer ---
# Asegúrate de que KAFKA_BOOTSTRAP_SERVERS apunte a la IP de tu host
# si el consumidor (y tu backend) se ejecutan directamente en el host,
# y Kafka está en Docker (expuesto en localhost:9092).
KAFKA_BOOTSTRAP_SERVERS = 'localhost:9092'
KAFKA_TOPIC_FILE_UPLOADED = 'file_uploaded'
KAFKA_GROUP_ID = 'file_processing_group' # Un ID de grupo para este consumidor

consumer_conf = {
    # ¡CORRECCIÓN AQUÍ! Era KAFKA_BOOTSTRates_SERVERS
    'bootstrap.servers': KAFKA_BOOTSTRAP_SERVERS,
    'group.id': KAFKA_GROUP_ID,
    'auto.offset.reset': 'earliest', # Empieza a leer desde el principio si no hay offset guardado
    'enable.auto.commit': False # Control manual de commits
}

try:
    consumer = Consumer(consumer_conf)
    consumer.subscribe([KAFKA_TOPIC_FILE_UPLOADED])
    logging.info(f"Consumidor de Kafka suscrito al topic: {KAFKA_TOPIC_FILE_UPLOADED}")

except KafkaException as e:
    logging.error(f"Error al inicializar consumidor de Kafka: {e}")
    sys.exit(1)

def process_file_uploaded_event(event_data):
    """
    Función que simula el procesamiento de un evento de archivo subido.
    Aquí iría la lógica para:
    - Escanear virus
    - Generar miniaturas
    - Indexar contenido para búsqueda
    - Notificar a otros sistemas
    - Actualizar metadatos en la base de datos, etc.
    """
    logging.info(f"Procesando evento de archivo subido para ID: {event_data.get('file_id')}")
    logging.info(f"Nombre original: {event_data.get('original_filename')}")
    logging.info(f"Ruta en Ceph: {event_data.get('ceph_path')}")
    logging.info(f"¡Simulando procesamiento asíncrono aquí!")
    # Ejemplo: Aquí podrías llamar a una función que interactúe con el archivo en MinIO/Ceph
    # o que actualice un campo 'processed_status' en PostgreSQL.

def main_consumer_loop():
    try:
        while True:
            msg = consumer.poll(timeout=1.0) # Espera 1 segundo por un mensaje

            if msg is None:
                continue
            if msg.error():
                if msg.error().code() == KafkaError._PARTITION_EOF:
                    # Fin de la partición (normal al llegar al final de los mensajes disponibles)
                    logging.info(f"%% {msg.topic()} [{msg.partition()}] reached end at offset {msg.offset()} %%")
                elif msg.error():
                    raise KafkaException(msg.error())
            else:
                # Mensaje válido recibido
                logging.info(f"Mensaje recibido: Topic={msg.topic()}, Partition={msg.partition()}, Offset={msg.offset()}")
                try:
                    event_data = json.loads(msg.value().decode('utf-8'))
                    process_file_uploaded_event(event_data)
                    # Confirma manualmente que el mensaje ha sido procesado
                    consumer.commit(message=msg)
                except json.JSONDecodeError:
                    logging.error(f"Error al decodificar JSON del mensaje: {msg.value()}")
                except Exception as e:
                    logging.error(f"Error al procesar mensaje: {e}", exc_info=True)
                    # En un entorno de producción, aquí manejarías reintentos o mensajes a un topic de errores

    except KeyboardInterrupt:
        logging.info("Interrupción por teclado, cerrando consumidor.")
    finally:
        # Cierra el consumidor limpiamente
        consumer.close()
        logging.info("Consumidor de Kafka cerrado.")

if __name__ == '__main__':
    main_consumer_loop()