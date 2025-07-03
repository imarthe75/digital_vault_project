# test_db_connection.py
import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()

POSTGRES_DB = os.getenv('POSTGRES_DB')
POSTGRES_USER = os.getenv('POSTGRES_USER')
POSTGRES_PASSWORD = os.getenv('POSTGRES_PASSWORD')
POSTGRES_HOST = os.getenv('POSTGRES_HOST')
POSTGRES_PORT = os.getenv('POSTGRES_PORT', '5432')

print(f"Connecting to DB: {POSTGRES_DB}")
print(f"User: {POSTGRES_USER}")
print(f"Host: {POSTGRES_HOST}")
print(f"Port: {POSTGRES_PORT}")
print(f"Password: {POSTGRES_PASSWORD}") # Temporarily print to confirm it's clean

try:
    conn = psycopg2.connect(
        dbname=POSTGRES_DB,
        user=POSTGRES_USER,
        password=POSTGRES_PASSWORD,
        host=POSTGRES_HOST,
        port=POSTGRES_PORT
    )
    print("SUCCESS: Connected to PostgreSQL!")
    conn.close()
except psycopg2.Error as e:
    print(f"ERROR: Could not connect to PostgreSQL: {e}")
    import traceback
    traceback.print_exc()
except Exception as e:
    print(f"ANOTHER ERROR: {e}")
    import traceback
    traceback.print_exc()