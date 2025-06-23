from pydantic import BaseModel
from typing import Optional, List
from uuid import UUID
from .track import TrackResponse

class CollectionBase(BaseModel):
    name: str
    is_public: Optional[bool] = False

class CollectionCreate(CollectionBase):
    pass  # No additional fields needed for creation

class CollectionUpdate(BaseModel):
    name: Optional[str] = None
    is_public: Optional[bool] = None

class CollectionResponse(CollectionBase):
    id: UUID
    user_id: UUID
    tracks: List[TrackResponse] = []

    class Config:
        from_attributes = True  # Allows Pydantic to convert SQLAlchemy models to JSON