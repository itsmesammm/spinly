from app.services.database import engine, Base

# dont import yet till check the xml files from discogs
from app.models.artist import Artist
from app.models.track import Track
from app.models.user import User
from app.models.collection import Collection

print("Creating database tables...")
Base.metadata.create_all(bind=engine)
print("Tables created successfully!")
