#!/usr/bin/env python3
"""Reset database and re-seed with fresh data."""

from app.db import get_db_connection
import os

def reset_and_seed():
    conn = get_db_connection()
    cur = conn.cursor()
    
    print("Clearing existing data...")
    # Disable foreign key checks temporarily (PostgreSQL uses CASCADE)
    cur.execute("""
        DO $$ DECLARE
            r RECORD;
        BEGIN
            FOR r IN (SELECT tablename FROM pg_tables WHERE schemaname = 'public') LOOP
                EXECUTE 'TRUNCATE TABLE ' || quote_ident(r.tablename) || ' CASCADE';
            END LOOP;
        END $$;
    """)
    
    print("Re-running schema...")
    current_dir = os.path.dirname(os.path.abspath(__file__))
    schema_path = os.path.join(current_dir, 'app', 'schema.sql')
    with open(schema_path, 'r') as f:
        cur.execute(f.read())
    
    print("Re-seeding data...")
    seed_path = os.path.join(current_dir, 'app', 'seed.sql')
    with open(seed_path, 'r') as f:
        cur.execute(f.read())
    
    conn.commit()
    cur.close()
    conn.close()
    print("Database reset and seeded successfully!")

if __name__ == "__main__":
    reset_and_seed()
