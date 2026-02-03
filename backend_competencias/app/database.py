from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
import os
from dotenv import load_dotenv

load_dotenv()

# ✅ URL de conexión (MySQL)
DATABASE_URL = os.getenv("DATABASE_URL", "mysql+pymysql://root:@localhost:3306/competencias_db")

# Crear el engine sin probar conexión en el import. 
# pool_pre_ping ayuda a reconectar conexiones muertas.
engine = create_engine(DATABASE_URL, pool_pre_ping=True)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Función opcional para probar la conexión manualmente (usar desde CLI o en un healthcheck)
def test_connection():
    try:
        with engine.connect() as conn:
            print("Database connection successful")
            return True
    except Exception as e:
        print(f"Database connection failed: {e}")
        return False