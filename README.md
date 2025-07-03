Sistema de Bóveda Digital con Ceph, Python y PostgreSQL
Este sistema permitirá el almacenamiento seguro de archivos encriptados utilizando Ceph como backend de almacenamiento, gestionando la metadata en PostgreSQL y exponiendo una API RESTful para la interacción.

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

Justificación de Tecnologías
Ceph: Es una excelente elección para el almacenamiento de objetos distribuidos. Proporciona alta disponibilidad, escalabilidad y tolerancia a fallos, lo que lo hace ideal para una bóveda digital donde la durabilidad de los archivos es crítica. Utilizaremos el protocolo S3 (compatible con Ceph Rados Gateway) para interactuar con él, lo cual simplifica la integración.
Python: Es el lenguaje más adecuado para este tipo de servicio por varias razones:
  Madurez de Bibliotecas: Cuenta con bibliotecas robustas para todas las necesidades:
  boto3: Para interactuar con Ceph (a través de la API S3).
  psycopg2 o SQLAlchemy: Para la interacción con PostgreSQL.
  cryptography: Para el manejo de encriptación y desencriptación robusta.
  Flask o FastAPI: Para construir la API REST de manera eficiente y escalable.
Productividad: Su sintaxis clara y concisa permite un desarrollo rápido.
Comunidad y Soporte: Amplia comunidad y recursos disponibles.
Rendimiento: Suficiente para este tipo de aplicación, especialmente cuando se delega el almacenamiento a Ceph y la base de datos a PostgreSQL.

PostgreSQL: Es una base de datos relacional de objetos muy potente y confiable, ideal para almacenar la metadata de los archivos.
Soporte JSON/JSONB: Su capacidad para almacenar datos en formatos JSON o JSONB es perfecta para la metadata variable de los archivos. JSONB es preferible por su eficiencia en el almacenamiento y las consultas indexadas.
Robustez y Transaccionalidad: Garantiza la integridad de los datos.
Seguridad: Ofrece características de seguridad avanzadas.

Kafka: El uso de Kafka en tu bóveda digital puede ser muy útil y beneficioso si:
Esperas un volumen significativo de subidas/descargas/operaciones.
Necesitas realizar múltiples tipos de procesamiento sobre los archivos (indexación, OCR, análisis de seguridad, etc.).
Buscas una alta escalabilidad y desacoplamiento entre los componentes de tu arquitectura.
Requiere auditoría robusta y trazabilidad de eventos.
Necesitas integrar la bóveda con otros sistemas empresariales.
Si tus requisitos son más modestos, la complejidad de Kafka podría ser excesiva. Pero para una solución "completa" y preparada para el futuro, Kafka es un componente estratégico que habilita capacidades que serían difíciles de lograr de otra manera.

Valkey (o Redis) para Caching y Sesiones:
Para qué: Como mencionamos, Valkey es excelente para caching (evitar consultas repetitivas a la base de datos para datos frecuentemente accedidos como metadatos de archivos), gestión de sesiones de usuario (almacenar tokens de autenticación), y como broker para Celery (si decides implementar tareas en segundo plano más avanzadas).
Beneficio: Mejora el rendimiento de la API al reducir la carga en PostgreSQL y proporciona un almacenamiento temporal rápido. Ya tienes PostgreSQL para datos persistentes y Kafka para eventos, Valkey llenaría el rol de almacenamiento "rápido y volátil".

Celery (con Valkey/Redis o RabbitMQ como Broker):
Para qué: Es un sistema de colas de tareas distribuidas. Perfecto para las tareas asíncronas que hablamos de poner en tu consumidor de Kafka.
Beneficio: Te permite ejecutar tareas que consumen mucho tiempo (como escaneo de virus, transcodificación, generación de miniaturas) en procesos separados, liberando tu API para responder rápidamente a los usuarios. Los eventos de Kafka pueden disparar estas tareas de Celery.

Arquitectura General
+----------------+       +-------------------+       +-------------------+
|   Sistema Web  | <---> |   Servicio Backend  | <---> |    Base de Datos  |
| (Frontend/UI)  |       |  (Python/Flask/   |       |    (PostgreSQL)   |
|                |       |     FastAPI)      |       |  - Metadata Archivos
+----------------+       +---------|---------+       |  - Usuarios
                                   |                   +-------------------+
                                   |
                                   | S3 API (boto3)
                                   V
                          +----------------+
                          |      Ceph      |
                          | (Rados Gateway)|
                          +----------------+
Módulo de Encriptación/Desencriptación
Utilizar la librería cryptography.fernet o cryptography.hazmat.primitives.ciphers para una encriptación simétrica robusta (ej. AES en modo GCM).
Clave de encriptación por archivo: Cada archivo debe tener una clave de encriptación única. Esto es crucial para la seguridad: si una clave se compromete, solo un archivo se ve afectado.
Clave Maestra del Sistema: Una clave maestra (o un par de claves asimétricas) debe ser utilizada para encriptar las claves individuales de los archivos antes de almacenarlas en PostgreSQL. Esta clave maestra debe ser gestionada de forma extremadamente segura (ej. variables de entorno, HashiCorp Vault, AWS Secrets Manager, etc.).

Proceso de Encriptación:
Generar una clave simétrica para el archivo (ej., Fernet.generate_key()).
Inicializar el objeto de encriptación con esta clave.
Encriptar el contenido del archivo.
Encriptar la clave simétrica del archivo usando la clave maestra del sistema.
Almacenar la clave simétrica encriptada en PostgreSQL.

Proceso de Desencriptación:
Recuperar la clave simétrica encriptada desde PostgreSQL.
Desencriptar la clave simétrica del archivo usando la clave maestra del sistema.
Descargar el archivo encriptado de Ceph.
Desencriptar el archivo usando la clave simétrica.

Módulo de Interacción con Ceph (S3)
Utilizar boto3, el SDK de AWS para Python, que es compatible con Ceph S3.
Configurar el cliente boto3 para apuntar al endpoint de Ceph Rados Gateway, en lugar de AWS S3.
Funciones para subir (put_object), descargar (get_object) y eliminar (delete_object) archivos.

Módulo de Interacción con PostgreSQL
Utilizar psycopg2 directamente o un ORM como SQLAlchemy para una gestión de base de datos más abstracta y robusta.



¿Por qué Digital Vault?
Este proyecto es ideal para desarrolladores y equipos que buscan entender o implementar:

Arquitecturas de microservicios.
Patrones de cifrado de datos en tránsito y en reposo.
Uso de almacenamiento de objetos distribuido.
Sistemas de colas de mensajes (Kafka) para comunicación asíncrona.
Procesamiento de tareas en segundo plano (Celery).
Despliegues con Docker Compose para entornos de desarrollo.

![image](https://github.com/user-attachments/assets/9cc1be91-94df-4544-af57-6c7839f47878)

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

Estructura de la tabla files (ejemplo):

SQL

CREATE TABLE files (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL, -- O INT si tus IDs de usuario son enteros
    ceph_path TEXT NOT NULL, -- Ruta o clave del objeto en Ceph
    encryption_key_encrypted BYTEA NOT NULL, -- Clave de encriptación del archivo, encriptada con la clave maestra
    original_filename TEXT NOT NULL,
    mimetype TEXT,
    size_bytes BIGINT,
    upload_timestamp TIMESTAMPTZ DEFAULT NOW(),
    metadata JSONB, -- Almacena la metadata variable del archivo
    CONSTRAINT fk_user
        FOREIGN KEY(user_id)
        REFERENCES users(id) -- Si tienes una tabla de usuarios
);

-- Tabla de usuarios (opcional, pero recomendada)
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    username VARCHAR(255) UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    email VARCHAR(255) UNIQUE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);


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
![image](https://github.com/user-attachments/assets/996b4710-2a36-4a03-bfd7-1f3166afb0d6)

🚀 Uso de la API (Ejemplos con Postman/cURL)
La API opera en http://127.0.0.1:5000.

![image](https://github.com/user-attachments/assets/d64c2d54-f6b6-43f1-802b-ee6f7816d0eb)


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

![image](https://github.com/user-attachments/assets/fa158202-4532-42aa-aecc-62a2d50271ef)


2. Obtener Metadatos de un Archivo (GET)
Recupera los metadatos de un archivo específico.

URL: http://127.0.0.1:5000/vault/metadata/{file_id}?user_id=[user_id]

Método: GET

Ejemplo: http://127.0.0.1:5000/vault/metadata/a0fb4e20-9440-4d15-94df-979f8f42a2a3?user_id=default_user

![image](https://github.com/user-attachments/assets/c4752147-5ef5-4e2c-8411-48d6fc4b329a)


3. Descargar un Archivo (GET)
Descarga un archivo previamente subido, que será descifrado al vuelo.

URL: http://127.0.0.1:5000/vault/{file_id}?user_id=[user_id]

Método: GET

Ejemplo: http://127.0.0.1:5000/vault/a0fb4e20-9440-4d15-94df-979f8f42a2a3?user_id=default_user

![image](https://github.com/user-attachments/assets/5bb6f300-a33b-44ad-99f4-983ab8817b52)


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

Consideraciones de Seguridad Adicionales
Autenticación y Autorización: Implementar un sistema de autenticación (ej., JWT) y autorización basado en roles/permisos para controlar quién puede subir, descargar o eliminar archivos.
Gestión de Claves: La clave maestra del sistema (para encriptar las claves de los archivos) es el punto más crítico. NUNCA debe estar en el código fuente ni ser accedida directamente por usuarios. Considera usar un servicio de gestión de secretos.
Comunicación Segura: Todas las comunicaciones (entre el cliente web y el servicio, y entre el servicio y Ceph/PostgreSQL) deben ser sobre HTTPS/TLS.
Validación de Entradas: Validar todas las entradas de usuario para prevenir inyecciones SQL, ataques XSS, etc.
Auditoría y Logs: Registrar todas las operaciones importantes (subidas, descargas, eliminaciones, intentos de acceso fallidos) para propósitos de auditoría y detección de anomalías.
Respaldo: Implementar una estrategia de respaldo tanto para Ceph como para PostgreSQL.


🤝 Contribuciones
Las contribuciones son bienvenidas. Si tienes sugerencias de mejora, nuevas características o encuentras algún bug, por favor:

Haz un "fork" del repositorio.

Crea una nueva rama (git checkout -b feature/nueva-caracteristica o bugfix/solucion-bug).

Realiza tus cambios y commitea (git commit -m 'feat: Añade nueva característica').

Haz "push" a tu rama (git push origin feature/nueva-caracteristica).

Abre un "Pull Request" explicando tus cambios.

Este proyecto está licenciado bajo la Licencia MIT - ver el archivo [LICENSE](LICENSE) para más detalles.
