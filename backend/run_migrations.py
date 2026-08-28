import os
import re
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
import db_config

def create_database_if_not_exists():
    """Connects to 'postgres' database and creates the target database if it does not exist."""
    print("Checking if target database exists...")
    target_db = db_config.DB_NAME
    
    # Establish connection to the default 'postgres' database
    conn = None
    try:
        conn = psycopg2.connect(
            host=db_config.DB_HOST,
            port=db_config.DB_PORT,
            user=db_config.DB_USER,
            password=db_config.DB_PASSWORD,
            database="postgres"
        )
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cur = conn.cursor()
        
        # Check if DB exists
        cur.execute("SELECT 1 FROM pg_database WHERE datname = %s;", (target_db,))
        exists = cur.fetchone()
        
        if not exists:
            print(f"Database '{target_db}' does not exist. Creating database...")
            # Database creation cannot run inside a transaction block, which is why we set autocommit above
            cur.execute(f'CREATE DATABASE "{target_db}";')
            print(f"Database '{target_db}' created successfully.")
        else:
            print(f"Database '{target_db}' already exists.")
            
        cur.close()
    except Exception as e:
        print(f"Error checking/creating database: {e}")
        raise e
    finally:
        if conn:
            conn.close()

def run_migrations():
    """Reads and executes all SQL migration files in the migrations directory."""
    print("Running migrations...")
    migrations_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "migrations")
    
    # Get all .sql files in migrations directory and sort them alphabetically/numerically
    sql_files = sorted([f for f in os.listdir(migrations_dir) if f.endswith(".sql")])
    
    if not sql_files:
        print("No migration SQL files found.")
        return
        
    print(f"Found {len(sql_files)} migration files to execute.")
    
    # Connect to the target database
    conn = db_config.get_db_connection()
    conn.autocommit = False # Use transactions for safety
    
    try:
        cur = conn.cursor()
        
        # 1. Create the update trigger function if not exists
        print("Creating automatic updated_at trigger function...")
        cur.execute("""
            CREATE OR REPLACE FUNCTION update_modified_column()
            RETURNS TRIGGER AS $$
            BEGIN
                NEW.updated_at = now();
                RETURN NEW;
            END;
            $$ language 'plpgsql';
        """)
        
        # 2. Run migration files
        for sql_file in sql_files:
            file_path = os.path.join(migrations_dir, sql_file)
            print(f"Executing migration: {sql_file}")
            with open(file_path, "r", encoding="utf-8") as f:
                sql_content = f.read()
                
            if sql_content.strip():
                cur.execute(sql_content)
                
        # 3. Apply the updated_at trigger to tables that have it
        tables_with_updated_at = [
            "roles", "users", "patients", "departments", "doctors", 
            "doctor_schedules", "appointments", "pre_admissions", 
            "conversations", "knowledge_documents", "knowledge_chunks"
        ]
        
        for table in tables_with_updated_at:
            # Drop the trigger if exists and recreate it to be idempotent
            cur.execute(f"DROP TRIGGER IF EXISTS update_{table}_modtime ON {table};")
            cur.execute(f"""
                CREATE TRIGGER update_{table}_modtime
                BEFORE UPDATE ON {table}
                FOR EACH ROW
                EXECUTE FUNCTION update_modified_column();
            """)
            print(f"Registered updated_at trigger for table: {table}")
            
        # Commit the transaction
        conn.commit()
        print("All migrations completed successfully!")
        
    except Exception as e:
        print(f"Migration failed: rollback initiated. Error: {e}")
        conn.rollback()
        raise e
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    create_database_if_not_exists()
    run_migrations()
