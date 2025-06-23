from sqlalchemy import Column, String, Integer
from sqlalchemy.orm import relationship
from app.models.track_artist import track_artist # For the many-to-many relationship

from app.services.database import Base

class Artist(Base):
    __tablename__ = "artists"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String(255), unique=True, nullable=False)
    discogs_id = Column(Integer, unique=True, nullable=True)

    # An artist can have many tracks (many-to-many relationship)
    tracks = relationship("Track", secondary=track_artist, back_populates="artists")

    # An artist can have many releases (one-to-many relationship)
    releases = relationship("Release", back_populates="artist")