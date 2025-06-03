from pydantic import BaseModel, ConfigDict
from typing import Optional, List

class ReleaseBase(BaseModel):
    title: str
    artist: str
    styles: List[str]
    year: Optional[int] = None
    label: Optional[str] = None

class ReleaseCreate(ReleaseBase):
    discogs_id: Optional[int] = None  # Optional for creation, as it might be fetched later

class ReleaseResponse(ReleaseBase):
    id: int  # Changed from UUID to int to match the database model
    discogs_id: Optional[int] = None
    
    model_config = ConfigDict(from_attributes=True)  # Updated Config syntax for Pydantic v2