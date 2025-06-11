from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.dialects.postgresql import ARRAY as PGARRAY
from sqlalchemy.orm import relationship
from app.services.database import Base

class Release(Base):
    __tablename__ = "releases"

    id = Column(Integer, primary_key=True, index=True)
    discogs_id = Column(Integer, unique=True, index=True, nullable=False)
    title = Column(String, nullable=False) 
    year = Column(Integer)
    label = Column(String)
    styles = Column(PGARRAY(String), nullable=True, default=[])   

    # A release is linked to one primary artist
    artist_id = Column(Integer, ForeignKey("artists.id"), nullable=True)
    artist = relationship("Artist", back_populates="releases")

    # A release has many tracks
    tracks = relationship("Track", back_populates="release", cascade="all, delete-orphan") 





    
