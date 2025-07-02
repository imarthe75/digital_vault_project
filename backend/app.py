# backend/app.py
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
from confluent_kafka import Producer # ¡NUEVA IMPORTACIÓN para Kafka!
import socket # Usado para el client.id del productor Kafka
from datetime import datetime # Para la marca de tiempo del evento Kafka

load_dotenv()

app = Flask(__name__)
CORS(app)

# --- Configuración (desde variables de entorno) ---
# Asegúrate de que CEPH_ENDPOINT_URL apunte a 'http://localhost:9000'
# si el backend se ejecuta directamente en tu máquina host.
CEPH_ENDPOINT_URL = os.getenv('CEPH_ENDPOINT_URL')
CEPH_ACCESS_KEY = os.getenv('CEPH_ACCESS_KEY')
CEPH_SECRET_KEY = os.getenv('CEPH_SECRET_KEY')
CEPH_BUCKET_NAME = os.getenv('CEPH_BUCKET_NAME')

POSTGRES_DB = os.getenv('POSTGRES_DB')
POSTGRES_USER = os.getenv('POSTGRES_USER')
POSTGRES_PASSWORD = os.getenv('POSTGRES_PASSWORD')
POSTGRES_HOST = os.getenv('POSTGRES_HOST')
# Asegúrate de que POSTGRES_PORT esté en tu .env si tu PostgreSQL local usa un puerto diferente
POSTGRES_PORT = os.getenv('POSTGRES_PORT', '5432') # Valor por defecto 5432

SYSTEM_MASTER_KEY = os.getenv('SYSTEM_MASTER_KEY')
if not SYSTEM_MASTER_KEY:
    raise ValueError("SYSTEM_MASTER_KEY no está configurada en .env. ¡Es crítica para la seguridad!")
master_fernet = Fernet(SYSTEM_MASTER_KEY.encode())

# --- Configuración de Kafka ---
# El backend se conecta a Kafka en el puerto 9092 del host.
KAFKA_BOOTSTRAP_SERVERS = os.getenv('KAFKA_BOOTSTRAP_SERVERS', 'localhost:9092')
KAFKA_TOPIC_FILE_UPLOADED = os.getenv('KAFKA_TOPIC_FILE_UPLOADED', 'file_uploaded')

# Configuración del productor de Kafka
producer_conf = {
    'bootstrap.servers': KAFKA_BOOTSTRAP_SERVERS,
    'client.id': socket.gethostname() # Identificador del cliente
}
kafka_producer = Producer(producer_conf)

# Callback para la entrega de mensajes de Kafka
def delivery_report(err, msg):
    """Callback llamado para indicar el resultado de la entrega del mensaje."""
    if err is not None:
        print(f"ERROR: Fallo al enviar mensaje a Kafka: {err}")
    else:
        print(f"INFO: Mensaje enviado a Kafka -> Topic: '{msg.topic()}', Partición: [{msg.partition()}], Offset: {msg.offset()}")

# --- Clientes ---
s3_client = boto3.client(
    's3',
    endpoint_url=CEPH_ENDPOINT_URL,
    aws_access_key_id=CEPH_ACCESS_KEY,
    aws_secret_access_key=CEPH_SECRET_KEY,
    config=boto3.session.Config(signature_version='s3v4') # Es buena práctica especificar la versión de firma
)

def get_db_connection():
    try:
        conn = psycopg2.connect(
            dbname=POSTGRES_DB,
            user=POSTGRES_USER,
            password=POSTGRES_PASSWORD,
            host=POSTGRES_HOST,
            port=POSTGRES_PORT # Usa el puerto configurable
        )
        return conn
    except psycopg2.Error as e:
        print(f"ERROR: No se pudo conectar a la base de datos PostgreSQL: {e}")
        raise # Vuelve a lanzar la excepción para que el llamador la maneje

# --- Funciones Auxiliares de Encriptación ---
def encrypt_data(data_bytes):
    file_key = Fernet.generate_key()
    file_fernet = Fernet(file_key)
    encrypted_data = file_fernet.encrypt(data_bytes)
    encrypted_file_key = master_fernet.encrypt(file_key)
    return encrypted_data, encrypted_file_key

def decrypt_data(encrypted_data_bytes, encrypted_file_key):
    # Asegúrate de que encrypted_file_key sea 'bytes'
    if isinstance(encrypted_file_key, memoryview):
        encrypted_file_key = bytes(encrypted_file_key)
    elif not isinstance(encrypted_file_key, bytes):
        raise TypeError(f"encrypted_file_key debe ser bytes o memoryview, no {type(encrypted_file_key)}")

    file_key = master_fernet.decrypt(encrypted_file_key)
    file_fernet = Fernet(file_key)
    decrypted_data = file_fernet.decrypt(encrypted_data_bytes)
    return decrypted_data

# --- Rutas de la API ---
# TODO: Implementar autenticación/autorización real. Por ahora, 'user_id' es un placeholder.
# En un sistema real, user_id se obtendría del token de sesión del usuario autenticado.

@app.route('/vault/upload', methods=['POST'])
def upload_file():
    user_id = request.form.get('user_id', 'default_user') # Default para pruebas rápidas
    if not user_id:
        return jsonify({"error": "User ID is required"}), 400

    if 'file' not in request.files:
        return jsonify({"error": "No file part"}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400

    original_filename = file.filename
    file_bytes = file.read()
    mimetype = file.mimetype or 'application/octet-stream' # Default mimetype
    size_bytes = len(file_bytes)

    metadata_json = request.form.get('metadata')
    metadata = {}
    if metadata_json:
        try:
            metadata = json.loads(metadata_json)
        except json.JSONDecodeError:
            return jsonify({"error": "Invalid metadata JSON"}), 400

    encrypted_file_content, encrypted_file_key = encrypt_data(file_bytes)
    file_id = uuid.uuid4() # Generar ID antes de guardar para usarlo en ceph_object_key y Kafka
    ceph_object_key = f"{user_id}/{file_id}" # Usa el file_id en la ruta de Ceph

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

        # 3. Publicar evento en Kafka
        event_data = {
            'file_id': str(file_id),
            'user_id': str(user_id),
            'original_filename': original_filename,
            'ceph_path': ceph_object_key,
            'mimetype': mimetype,
            'size_bytes': size_bytes,
            'timestamp': datetime.now().isoformat() # Usar datetime para la marca de tiempo
        }
        # Envía el mensaje de forma asíncrona. delivery_report se llamará cuando se confirme o falle.
        kafka_producer.produce(
            KAFKA_TOPIC_FILE_UPLOADED,
            key=str(file_id).encode('utf-8'), # Clave para asegurar el orden en la misma partición para el mismo archivo
            value=json.dumps(event_data).encode('utf-8'),
            callback=delivery_report
        )
        # Flush() asegura que todos los mensajes pendientes sean enviados.
        # En un sistema de alto rendimiento, puedes flushear periódicamente o al final de la solicitud.
        kafka_producer.flush(timeout=5) # Un pequeño timeout para no bloquear indefinidamente

        print(f"INFO: Evento de subida para file_id {file_id} publicado en Kafka.")

        return jsonify({"message": "File uploaded successfully", "file_id": str(file_id)}), 201

    except Exception as e:
        print(f"ERROR: Fallo al subir archivo: {e}")
        # Si falla la DB o Kafka, intentar limpiar el archivo de S3 para evitar huérfanos.
        try:
            s3_client.delete_object(Bucket=CEPH_BUCKET_NAME, Key=ceph_object_key)
            print(f"INFO: Se limpió {ceph_object_key} de S3 debido a un error.")
        except Exception as s3_e:
            print(f"WARNING: Fallo al limpiar objeto S3: {s3_e}")
        return jsonify({"error": str(e)}), 500
    finally:
        if conn:
            conn.close()

@app.route('/vault/<file_id>', methods=['GET'])
def get_file(file_id):
    user_id_requester = request.args.get('user_id', 'default_user') # Para pruebas, normalmente de sesión
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

        # Desempaca los valores
        ceph_path, raw_encrypted_file_key, original_filename, mimetype, file_owner_user_id = file_record

        # CONVERTIR memoryview a bytes aquí
        encrypted_file_key = bytes(raw_encrypted_file_key)

        # Simulación de autorización: solo el propietario puede descargar
        if str(user_id_requester) != str(file_owner_user_id):
            return jsonify({"error": "Forbidden: You do not own this file"}), 403

        # 1. Descargar de Ceph
        response = s3_client.get_object(Bucket=CEPH_BUCKET_NAME, Key=ceph_path)
        encrypted_file_content = response['Body'].read()

        # 2. Desencriptar
        decrypted_file_content = decrypt_data(encrypted_file_content, encrypted_file_key)

        return send_file(
            io.BytesIO(decrypted_file_content),
            mimetype=mimetype or 'application/octet-stream',
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
    user_id_requester = request.args.get('user_id', 'default_user') # Para pruebas
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
    user_id_requester = request.args.get('user_id', 'default_user') # Para pruebas
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

        # Opcional: Publicar un evento 'file_deleted' en Kafka aquí también
        # kafka_producer.produce('file_deleted', key=str(file_id).encode('utf-8'), value=json.dumps({'file_id': str(file_id), 'user_id': str(file_owner_user_id), 'timestamp': datetime.now().isoformat()}).encode('utf-8'))
        # kafka_producer.flush(timeout=5)

        return jsonify({"message": "File deleted successfully"}), 200

    except Exception as e:
        print(f"ERROR: Fallo al eliminar archivo: {e}")
        return jsonify({"error": str(e)}), 500
    finally:
        if conn:
            conn.close()

@app.route('/vault/user/<user_id>', methods=['GET'])
def list_user_files(user_id):
    user_id_requester = request.args.get('requester_id', 'default_user') # Para pruebas
    # TODO: En un sistema real, verificar si requester_id tiene permiso para ver los archivos de user_id
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
    # Es recomendable usar Gunicorn para producción.
    # Por ejemplo: gunicorn --bind 0.0.0.0:5000 --workers 4 --threads 2 app:app
    app.run(debug=True, host='0.0.0.0', port=5000)