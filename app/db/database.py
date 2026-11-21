import os
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

db_url = os.environ.get("DATABASE_URL", "").strip().strip("\"'")

if db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql://", 1)

if not db_url or db_url == "DATABASE_URL" or not (db_url.startswith("postgresql://") or db_url.startswith("sqlite://")):
    print("[Database Info] DATABASE_URL is missing or invalid. Using default local SQLite database.")
    SQLALCHEMY_DATABASE_URL = "sqlite:///./smart_reader.db"
else:
    if "supabase" in db_url and "sslmode" not in db_url:
        if "?" in db_url:
            db_url += "&sslmode=require"
        else:
            db_url += "?sslmode=require"
    SQLALCHEMY_DATABASE_URL = db_url

if SQLALCHEMY_DATABASE_URL.startswith("sqlite"):
    engine = create_engine(
        SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
    )
else:
    try:
        temp_engine = create_engine(SQLALCHEMY_DATABASE_URL, pool_pre_ping=True, connect_args={"connect_timeout": 5})
        with temp_engine.connect() as conn:
            pass
        engine = temp_engine
        masked = SQLALCHEMY_DATABASE_URL
        if "@" in masked:
            p = masked.split("@")
            masked = f"{p[0].split(':')[0]}:****@{p[1]}"
        print(f"[Database Info] CONNECTED TO REMOTE POSTGRESQL: {masked}")
    except Exception as e:
        print(f"[Database Warning] Could not connect to PostgreSQL ({e}). Falling back to local SQLite database.")
        SQLALCHEMY_DATABASE_URL = "sqlite:///./smart_reader.db"
        engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
