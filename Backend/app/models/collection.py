from sqlalchemy import Column, String, ForeignKey, Boolean
from sqlalchemy.orm import relationship
from app.models.collection_track import collection_track
from sqlalchemy.dialects.postgresql import UUID
import uuid

from app.services.database import Base

class Collection(Base):
    __tablename__ = "collections"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, unique=True, nullable=False)
    name = Column(String(255), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    is_public = Column(Boolean, default=False, nullable=False)

    tracks = relationship(
        "Track",
        secondary=collection_track,
        back_populates="collections"
    )
