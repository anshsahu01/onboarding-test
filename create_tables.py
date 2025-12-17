"""
Create database tables.
Run this once to initialize your database schema.
"""
import sys
import asyncio

# FORCE WINDOWS TO USE THE CORRECT EVENT LOOP
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from app.db import engine, Base
from app.models_db.db_models import OnboardingSession, UserProfile


async def create_tables():
    """Create all tables defined in models."""
    print("🔧 Creating database tables...")

    async with engine.begin() as conn:
        # Drop all tables (use with caution - only for development)
        # await conn.run_sync(Base.metadata.drop_all)

        # Create all tables
        await conn.run_sync(Base.metadata.create_all)

    print("✅ Tables created successfully!")
    print("\nCreated tables:")
    print("  - onboarding_sessions")
    print("  - user_profiles")


async def main():
    try:
        await create_tables()
    except Exception as e:
        print(f"❌ Error creating tables: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
