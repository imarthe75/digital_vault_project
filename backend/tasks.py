# backend/tasks.py
import os
from celery import Celery
import boto3
import psycopg2
import json
from cryptography.fernet import Fernet
import time
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- Configuración de Celery ---
CELERY_BROKER_URL = os.getenv('CELERY_BROKER_URL', 'redis://localhost:6379/0')
CELERY_RESULT_BACKEND = os.getenv('CELERY_RESULT_BACKEND', 'redis://localhost:6379/0')

celery_app = Celery('tasks', broker=CELERY_BROKER_URL, backend=CELERY_RESULT_BACKEND)

# --- Configuración para tareas (variables de entorno) ---
CEPH_ENDPOINT_URL = os.getenv('CEPH_ENDPOINT_URL')
CEPH_ACCESS_KEY = os.getenv('CEPH_ACCESS_KEY')
CEPH_SECRET_KEY = os.getenv('CEPH_SECRET_KEY')
CEPH_BUCKET_NAME = os.getenv('CEPH_BUCKET_NAME')
POSTGRES_DB = os.getenv('POSTGRES_DB')
POSTGRES_USER = os.getenv('POSTGRES_USER')
POSTGRES_PASSWORD = os.getenv('POSTGRES_PASSWORD')
POSTGRES_HOST = os.getenv('POSTGRES_HOST')
POSTGRES_PORT = os.getenv('POSTGRES_PORT', '5432')
SYSTEM_MASTER_KEY = os.getenv('SYSTEM_MASTER_KEY')

s3_client = None
master_fernet_worker = None

def get_s3_client():
    global s3_client
    if s3_client is None:
        s3_client = boto3.client(
            's3',
            endpoint_url=CEPH_ENDPOINT_URL,
            aws_access_key_id=CEPH_ACCESS_KEY,
            aws_secret_access_key=CEPH_SECRET_KEY,
            config=boto3.session.Config(signature_version='s3v4')
        )
    return s3_client

def get_master_fernet():
    global master_fernet_worker
    if master_fernet_worker is None:
        if not SYSTEM_MASTER_KEY:
            raise ValueError("SYSTEM_MASTER_KEY no configurada para el worker.")
        master_fernet_worker = Fernet(SYSTEM_MASTER_KEY.encode())
    return master_fernet_worker

def decrypt_data(encrypted_data_bytes, encrypted_file_key):
    # Asegurarse de que encrypted_file_key sea bytes
    if isinstance(encrypted_file_key, memoryview):
        encrypted_file_key = bytes(encrypted_file_key)
    elif not isinstance(encrypted_file_key, bytes):
        # Esta línea puede ser la causa del problema si se intentaba decodificar la clave
        raise TypeError(f"encrypted_file_key debe ser bytes o memoryview, no {type(encrypted_file_key)}")

    file_key = get_master_fernet().decrypt(encrypted_file_key)
    file_fernet = Fernet(file_key)
    decrypted_data = file_fernet.decrypt(encrypted_data_bytes)
    return decrypted_data

def get_db_connection():
    try:
        conn = psycopg2.connect(
            dbname=POSTGRES_DB,
            user=POSTGRES_USER,
            password=POSTGRES_PASSWORD,
            host=POSTGRES_HOST,
            port=POSTGRES_PORT
        )
        return conn
    except psycopg2.Error as e:
        logging.error(f"Error al conectar a la base de datos desde Celery worker: {e}")
        raise

@celery_app.task(bind=True, max_retries=3, default_retry_delay=60)
# La tarea ahora solo recibe file_id_str y ceph_path
def process_uploaded_file(self, file_id_str, ceph_path): # ¡CAMBIO AQUÍ!
    """
    Tarea Celery para procesar un archivo subido de forma asíncrona.
    Aquí se realizarían tareas como escaneo de virus, generación de miniaturas, etc.
    """
    logging.info(f"Tarea Celery: Iniciando procesamiento para file_id: {file_id_str}")
    conn = None # Inicializa conn a None
    try:
        # Recuperar la clave de encriptación de la base de datos dentro del worker
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT encryption_key_encrypted FROM files WHERE id = %s", (file_id_str,))
        result = cur.fetchone()
        cur.close() # Cierra el cursor tan pronto como no se necesite

        if not result:
            logging.error(f"Tarea Celery: No se encontró clave de encriptación para file_id: {file_id_str}")
            return # Salir si no hay clave

        # La clave encriptada de la DB ya viene como un objeto de tipo 'memoryview' o 'bytes'
        # psycopg2 devuelve 'memoryview' para BYTEA, que es compatible con 'bytes'
        encrypted_file_key_from_db = bytes(result[0])

        s3 = get_s3_client()
        response = s3.get_object(Bucket=CEPH_BUCKET_NAME, Key=ceph_path)
        encrypted_content = response['Body'].read() # Esto es bytes

        # Asegúrate de que decrypted_content siga siendo bytes si no es un archivo de texto
        decrypted_content = decrypt_data(encrypted_content, encrypted_file_key_from_db)

        logging.info(f"Tarea Celery: Archivo {file_id_str} descargado y desencriptado. Tamaño: {len(decrypted_content)} bytes.")

        # --- SIMULACIÓN DE PROCESAMIENTO REAL ---
        # Si fueras a procesar el contenido aquí, asegúrate de que el contenido es binario.
        # Por ejemplo, para escanear virus:
        logging.info(f"Tarea Celery: Simulando escaneo de virus para {file_id_str}...")
        time.sleep(2) # Simula un proceso que lleva tiempo
        virus_found = False # Lógica real aquí

        # Actualizar estado en la base de datos (ej. "processed", "virus_scanned")
        cur = conn.cursor() # Usa la misma conexión si no la has cerrado
        cur.execute(
            "UPDATE files SET processed_status = %s, last_processed_at = NOW() WHERE id = %s",
            ('virus_scanned' if not virus_found else 'infected', file_id_str)
        )
        conn.commit()
        cur.close()
        logging.info(f"Tarea Celery: Estado de procesamiento para {file_id_str} actualizado a 'virus_scanned'.")

        # Aquí podrías añadir más lógica: generar miniaturas, indexar, etc.

    except Exception as e:
        logging.error(f"Tarea Celery: Error al procesar archivo {file_id_str}: {e}", exc_info=True)
        # Manejo de reintentos
        try:
            self.retry(exc=e)
        except self.MaxRetriesExceededError:
            logging.error(f"Tarea Celery: Se excedieron los reintentos para file_id {file_id_str}. No se pudo procesar.")
            # Actualizar DB con estado de fallo crítico si no se pudo reintentar más
            try:
                if conn: # Asegurarse de que la conexión existe antes de intentar usarla
                    cur = conn.cursor()
                    cur.execute(
                        "UPDATE files SET processed_status = %s, last_processed_at = NOW() WHERE id = %s",
                        ('failed_processing', file_id_str)
                    )
                    conn.commit()
                    cur.close()
            except Exception as db_e:
                logging.error(f"Tarea Celery: Error al actualizar estado de fallo en DB para {file_id_str}: {db_e}")
    finally:
        if conn:
            conn.close() # Asegurarse de cerrar la conexión a la DB