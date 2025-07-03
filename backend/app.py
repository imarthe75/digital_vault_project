# backend/app.py
import traceback
import os
from flask import Flask, request, jsonify, send_file
from cryptography.fernet import Fernet
import boto3
import psycopg2
import json
import uuid
import io
from dotenv import load_dotenv
from flask_cors import CORS
from datetime import datetime
import socket # Para el client.id del productor Kafka

# Importaciones condicionales para Kafka y Celery
# Esto permite que la app funcione si estas librerías no están instaladas
# o si la funcionalidad está deshabilitada por variables de entorno.
Producer = None
try:
    from confluent_kafka import Producer, KafkaException, KafkaError
except ImportError:
    print("WARNING: 'confluent-kafka' no instalada o disponible. La integración con Kafka estará deshabilitada.")
except Exception as e:
    print(f"WARNING: Error al importar confluent-kafka: {e}. La integración con Kafka estará deshabilitada.")

Celery = None
process_uploaded_file_task = None
try:
    from celery import Celery
    from tasks import process_uploaded_file as process_uploaded_file_task # Importa la tarea de Celery
except ImportError:
    print("WARNING: 'celery' no instalada o disponible. Las tareas asíncronas estarán deshabilitadas.")
except Exception as e:
    print(f"WARNING: Error al importar Celery/tareas: {e}. Las tareas asíncronas estarán deshabilitadas.")

load_dotenv()

app = Flask(__name__)
CORS(app)

# --- Configuración (desde variables de entorno) ---
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
if not SYSTEM_MASTER_KEY:
    raise ValueError("SYSTEM_MASTER_KEY no está configurada en .env. ¡Es crítica para la seguridad!")
master_fernet = Fernet(SYSTEM_MASTER_KEY.encode())

# --- Configuración de Kafka ---
ENABLE_KAFKA = os.getenv('ENABLE_KAFKA', 'True').lower() == 'true'
KAFKA_BOOTSTRAP_SERVERS = os.getenv('KAFKA_BOOTSTRAP_SERVERS', 'localhost:9092')
KAFKA_TOPIC_FILE_UPLOADED = os.getenv('KAFKA_TOPIC_FILE_UPLOADED', 'file_uploaded')

kafka_producer = None
if ENABLE_KAFKA and Producer:
    try:
        producer_conf = {
            'bootstrap.servers': KAFKA_BOOTSTRAP_SERVERS,
            'client.id': socket.gethostname()
        }
        kafka_producer = Producer(producer_conf)
        print("INFO: Productor de Kafka inicializado.")
    except Exception as e:
        print(f"WARNING: No se pudo inicializar el productor de Kafka: {e}. La funcionalidad de Kafka estará deshabilitada.")
        kafka_producer = None # Asegurarse de que sea None si falla

# --- Configuración de Celery ---
ENABLE_CELERY = os.getenv('ENABLE_CELERY', 'True').lower() == 'true'
CELERY_BROKER_URL = os.getenv('CELERY_BROKER_URL', 'redis://localhost:6379/0')
CELERY_RESULT_BACKEND = os.getenv('CELERY_RESULT_BACKEND', 'redis://localhost:6379/0')

celery_app = None
if ENABLE_CELERY and Celery:
    try:
        celery_app = Celery('tasks', broker=CELERY_BROKER_URL, backend=CELERY_RESULT_BACKEND)
        print("INFO: Celery aplicación inicializada.")
    except Exception as e:
        print(f"WARNING: No se pudo inicializar la aplicación Celery: {e}. Las tareas asíncronas estarán deshabilitadas.")
        celery_app = None

# --- Clientes ---
s3_client = boto3.client(
    's3',
    endpoint_url=CEPH_ENDPOINT_URL,
    aws_access_key_id=CEPH_ACCESS_KEY,
    aws_secret_access_key=CEPH_SECRET_KEY,
    config=boto3.session.Config(signature_version='s3v4')
)

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
        print(f"ERROR: No se pudo conectar a la base de datos PostgreSQL: {e}")
        raise

# --- Funciones Auxiliares de Encriptación ---
def encrypt_data(data_bytes):
    file_key = Fernet.generate_key()
    file_fernet = Fernet(file_key)
    encrypted_data = file_fernet.encrypt(data_bytes)
    encrypted_file_key = master_fernet.encrypt(file_key)
    return encrypted_data, encrypted_file_key

def decrypt_data(encrypted_data_bytes, encrypted_file_key):
    if isinstance(encrypted_file_key, memoryview):
        encrypted_file_key = bytes(encrypted_file_key)
    elif not isinstance(encrypted_file_key, bytes):
        raise TypeError(f"encrypted_file_key debe ser bytes o memoryview, no {type(encrypted_file_key)}")

    file_key = master_fernet.decrypt(encrypted_file_key)
    file_fernet = Fernet(file_key)
    decrypted_data = file_fernet.decrypt(encrypted_data_bytes)
    return decrypted_data

# --- Callback para la entrega de mensajes de Kafka ---
def delivery_report(err, msg):
    if err is not None:
        print(f"ERROR: Fallo al enviar mensaje a Kafka: {err}")
    else:
        print(f"INFO: Mensaje enviado a Kafka -> Topic: '{msg.topic()}', Partición: [{msg.partition()}], Offset: {msg.offset()}")

# --- Rutas de la API ---

@app.route('/vault/upload', methods=['POST'])
def upload_file():
    user_id = request.form.get('user_id', 'default_user')
    if not user_id:
        return jsonify({"error": "User ID is required"}), 400

    if 'file' not in request.files:
        return jsonify({"error": "No file part"}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400

    original_filename = file.filename
    file_bytes = file.read()
    mimetype = file.mimetype or 'application/octet-stream'
    size_bytes = len(file_bytes)

    metadata_json = request.form.get('metadata')
    metadata = {}
    if metadata_json:
        try:
            metadata = json.loads(metadata_json)
        except json.JSONDecodeError:
            return jsonify({"error": "Invalid metadata JSON"}), 400

    print(f"DEBUG: Tipo de file_bytes ANTES de encriptar: {type(file_bytes)}")
    # NO intentes imprimir file_bytes directamente si es grande, solo su tipo y longitud
    print(f"DEBUG: Longitud de file_bytes: {len(file_bytes)}")

    encrypted_file_content, encrypted_file_key = encrypt_data(file_bytes)

    # --- NUEVAS LÍNEAS DE DEBUGGING AQUÍ ---
    print(f"DEBUG: Tipo de encrypted_file_content: {type(encrypted_file_content)}")
    print(f"DEBUG: Longitud de encrypted_file_content: {len(encrypted_file_content)}")

    print(f"DEBUG: Tipo de encrypted_file_key: {type(encrypted_file_key)}")
    # Fernet keys son base64, pueden decodificarse a string sin problema para debugging
    print(f"DEBUG: encrypted_file_key (B64 decodificada para log): {encrypted_file_key.decode('utf-8')}")
    # Puedes incluso imprimir los primeros bytes del contenido encriptado si quieres, de forma segura
    print(f"DEBUG: encrypted_file_content (primeros 50 bytes): {encrypted_file_content[:50].hex()}")
    # --- FIN DE NUEVAS LÍNEAS DE DEBUGGING ---

    file_id = uuid.uuid4()
    ceph_object_key = f"{user_id}/{file_id}"

    conn = None
    try:
        # 1. Subir a MinIO/Ceph
        s3_client.put_object(
            Bucket=CEPH_BUCKET_NAME,
            Key=ceph_object_key,
            Body=encrypted_file_content,
            ContentType=mimetype
        )
        print(f"INFO: Archivo {original_filename} subido a MinIO/Ceph como {ceph_object_key}.")

        # 2. Guardar metadatos en PostgreSQL
        conn = get_db_connection()
        cur = conn.cursor()

        cur.execute(
            """
            INSERT INTO files (id, user_id, ceph_path, encryption_key_encrypted, original_filename, mimetype, size_bytes, metadata)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (str(file_id), str(user_id), ceph_object_key, encrypted_file_key, original_filename, mimetype, size_bytes, json.dumps(metadata))
        )
        conn.commit()
        cur.close()
        print(f"INFO: Metadatos del archivo {file_id} guardados en PostgreSQL.")

        # 3. Publicar evento en Kafka (si está habilitado y el productor está listo)
        if ENABLE_KAFKA and kafka_producer:
            event_data = {
                'file_id': str(file_id),
                'user_id': str(user_id),
                'original_filename': original_filename,
                'ceph_path': ceph_object_key,
                'mimetype': mimetype,
                'size_bytes': size_bytes,
                'timestamp': datetime.now().isoformat()
            }
            try:
                kafka_producer.produce(
                    KAFKA_TOPIC_FILE_UPLOADED,
                    key=str(file_id).encode('utf-8'),
                    value=json.dumps(event_data).encode('utf-8'),
                    callback=delivery_report
                )
                kafka_producer.flush(timeout=5) # Pequeño timeout para no bloquear
                print(f"INFO: Evento de subida para file_id {file_id} publicado en Kafka.")
            except KafkaException as kafka_err:
                print(f"ERROR: Fallo al enviar el evento a Kafka: {kafka_err}. La subida fue exitosa en almacenamiento y DB.")
                # Aquí podrías decidir si quieres registrar esto como un error grave o simplemente una advertencia.
                # Para una bóveda digital, la notificación de eventos puede ser crítica.
            except Exception as e:
                print(f"ERROR: Error inesperado al intentar publicar en Kafka: {e}. La subida fue exitosa en almacenamiento y DB.")
        else:
            print("INFO: La integración con Kafka está deshabilitada o no inicializada.")

        # 4. Disparar tarea Celery (si está habilitada)
        if ENABLE_CELERY and celery_app and process_uploaded_file_task:
            try:
                # ¡CONFIRMA QUE ESTA ES LA VERSIÓN QUE TIENES EN TU app.py!
                # La tarea Celery ahora solo recibe file_id y ceph_path.
                # La clave se recupera desde la DB dentro del worker.
                process_uploaded_file_task.delay(str(file_id), ceph_object_key) # NO SE PASA encrypted_file_key AQUÍ
                print(f"INFO: Tarea Celery para procesar file_id {file_id} disparada.")
            except Exception as celery_err:
                print(f"ERROR: Fallo al disparar tarea Celery para file_id {file_id}: {celery_err}")
        else:
            print("INFO: La integración con Celery está deshabilitada o no inicializada.")

        return jsonify({"message": "File uploaded successfully", "file_id": str(file_id)}), 201

    except psycopg2.Error as db_err:
        print(f"ERROR: Fallo en la operación de base de datos durante la subida: {db_err}")
        # Intentar limpiar el archivo de S3 si la DB falla
        try:
            s3_client.delete_object(Bucket=CEPH_BUCKET_NAME, Key=ceph_object_key)
            print(f"INFO: Se limpió {ceph_object_key} de S3 debido a un error de DB.")
        except Exception as s3_e:
            print(f"WARNING: Fallo al limpiar objeto S3 después de un error de DB: {s3_e}")
        return jsonify({"error": "Database operation failed during upload."}), 500
    except Exception as e:
        traceback.print_exc()
        print(f"ERROR: Error inesperado durante la subida del archivo: {e}")
        # Intentar limpiar el archivo de S3 si hubo algún otro error
        try:
            s3_client.delete_object(Bucket=CEPH_BUCKET_NAME, Key=ceph_object_key)
            print(f"INFO: Se limpió {ceph_object_key} de S3 debido a un error inesperado.")
        except Exception as s3_e:
            print(f"WARNING: Fallo al limpiar objeto S3 después de un error inesperado: {s3_e}")
        return jsonify({"error": str(e)}), 500
    finally:
        if conn:
            conn.close()

# --- Resto de tus rutas (get_file, get_file_metadata, delete_file, list_user_files) ---
# Se mantienen igual que antes, el foco del cambio es en upload_file.
# ... (tu código existente para estas rutas) ...

@app.route('/vault/<file_id>', methods=['GET'])
def get_file(file_id):
    user_id_requester = request.args.get('user_id', 'default_user')
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(
            "SELECT ceph_path, encryption_key_encrypted, original_filename, mimetype, user_id FROM files WHERE id = %s",
            (file_id,)
        )
        file_record = cur.fetchone()
        if not file_record:
            return jsonify({"error": "File not found"}), 404
        ceph_path, raw_encrypted_file_key, original_filename, mimetype, file_owner_user_id = file_record
        encrypted_file_key = bytes(raw_encrypted_file_key)
        if str(user_id_requester) != str(file_owner_user_id):
            return jsonify({"error": "Forbidden: You do not own this file"}), 403
        response = s3_client.get_object(Bucket=CEPH_BUCKET_NAME, Key=ceph_path)
        encrypted_file_content = response['Body'].read()
        decrypted_file_content = decrypt_data(encrypted_file_content, encrypted_file_key)
        return send_file(
            io.BytesIO(decrypted_file_content),
            mimetype=mimetype or 'application/octet-union',
            as_attachment=True,
            download_name=original_filename
        )
    except Exception as e:
        print(f"ERROR: Fallo al obtener archivo: {e}")
        return jsonify({"error": str(e)}), 500
    finally:
        if conn:
            conn.close()

@app.route('/vault/metadata/<file_id>', methods=['GET'])
def get_file_metadata(file_id):
    user_id_requester = request.args.get('user_id', 'default_user')
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT original_filename, mimetype, size_bytes, upload_timestamp, metadata, user_id FROM files WHERE id = %s", (file_id,))
        record = cur.fetchone()
        if not record:
            return jsonify({"error": "File metadata not found"}), 404
        original_filename, mimetype, size_bytes, upload_timestamp, metadata, file_owner_user_id = record
        if str(user_id_requester) != str(file_owner_user_id):
            return jsonify({"error": "Forbidden: You do not own this file's metadata"}), 403
        return jsonify({
            "file_id": file_id,
            "original_filename": original_filename,
            "mimetype": mimetype,
            "size_bytes": size_bytes,
            "upload_timestamp": upload_timestamp.isoformat(),
            "metadata": metadata,
            "user_id": str(file_owner_user_id)
        })
    except Exception as e:
        print(f"ERROR: Fallo al obtener metadatos: {e}")
        return jsonify({"error": str(e)}), 500
    finally:
        if conn:
            conn.close()

@app.route('/vault/<file_id>', methods=['DELETE'])
def delete_file(file_id):
    user_id_requester = request.args.get('user_id', 'default_user')
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT ceph_path, user_id FROM files WHERE id = %s", (file_id,))
        file_record = cur.fetchone()
        if not file_record:
            return jsonify({"error": "File not found"}), 404
        ceph_path, file_owner_user_id = file_record
        if str(user_id_requester) != str(file_owner_user_id):
            return jsonify({"error": "Forbidden: You do not own this file"}), 403
        cur.execute("DELETE FROM files WHERE id = %s", (file_id,))
        conn.commit()
        s3_client.delete_object(Bucket=CEPH_BUCKET_NAME, Key=ceph_path)
        print(f"INFO: Archivo {file_id} eliminado de PostgreSQL y S3.")

        # Opcional: Publicar un evento 'file_deleted' en Kafka aquí también
        # if ENABLE_KAFKA and kafka_producer:
        #     try:
        #         kafka_producer.produce('file_deleted', key=str(file_id).encode('utf-8'), value=json.dumps({'file_id': str(file_id), 'user_id': str(file_owner_user_id), 'timestamp': datetime.now().isoformat()}).encode('utf-8'))
        #         kafka_producer.flush(timeout=5)
        #         print(f"INFO: Evento de eliminación para file_id {file_id} publicado en Kafka.")
        #     except KafkaException as kafka_err:
        #         print(f"ERROR: Fallo al enviar el evento de eliminación a Kafka: {kafka_err}.")

        return jsonify({"message": "File deleted successfully"}), 200

    except Exception as e:
        print(f"ERROR: Fallo al eliminar archivo: {e}")
        return jsonify({"error": str(e)}), 500
    finally:
        if conn:
            conn.close()

@app.route('/vault/user/<user_id>', methods=['GET'])
def list_user_files(user_id):
    user_id_requester = request.args.get('requester_id', 'default_user')
    if str(user_id_requester) != str(user_id):
        return jsonify({"error": "Forbidden: Not authorized to view these files"}), 403
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(
            "SELECT id, original_filename, mimetype, size_bytes, upload_timestamp, metadata FROM files WHERE user_id = %s",
            (user_id,)
        )
        files = []
        for row in cur.fetchall():
            files.append({
                "file_id": str(row[0]),
                "original_filename": row[1],
                "mimetype": row[2],
                "size_bytes": row[3],
                "upload_timestamp": row[4].isoformat(),
                "metadata": row[5]
            })
        return jsonify(files)
    except Exception as e:
        print(f"ERROR: Fallo al listar archivos para el usuario {user_id}: {e}")
        return jsonify({"error": str(e)}), 500
    finally:
        if conn:
            conn.close()

if __name__ == '__main__':
    # Para producción, es altamente recomendado usar Gunicorn (en WSL/Linux) o Waitress (en Windows)
    # Por ejemplo: gunicorn --bind 0.0.0.0:5000 --workers 4 --threads 2 app:app
    # O para Waitress en Windows: from waitress import serve; serve(app, host='0.0.0.0', port=5000)
    print("INFO: Iniciando la aplicación Flask...")
    app.run(debug=True, host='0.0.0.0', port=5000)