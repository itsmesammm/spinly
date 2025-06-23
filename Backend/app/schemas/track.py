from pydantic import BaseModel
from typing import Optional, List
from .artist import ArtistResponse # To represent artists associated with a track

class TrackBase(BaseModel):
    title: str
    position: Optional[str] = None
    youtube_url: Optional[str] = None

class TrackCreate(TrackBase):
    pass

class TrackResponse(TrackBase):
    id: int
    artists: List[ArtistResponse] = [] # A track can have multiple artists

    class Config:
        from_attributes = True # Pydantic V2 for orm_mode
