import sys
import asyncio
from urllib.parse import quote_plus
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase
from pydantic_settings import BaseSettings
import logging

# Configure centralized logging first
from app.logging_config import get_logger
logger = get_logger("app.db")

# --- 1. CONFIGURATION ---
class Settings(BaseSettings):
    DB_USER: str
    DB_PASSWORD: str
    DB_HOST: str
    DB_PORT: str
    DB_NAME: str

    class Config:
        env_file = ".env"
        extra = "ignore"

settings = Settings()

# Construct the URL safely with URL encoding for special characters
# Format: postgresql+asyncpg://user:pass@host:port/dbname
# URL-encode password to handle special characters like @, :, /, etc.
encoded_password = quote_plus(settings.DB_PASSWORD)
DATABASE_URL = f"postgresql+asyncpg://{settings.DB_USER}:{encoded_password}@{settings.DB_HOST}:{settings.DB_PORT}/{settings.DB_NAME}"

# --- 2. WINDOWS FIX ---
# This is crucial for "getaddrinfo failed" errors on Windows/Asyncpg
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

# --- 3. ENGINE SETUP ---
engine = create_async_engine(
    DATABASE_URL,
    echo=True, # Logs SQL queries to terminal (good for debugging)
)

# --- 4. SESSION FACTORY ---
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False
)

# --- 5. BASE MODEL ---
class Base(DeclarativeBase):
    pass

# --- 6. DEPENDENCY ---
# Use this in your FastAPI routes
async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            logger.debug("Database session created")
            yield session
            logger.debug("Database session completed")
        except Exception as e:
            logger.error(f"Database session error: {type(e).__name__}: {str(e)}")
            raise
        finally:
            await session.close()
            logger.debug("Database session closed")