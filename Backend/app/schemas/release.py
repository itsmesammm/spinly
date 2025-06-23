# In app/schemas/release.py
from pydantic import BaseModel, ConfigDict
from typing import Optional, List
from .artist import ArtistResponse # Import artist schema
from .track import TrackResponse   # Import track schema

class ReleaseBase(BaseModel):
    title: str
    year: Optional[int] = None
    label: Optional[str] = None
    styles: List[str] = []

class ReleaseCreate(ReleaseBase):
    # We will handle artist linking via ID in the service, not directly in the API create call
    pass

class ReleaseResponse(ReleaseBase):
    id: int
    discogs_id: Optional[int] = None
    
    # These will automatically include the nested objects in the API response
    artist: Optional[ArtistResponse] = None
    tracks: List[TrackResponse] = []
    
    model_config = ConfigDict(from_attributes=True)