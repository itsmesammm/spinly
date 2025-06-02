from pydantic import BaseModel
from typing import Optional, List
from uuid import UUID

class ReleaseBase(BaseModel):
    title: str
    artist: str
    styles: List[str]
    year: Optional[int] = None
    label: Optional[str] = None

class ReleaseCreate(ReleaseBase):
    discogs_id: Optional[int] = None  # Optional for creation, as it might be fetched later

class ReleaseResponse(ReleaseBase):
    id: UUID
    discogs_id: Optional[int] = None

    class Config:
        from_attributes = True  # Allows Pydantic to convert SQLAlchemy models to JSON