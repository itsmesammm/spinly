from sqlalchemy import Column, Integer, String
from app.services.database import Base  # You already have Base imported this way

class Release(Base):
    __tablename__ = "releases"

    id = Column(Integer, primary_key=True, index=True)
    discogs_id = Column(Integer, unique=True, index=True)
    title = Column(String, nullable=False)
    artist = Column(String, nullable=False)
    style = Column(String, nullable=False)  # Adding style column as nullable since existing records won't have it