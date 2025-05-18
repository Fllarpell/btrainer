from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.db.models import Base

# Construct a synchronous DSN for psycopg2 from the async DSN
# Example: postgresql+asyncpg://user:pass@host:port/db -> postgresql://user:pass@host:port/db
sync_db_url = settings.DATABASE_URL
if settings.DATABASE_URL.startswith("postgresql+asyncpg://"):
    sync_db_url = settings.DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://", 1)

print(f"Using synchronous DSN for setup: {sync_db_url}")
engine = create_engine(sync_db_url)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def create_db_tables():
    print("Attempting to create database tables...")
    try:
        Base.metadata.create_all(bind=engine)
        print("Database tables created successfully (or already exist).")

        # Optional: Verify connection by executing a simple query
        with engine.connect() as connection:
            result = connection.execute(text("SELECT 1"))
            print(f"DB connection test successful, selected: {result.scalar_one()}")

    except Exception as e:
        print(f"Error creating database tables: {e}")
        # import traceback
        # traceback.print_exc() # Uncomment for detailed traceback if needed

if __name__ == "__main__":
    create_db_tables() 
