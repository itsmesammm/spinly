from sqlalchemy import Column, String, Integer
from sqlalchemy.dialects.postgresql import UUID
import uuid

from app.services.database import Base

class Artist(Base):
    __tablename__ = "artists"

    id = Column(UUID(as_uuid = True), primary_key=True, default=uuid.uuid4, unique=True, nullable=False)
    name = Column(String(255), unique=True, nullable=False)
    discogs_id = Column(Integer, unique=True, nullable=True)