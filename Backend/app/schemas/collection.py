from pydantic import BaseModel
from typing import Optional
from uuid import UUID

class CollectionBase(BaseModel):
    name: str

class CollectionCreate(CollectionBase):
    pass  # No additional fields needed for creation

class CollectionUpdate(BaseModel):
    name: Optional[str] = None

class CollectionResponse(CollectionBase):
    id: UUID
    user_id: UUID

    class Config:
        from_attributes = True  # Allows Pydantic to convert SQLAlchemy models to JSON