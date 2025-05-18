from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import sessionmaker
from app.core.config import settings


async_engine = create_async_engine(
    settings.DATABASE_URL, 
    pool_pre_ping=True,
    echo=settings.LOG_LEVEL == "DEBUG"
)

AsyncSessionLocal = async_sessionmaker(
    bind=async_engine,
    class_=AsyncSession,
    autocommit=False, 
    autoflush=False, 
    expire_on_commit=False
) 