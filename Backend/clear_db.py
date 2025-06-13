import asyncio
import os
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

async def clear_database():
    """
    Connects to the database and drops music-related tables.
    This is useful for clearing out old data during development.
    """
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        print("Error: DATABASE_URL environment variable not set.")
        return

    # The DATABASE_URL from docker-compose is for a non-async driver.
    # We need to ensure it's compatible with asyncpg.
    if database_url.startswith("postgresql://"):
        database_url = database_url.replace("postgresql://", "postgresql+asyncpg://")

    print(f"Connecting to database...")
    engine = create_async_engine(database_url)

    async with engine.connect() as conn:
        print("Clearing music data tables (artists, releases, tracks, track_artist)...")
        # Using CASCADE to automatically drop dependent objects like foreign key constraints.
        # The order matters if not using CASCADE, but with it, it's more robust.
        await conn.execute(text("DROP TABLE IF EXISTS track_artist CASCADE"))
        await conn.execute(text("DROP TABLE IF EXISTS tracks CASCADE"))
        await conn.execute(text("DROP TABLE IF EXISTS releases CASCADE"))
        await conn.execute(text("DROP TABLE IF EXISTS artists CASCADE"))
        await conn.commit()
        print("Tables cleared successfully.")

    await engine.dispose()

if __name__ == "__main__":
    print("This script will permanently delete music data from your database.")
    confirm = input("Are you sure you want to continue? (y/n): ")
    if confirm.lower() == 'y':
        asyncio.run(clear_database())
    else:
        print("Operation cancelled.")
