from pydantic import BaseModel, ConfigDict
from typing import Optional, List
from .artist import ArtistResponse # To represent artists associated with a track

# A new, minimal schema to represent release info without causing circular imports
class ReleaseInfo(BaseModel):
    id: int
    discogs_id: Optional[int] = None
    title: str
    model_config = ConfigDict(from_attributes=True)

class TrackBase(BaseModel):
    title: str
    position: Optional[str] = None
    youtube_url: Optional[str] = None

class TrackCreate(TrackBase):
    pass

class TrackResponse(TrackBase):
    id: int
    artists: List[ArtistResponse] = [] # A track can have multiple artists
    release: Optional[ReleaseInfo] = None # Add release info

    model_config = ConfigDict(from_attributes=True)
