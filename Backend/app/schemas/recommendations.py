from pydantic import BaseModel
from typing import List, Optional

# The new, clean response model for a single recommended track.
class SimpleTrackRecommendation(BaseModel):
    track_id: int
    title: str
    artist_name: str
    discogs_release_id: int

    class Config:
        orm_mode = True

# The main response model that contains a list of recommendations.
class RecommendationResponse(BaseModel):
    recommendations: List[SimpleTrackRecommendation]

# This schema is kept for other potential internal uses.
class SimilarRelease(BaseModel):
    id: int
    title: str
    artist: str
    year: Optional[int] = None
    score: float