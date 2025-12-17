"""Check if tables exist in database."""
import asyncio
from app.db import engine
from sqlalchemy import text


async def check_tables():
    """Check what tables exist in the database."""
    async with engine.connect() as conn:
        result = await conn.execute(
            text("SELECT table_name FROM information_schema.tables WHERE table_schema='public'")
        )
        tables = [row[0] for row in result]
        print("\n✅ Tables in database:")
        for table in tables:
            print(f"  - {table}")
        print()


if __name__ == "__main__":
    asyncio.run(check_tables())
