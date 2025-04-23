import asyncio
from app.services.database import engine

async def test_connection():
    try:
        async with engine.begin() as conn:
            await conn.run_sync(lambda x: print("Database connection successful!"))
    except Exception as e:
        print(f"Database connection failed: {str(e)}")

asyncio.run(test_connection())