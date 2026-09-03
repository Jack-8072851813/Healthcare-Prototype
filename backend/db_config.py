import os
import psycopg2

def load_dotenv(override=True):
    """Lightweight, zero-dependency dotenv loader."""
    # Look for .env in the current file's directory or the current working directory
    base_dir = os.path.dirname(os.path.abspath(__file__))
    dotenv_paths = [
        os.path.join(base_dir, ".env"),
        os.path.join(os.getcwd(), ".env"),
        os.path.join(os.getcwd(), "backend", ".env")
    ]
    for path in dotenv_paths:
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        key, val = line.split("=", 1)
                        # Strip spaces and optional quotes
                        key = key.strip()
                        val = val.strip().strip('"').strip("'")
                        if override or key not in os.environ:
                            os.environ[key] = val
            break

# Load env variables on module import
load_dotenv()

# Database Config Defaults
DB_HOST = os.getenv("DATABASE_HOST", "localhost")
DB_PORT = os.getenv("DATABASE_PORT", "5433")
DB_NAME = os.getenv("DATABASE_NAME", "healthcare")
DB_USER = os.getenv("DATABASE_USER", "postgres")
DB_PASSWORD = os.getenv("DATABASE_PASSWORD", "reji123@")

def get_db_connection(database_name=None):
    """Establishes and returns a connection to the PostgreSQL database."""
    dbname = database_name or DB_NAME
    return psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        database=dbname,
        user=DB_USER,
        password=DB_PASSWORD
    )

def get_db_connection_string(database_name=None):
    """Returns the PostgreSQL connection DSN string."""
    dbname = database_name or DB_NAME
    return f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{dbname}"
