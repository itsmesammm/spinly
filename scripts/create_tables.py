import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'Backend')))

import asyncio
from app.services.database import engine, Base

async def create_tables():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("✅ Tables created successfully!")

if __name__ == "__main__":
    asyncio.run(create_tables())