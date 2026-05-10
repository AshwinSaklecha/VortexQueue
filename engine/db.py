import psycopg2
from psycopg2.extras import RealDictCursor
import uuid
import os
from dotenv import load_dotenv
load_dotenv()

# 1. The Connection Settings
# Update the password to whatever your local PostgreSQL password is
DB_CONFIG = {
    "dbname": os.getenv("DB_NAME"),
    "user": os.getenv("DB_USER"),
    "password": os.getenv("DB_PASSWORD"), 
    "host": os.getenv("DB_HOST"),
    "port": int(os.getenv("DB_PORT", "5432"))
}

def get_db_connection():
    """
    Opens a connection to PostgreSQL. 
    We use RealDictCursor so database rows come back as Python dictionaries 
    (e.g., row['status']) instead of confusing tuples (row[2]).
    """
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        # This ensures every database command we run is committed automatically
        conn.autocommit = True 
        return conn
    except Exception as e:
        print(f"Database connection failed: {e}")
        return None

# Let's test if it works!
if __name__ == "__main__":
    conn = get_db_connection()
    if conn:
        print("Success! Connected to PostgreSQL.")
        conn.close()