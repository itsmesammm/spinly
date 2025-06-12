import logging
from typing import List
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.services.database import get_db
from app.services.discogs import DiscogsService, get_discogs_service
from app.services import recommendation_service, music_data_service
from app.schemas.recommendations import RecommendationResponse, TrackRecommendationResponse
from app.schemas.release import ReleaseResponse # For the old endpoint
from app.core.exceptions import NotFoundException

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Recommendations"]) # Prefix is handled in main.py

@router.get("/recommendations/from-track", response_model=RecommendationResponse)
async def get_recommendations_from_track_endpoint(
    track_title: str = Query(...),
    artist_name: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
    discogs_service: DiscogsService = Depends(get_discogs_service),
    limit_similar_releases: int = Query(5)
):
    """Generates a list of recommended tracks based on an input track title."""
    try:
        similar_tracks = await recommendation_service.get_track_recommendations(
            db=db, discogs_service=discogs_service, track_title=track_title,
            artist_name=artist_name, limit=limit_similar_releases
        )
        track_titles = [track.title for track in similar_tracks if track.title]
        return RecommendationResponse(recommendations=TrackRecommendationResponse(tracks=track_titles))
    except NotFoundException as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to get recommendations: {e}")
        raise HTTPException(status_code=500, detail="An internal error occurred.")

@router.get("/releases/{release_id}/similar", response_model=List[ReleaseResponse])
async def get_similar_releases_endpoint(
    release_id: int,
    db: AsyncSession = Depends(get_db),
    discogs_service: DiscogsService = Depends(get_discogs_service)
):
    """
    Finds and returns releases that are similar to a given release ID from our database.
    (This is a simplified version of your old endpoint for clarity).
    """
    base_release = await music_data_service.get_or_create_release_with_tracks(
        release_id, db, discogs_service
    )
    if not base_release:
        raise NotFoundException("Release", str(release_id))

    # The logic for finding and ranking similar releases could also be moved to recommendation_service
    # For now, we'll keep a simplified version here.
    all_releases = (await db.execute(select(Release))).scalars().all()
    
    similarities = []
    for target in all_releases:
        if base_release.id == target.id:
            continue
        score = await recommendation_service.calculate_release_similarity(base_release, target)
        if score > 0.1:
            similarities.append({"release": target, "score": score})
    
    similarities.sort(key=lambda x: x["score"], reverse=True)
    
    return [item["release"] for item in similarities[:10]]