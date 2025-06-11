from sqlalchemy import Column, String, Integer, ForeignKey
from sqlalchemy.orm import relationship
from app.services.database import Base
from app.models.track_artist import track_artist_association

class Track(Base):
    __tablename__ = "tracks"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    position = Column(String, nullable=True)
    duration = Column(String, nullable=True)
    youtube_url = Column(String, nullable=True)

    # Link to its parent release
    release_id = Column(Integer, ForeignKey("releases.id"), nullable=False, index=True)
    release = relationship("Release", back_populates="tracks")

    # A track can have many artists (many-to-many relationship)
    artists = relationship(
        "Artist", 
        secondary=track_artist_association, 
        back_populates="tracks"
    )