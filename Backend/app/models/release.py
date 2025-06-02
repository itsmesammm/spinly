from sqlalchemy import Column, Integer, String
from sqlalchemy.dialects.postgresql import ARRAY as PGARRAY
from app.services.database import Base

class Release(Base):
    __tablename__ = "releases"

    id = Column(Integer, primary_key=True, index=True)
    discogs_id = Column(Integer, unique=True, index=True)
    title = Column(String, nullable=False)
    artist = Column(String, nullable=False)
    styles = Column(PGARRAY(String), nullable=False, default=[]) 
    year = Column(Integer)
    label = Column(String)