from pydantic import BaseModel
from typing import List

class TrackRecommendationResponse(BaseModel):
    tracks: List[str]

class RecommendationResponse(BaseModel):
    recommendations: TrackRecommendationResponse