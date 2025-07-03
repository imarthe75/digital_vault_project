Digital Vault es una solución robusta y moderna para la gestión segura y descentralizada de archivos digitales. Diseñado con una arquitectura de microservicios y tecnologías de vanguardia, este proyecto demuestra cómo construir un sistema escalable y resiliente que prioriza la seguridad, la asincronía y la eficiencia en el manejo de datos sensibles.

Características Principales:
API RESTful con Flask: Un backend potente y flexible desarrollado con Flask, ofreciendo endpoints intuitivos para la subida, descarga, eliminación y gestión de metadatos de archivos.

Almacenamiento Descentralizado con MinIO/Ceph: Los archivos se almacenan de forma segura en un clúster de objetos compatible con S3 (MinIO, emulando Ceph), garantizando alta disponibilidad y escalabilidad.

Cifrado Robusto de Archivos: Cada archivo se cifra con una clave única (Fernet) antes de ser almacenado, y esta clave de cifrado se gestiona de forma segura, garantizando que solo los usuarios autorizados puedan acceder al contenido original.

Base de Datos PostgreSQL: Almacenamiento fiable de metadatos de archivos (nombres, ubicaciones, claves de cifrado) para una gestión y recuperación eficientes.

Procesamiento Asíncrono con Celery y Redis/Valkey: Las tareas intensivas, como el cifrado y el procesamiento post-subida, se delegan a workers de Celery, utilizando Redis (o Valkey) como broker, lo que asegura que la API responda rápidamente y el procesamiento se realice en segundo plano.

Comunicación de Eventos con Apache Kafka: Implementación de un productor de Kafka para publicar eventos de subida de archivos, permitiendo la integración con futuros servicios que necesiten reaccionar a la actividad del sistema.

Contenedorización con Docker Compose: Todos los componentes de la infraestructura (MinIO, PostgreSQL, Redis/Valkey, Zookeeper, Kafka, Celery Worker) se orquestan fácilmente con Docker Compose, facilitando la configuración del entorno de desarrollo.

Diseño Modular y Escalable: La arquitectura de microservicios permite escalar componentes de forma independiente y facilita el desarrollo y mantenimiento.

¿Por qué Digital Vault?
Este proyecto es ideal para desarrolladores y equipos que buscan entender o implementar:

Arquitecturas de microservicios.

Patrones de cifrado de datos en tránsito y en reposo.

Uso de almacenamiento de objetos distribuido.

Sistemas de colas de mensajes (Kafka) para comunicación asíncrona.

Procesamiento de tareas en segundo plano (Celery).

Despliegues con Docker Compose para entornos de desarrollo.

¡Explora el código, contribuye o adáptalo a tus propias necesidades!

🚀 Instalación y Configuración
Sigue estos pasos para poner en marcha el proyecto en tu entorno de desarrollo.

1. Clonar el Repositorio
Bash

git clone https://github.com/tu_usuario/digital_vault_project.git
cd digital_vault_project
2. Configurar Variables de Entorno
Crea un archivo .env en la raíz del proyecto (junto a docker-compose.yml) y configura las siguientes variables. Puedes usar nuevo1.env como plantilla si lo tienes.

.env:

Fragmento de código

# Configuración del Backend (Flask) y PostgreSQL
POSTGRES_DB=digital_vault_db
POSTGRES_USER=dvu
POSTGRES_PASSWORD=testpass # Asegúrate de que coincida con tu instalación nativa de PostgreSQL
POSTGRES_HOST=localhost # ¡Importante! Para tu instalación nativa de Windows
POSTGRES_PORT=5432

# Configuración de Valkey (Redis)
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0

# Configuración de MinIO/Ceph
CEPH_ENDPOINT_URL=http://localhost:9000
CEPH_ACCESS_KEY=minioadmin # Clave por defecto de MinIO
CEPH_SECRET_KEY=minioadmin # Clave por defecto de MinIO
CEPH_BUCKET_NAME=digital-vault-bucket

# Clave Maestra del Sistema (Fernet) - Genera una con `from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())`
SYSTEM_MASTER_KEY=TU_CLAVE_FERNET_BASE64_AQUI=

# Configuración de Kafka
KAFKA_BOOTSTRAP_SERVERS=localhost:9092
3. Levantar Servicios con Docker Compose
Navega a la raíz del proyecto donde se encuentra docker-compose.yml y levanta todos los servicios. Asegúrate de que Docker Desktop esté corriendo.

Bash

docker-compose up -d --build
Esto levantará los siguientes servicios:

zookeeper (para Kafka)

kafka (broker de mensajes)

valkey (broker y backend de resultados para Celery)

minio (almacenamiento de objetos compatible con S3)

celery_worker (procesa tareas asíncronas)

4. Configurar PostgreSQL
Si aún no lo has hecho:

Asegúrate de que tu instancia de PostgreSQL nativa en Windows esté corriendo y acepte conexiones en el puerto 5432.

Crea la base de datos digital_vault_db y el usuario dvu con la contraseña testpass.

Puedes hacerlo conectándote a psql (o pgAdmin) y ejecutando:

SQL

CREATE DATABASE digital_vault_db;
CREATE USER dvu WITH PASSWORD 'testpass';
GRANT ALL PRIVILEGES ON DATABASE digital_vault_db TO dvu;
Ejecuta las migraciones de la base de datos (crear tablas):
Navega a la carpeta backend e instala las dependencias de Python:

Bash

cd backend
pip install -r requirements.txt
Luego, ejecuta el script de inicialización de la base de datos (si tienes uno, por ejemplo, init_db.py o directamente desde app.py si tiene una función de inicialización de tablas):

Bash

python -c "from app import create_tables; create_tables()" # Asumiendo que create_tables() está en app.py
(Si no tienes una función create_tables separada, deberías agregarla a app.py o ejecutar las sentencias SQL para crear la tabla files manualmente.)

5. Iniciar la Aplicación Flask (Backend)
Desde la carpeta backend:

Bash

python app.py
La aplicación Flask se ejecutará en http://127.0.0.1:5000 (o http://localhost:5000).

🛠️ Estructura del Proyecto
El proyecto se organiza de la siguiente manera:

/: Contiene el docker-compose.yml, .env y el Dockerfile principal.

backend/: Contiene la lógica del backend de Flask.

app.py: La aplicación Flask principal, rutas, lógica de autenticación y conexión a servicios.

tasks.py: Definiciones de tareas Celery para procesamiento asíncrono.

minio_client.py: Módulo para interactuar con MinIO/Ceph.

kafka_producer.py: Módulo para producir mensajes a Kafka.

db.py: Lógica de conexión y operaciones con la base de datos PostgreSQL. (Podrías considerar mover get_db_connection y la lógica de creación de tablas aquí)

utils.py: Funciones de utilidad (ej. cifrado/descifrado).

requirements.txt: Dependencias de Python para el backend y Celery.

Dockerfile: Define la imagen Docker para el Celery worker.

frontend/ (Si existe): Contiene el código de la interfaz de usuario.

🚀 Uso de la API (Ejemplos con Postman/cURL)
La API opera en http://127.0.0.1:5000.

1. Subir un Archivo (POST)
Sube un archivo, cifrándolo y almacenando sus metadatos.

URL: http://127.0.0.1:5000/vault/upload

Método: POST

Headers:

Content-Type: multipart/form-data

Body (form-data):

file: Selecciona el archivo que deseas subir.

user_id: [ID del usuario que sube el archivo, ej., default_user]

original_filename: [Nombre original del archivo, ej., documento.pdf]

2. Obtener Metadatos de un Archivo (GET)
Recupera los metadatos de un archivo específico.

URL: http://127.0.0.1:5000/vault/metadata/{file_id}?user_id=[user_id]

Método: GET

Ejemplo: http://127.0.0.1:5000/vault/metadata/a0fb4e20-9440-4d15-94df-979f8f42a2a3?user_id=default_user

3. Descargar un Archivo (GET)
Descarga un archivo previamente subido, que será descifrado al vuelo.

URL: http://127.0.0.1:5000/vault/{file_id}?user_id=[user_id]

Método: GET

Ejemplo: http://127.0.0.1:5000/vault/a0fb4e20-9440-4d15-94df-979f8f42a2a3?user_id=default_user

4. Listar Archivos por Usuario (GET)
Obtiene una lista de todos los archivos asociados a un user_id específico.

URL: http://127.0.0.1:5000/vault/user/{user_id}?requester_id=[requester_id]

Método: GET

Ejemplo: http://127.0.0.1:5000/vault/user/default_user?requester_id=admin

5. Eliminar un Archivo (DELETE)
Elimina un archivo del almacenamiento y sus metadatos de la base de datos.

URL: http://127.0.0.1:5000/vault/{file_id}?user_id=[user_id]

Método: DELETE

Ejemplo: http://127.0.0.1:5000/vault/a0fb4e20-9440-4d15-94df-979f8f42a2a3?user_id=default_user

🤝 Contribuciones
Las contribuciones son bienvenidas. Si tienes sugerencias de mejora, nuevas características o encuentras algún bug, por favor:

Haz un "fork" del repositorio.

Crea una nueva rama (git checkout -b feature/nueva-caracteristica o bugfix/solucion-bug).

Realiza tus cambios y commitea (git commit -m 'feat: Añade nueva característica').

Haz "push" a tu rama (git push origin feature/nueva-caracteristica).

Abre un "Pull Request" explicando tus cambios.

Este proyecto está licenciado bajo la Licencia MIT - ver el archivo [LICENSE](LICENSE) para más detalles.
