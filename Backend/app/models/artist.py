from sqlalchemy import Column, String, Integer

from app.services.database import Base

class Artist(Base):
    __tablename__ = "artists"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String(255), unique=True, nullable=False)
    discogs_id = Column(Integer, unique=True, nullable=True)