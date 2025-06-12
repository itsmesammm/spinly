from pydantic import BaseModel
from typing import Optional

class ArtistBase(BaseModel):
    name: str
    discogs_id: Optional[int] = None

class ArtistCreate(ArtistBase):
    pass

class ArtistResponse(ArtistBase): # Named to match the import in release.py
    id: int

    class Config:
        from_attributes = True
