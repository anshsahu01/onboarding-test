"""
Configuration management for the application.
Loads environment variables and provides type-safe settings.

Usage:
    from app.core.config import settings
    print(settings.DATABASE_URL)
"""

import os
from typing import Optional
from pydantic_settings import BaseSettings
from pydantic import Field, validator


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables.

    To switch between local and DigitalOcean:
    Just change DATABASE_URL in .env file - no code changes needed!
    """

    # ============================================
    # APPLICATION SETTINGS
    # ============================================
    APP_NAME: str = "Onboarding API"
    APP_VERSION: str = "1.0.0"
    ENVIRONMENT: str = Field(default="development")  # development, staging, production
    DEBUG: bool = Field(default=True)

    # ============================================
    # DATABASE SETTINGS
    # ============================================
    DATABASE_URL: str = Field(
        default="postgresql+asyncpg://postgres:postgres@localhost:5432/onboarding_db",
        description="PostgreSQL connection string"
    )

    # Database pool settings
    DB_POOL_SIZE: int = Field(default=10, description="Number of permanent connections")
    DB_MAX_OVERFLOW: int = Field(default=20, description="Max additional connections")
    DB_POOL_TIMEOUT: int = Field(default=30, description="Connection timeout in seconds")
    DB_POOL_RECYCLE: int = Field(default=3600, description="Recycle connections after N seconds")
    DB_ECHO: bool = Field(default=False, description="Log all SQL queries (use in debug)")

    # ============================================
    # LLM API SETTINGS
    # ============================================
    LLM_PROVIDER: str = Field(default="openai", description="openai, gemini, or deepseek")

    # OpenAI
    OPENAI_API_KEY: Optional[str] = None
    OPENAI_API_URL: str = "https://api.openai.com/v1/chat/completions"
    OPENAI_MODEL: str = "gpt-4o"

    # Gemini
    GEMINI_API_KEY: Optional[str] = None
    GEMINI_MODEL: str = "gemini-2.0-flash"

    # DeepSeek
    DEEPSEEK_API_KEY: Optional[str] = None
    DEEPSEEK_API_URL: str = "https://api.deepseek.com/v1/chat/completions"
    DEEPSEEK_MODEL: str = "deepseek-chat"

    # ============================================
    # CORS SETTINGS
    # ============================================
    CORS_ORIGINS: list = ["http://localhost:3000", "http://localhost:5173"]
    CORS_ALLOW_CREDENTIALS: bool = True
    CORS_ALLOW_METHODS: list = ["*"]
    CORS_ALLOW_HEADERS: list = ["*"]

    # ============================================
    # VALIDATORS
    # ============================================

    @validator("DATABASE_URL")
    def validate_database_url(cls, v):
        """Ensure DATABASE_URL is set and valid"""
        if not v:
            raise ValueError("DATABASE_URL must be set in .env file")

        if not v.startswith("postgresql"):
            raise ValueError("DATABASE_URL must be a PostgreSQL connection string")

        return v

    @validator("DB_ECHO", pre=True)
    def set_db_echo_from_debug(cls, v, values):
        """Auto-enable SQL logging in DEBUG mode"""
        if values.get("DEBUG") and v is None:
            return True
        return v

    # ============================================
    # HELPER PROPERTIES
    # ============================================

    @property
    def is_development(self) -> bool:
        """Check if running in development mode"""
        return self.ENVIRONMENT == "development"

    @property
    def is_production(self) -> bool:
        """Check if running in production mode"""
        return self.ENVIRONMENT == "production"

    @property
    def database_config(self) -> dict:
        """Get database connection configuration"""
        return {
            "url": self.DATABASE_URL,
            "pool_size": self.DB_POOL_SIZE,
            "max_overflow": self.DB_MAX_OVERFLOW,
            "pool_timeout": self.DB_POOL_TIMEOUT,
            "pool_recycle": self.DB_POOL_RECYCLE,
            "echo": self.DB_ECHO,
        }

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True
        extra = "ignore"  # Ignore extra fields from .env


# ============================================
# SINGLETON INSTANCE
# ============================================

# Create a single instance to be imported everywhere
settings = Settings()


# ============================================
# STARTUP VALIDATION
# ============================================

def validate_settings():
    """
    Validate all required settings on startup.
    Call this in main.py before starting the server.
    """
    errors = []

    # Check database URL
    if "your_password" in settings.DATABASE_URL:
        errors.append("❌ DATABASE_URL still contains 'your_password' - update .env file!")

    # Check LLM API keys
    if settings.LLM_PROVIDER == "openai" and not settings.OPENAI_API_KEY:
        errors.append("❌ OPENAI_API_KEY not set but LLM_PROVIDER is 'openai'")

    if settings.LLM_PROVIDER == "gemini" and not settings.GEMINI_API_KEY:
        errors.append("❌ GEMINI_API_KEY not set but LLM_PROVIDER is 'gemini'")

    if settings.LLM_PROVIDER == "deepseek" and not settings.DEEPSEEK_API_KEY:
        errors.append("❌ DEEPSEEK_API_KEY not set but LLM_PROVIDER is 'deepseek'")

    if errors:
        print("\n" + "="*60)
        print("⚠️  CONFIGURATION ERRORS")
        print("="*60)
        for error in errors:
            print(error)
        print("="*60 + "\n")
        raise ValueError("Configuration validation failed")

    # Success message
    print("\n" + "="*60)
    print("✅ Configuration validated successfully!")
    print("="*60)
    print(f"Environment: {settings.ENVIRONMENT}")
    print(f"Debug Mode: {settings.DEBUG}")
    print(f"Database: {settings.DATABASE_URL.split('@')[1] if '@' in settings.DATABASE_URL else 'Not configured'}")
    print(f"LLM Provider: {settings.LLM_PROVIDER}")
    print("="*60 + "\n")


# ============================================
# USAGE EXAMPLE
# ============================================

if __name__ == "__main__":
    # Test configuration loading
    print("Loading configuration...")
    validate_settings()
    print(f"App Name: {settings.APP_NAME}")
    print(f"Database URL: {settings.DATABASE_URL}")
    print(f"LLM Provider: {settings.LLM_PROVIDER}")
