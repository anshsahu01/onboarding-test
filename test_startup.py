"""
Quick test to see if the app can start and if endpoints are registered.
"""
import sys
import asyncio

# FORCE WINDOWS TO USE THE CORRECT EVENT LOOP
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

print("=" * 60)
print("TESTING APP STARTUP")
print("=" * 60)

try:
    print("\n1. Importing FastAPI...")
    from fastapi import FastAPI
    print("   [OK] FastAPI imported")

    print("\n2. Importing main app...")
    from main import app
    print("   [OK] Main app imported")

    print("\n3. Checking registered routes...")
    for route in app.routes:
        if hasattr(route, 'path') and hasattr(route, 'methods'):
            print(f"   - {route.methods} {route.path}")

    print("\n4. Checking if start endpoint exists...")
    start_routes = [r for r in app.routes if hasattr(r, 'path') and '/api/onboarding/start' in r.path]
    if start_routes:
        print(f"   [OK] Found /api/onboarding/start endpoint")
    else:
        print(f"   [ERROR] /api/onboarding/start endpoint NOT FOUND!")

    print("\n5. Testing database connection...")
    from app.db import engine
    from sqlalchemy import text

    async def test_db():
        try:
            async with engine.connect() as conn:
                result = await conn.execute(text("SELECT 1"))
                print(f"   [OK] Database connection successful: {result.scalar()}")
        except Exception as e:
            print(f"   [ERROR] Database connection failed: {e}")

    asyncio.run(test_db())

    print("\n" + "=" * 60)
    print("ALL CHECKS PASSED - App should work!")
    print("=" * 60)

except Exception as e:
    print(f"\n[ERROR] {type(e).__name__}: {str(e)}")
    import traceback
    traceback.print_exc()
