import asyncio
import os
import sys
from dotenv import load_dotenv

# STEP 1: Set up the Python path for imports
# ------------------------------------------
# Add the 'Backend' directory to the system path so we can import from the 'app' module.
backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'Backend'))
sys.path.append(backend_dir)

# STEP 2: Load environment variables
# ----------------------------------
# Load the .env file from the project root to get the DATABASE_URL.
project_root = os.path.dirname(backend_dir)
load_dotenv(os.path.join(project_root, ".env"))
print(" Environment loaded.")

# STEP 3: Import application modules (NOW that path and env are set)
# -----------------------------------------------------------------
# This is the corrected import path, as you rightly pointed out.
from app.services.database import engine, Base

# Import all models so SQLAlchemy knows about them and can create the tables.
from app.models.user import User
from app.models.artist import Artist
from app.models.collection import Collection
from app.models.release import Release
from app.models.track import Track
# The track_artist association table is created because it's linked in the Track and Artist models.
print(" Application modules imported successfully.")

# --- Main Table Creation Logic ---
async def create_all_tables():
    """Connects to the database and creates all tables for the imported models."""
    print("\nConnecting to the database to create tables...")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print(" All tables created successfully!")
    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(create_all_tables())