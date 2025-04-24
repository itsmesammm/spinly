import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'Backend')))

import asyncio
from app.services.database import engine, Base

# Import all models to ensure they are registered with SQLAlchemy
from app.models.user import User
from app.models.artist import Artist
from app.models.collection import Collection
from app.models.release import Release
from app.models.track import Track

async def create_tables():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("✅ Tables created successfully!")

if __name__ == "__main__":
    asyncio.run(create_tables())