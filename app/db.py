import psycopg2
import os
from dotenv import load_dotenv

load_dotenv()

def get_db_connection():
    conn = psycopg2.connect(
        host=os.getenv("DB_HOST"),
        database=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        port=os.getenv("DB_PORT")
    )
    return conn


def init_db():
    """Initialize database with schema and seed data."""
    conn = None
    cur = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Get the directory where this file is located
        current_dir = os.path.dirname(os.path.abspath(__file__))
        
        # Execute schema.sql
        schema_path = os.path.join(current_dir, 'schema.sql')
        print(f"Loading schema from {schema_path}...")
        with open(schema_path, 'r') as f:
            cur.execute(f.read())
        print("Schema loaded.")
        
        # Check if data already exists in key tables to avoid re-seeding
        cur.execute("SELECT COUNT(*) FROM company;")
        company_count = cur.fetchone()[0]
        print(f"Found {company_count} existing companies.")
        
        if company_count == 0:
            # Execute seed.sql only if tables are empty
            seed_path = os.path.join(current_dir, 'seed.sql')
            print(f"Loading seed data from {seed_path}...")
            with open(seed_path, 'r') as f:
                cur.execute(f.read())
            print("Database seeded successfully.")
        else:
            print(f"Database already has {company_count} companies. Skipping seed.")
        
        conn.commit()
        print("Database initialization complete.")
    except Exception as e:
        print(f"ERROR initializing database: {e}")
        if conn:
            conn.rollback()
        raise
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()