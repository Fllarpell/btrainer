from sqlalchemy import create_engine

from app.core.config import settings 
from app.db.models import Base


DATABASE_URL = settings.DATABASE_URL

if not DATABASE_URL or DATABASE_URL == "postgresql://user:pass@host:port/db":
    print("Error: DATABASE_URL environment variable not set")
    exit(1)

engine = create_engine(DATABASE_URL)

def create_db_tables():
    try:
        Base.metadata.create_all(bind=engine)
        print(f"Database tables created: {engine.url.render_as_string(hide_password=True)}")
    except Exception as e:
        print(f"Error creating database tables: {e}")

if __name__ == "__main__":
    print(f"DATABASE_URL: {engine.url.render_as_string(hide_password=True)}")
    create_db_tables() 
