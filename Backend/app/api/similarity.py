import logging
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from typing import List

from app.services.database import get_db
from app.models.release import Release
from app.schemas.release import ReleaseResponse  # Re-use your existing schema
from app.core.exceptions import NotFoundException

# Import your similarity logic
from app.services.similarity import calculate_release_similarity, find_similar_releases_on_discogs
from app.services.discogs_manager import get_or_create_release  # To ensure base release exists
from app.services.discogs import DiscogsService

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/releases/{base_release_id}/similar", response_model=List[ReleaseResponse])
async def get_similar_releases(
        base_release_id: int,
        db: AsyncSession = Depends(get_db),
        discogs_service: DiscogsService = Depends(),
        limit: int = 10,  # Maximum number of similar releases to return
        min_score: float = 0.5,  # Only return releases above this similarity score
        min_db_results: int = Query(3, description="Minimum number of database results before querying Discogs")
):
    logger.info(f"Finding similar releases for release_id={base_release_id}")
    
    # 1. Get the base release. Use get_or_create_release to ensure it exists in the DB.
    base_release = await get_or_create_release(base_release_id, db)
    if not base_release:
        logger.error(f"Release {base_release_id} not found")
        raise NotFoundException("Release", str(base_release_id))

    # 2. Get all other releases from the database
    result = await db.execute(select(Release))
    all_releases = result.scalars().all()
    logger.info(f"Found {len(all_releases)} total releases in database")

    # Calculate similarity for database releases
    db_similarities = []
    for target_release in all_releases:
        # Don't compare a release to itself
        if base_release.id == target_release.id:
            continue

        # Calculate similarity score using your function
        score = await calculate_release_similarity(base_release, target_release)

        # Only add if score meets a minimum threshold
        if score >= min_score:
            db_similarities.append({"release": target_release, "score": score})
    
    logger.info(f"Found {len(db_similarities)} similar releases in database with score >= {min_score}")
    
    # If we don't have enough results from the database, try Discogs API
    if len(db_similarities) < min_db_results:
        logger.info(f"Not enough similar releases in database, searching Discogs API")
        try:
            # Find similar releases on Discogs and add them to our database
            discogs_releases = await find_similar_releases_on_discogs(
                base_release=base_release,
                discogs_service=discogs_service,
                db=db,
                limit=limit - len(db_similarities)  # Only fetch what we need
            )
            
            logger.info(f"Found {len(discogs_releases)} similar releases from Discogs API")
            
            # Calculate similarity scores for the new releases
            for release in discogs_releases:
                score = await calculate_release_similarity(base_release, release)
                if score >= min_score:
                    db_similarities.append({"release": release, "score": score})
        except Exception as e:
            logger.error(f"Error fetching similar releases from Discogs: {str(e)}")
            # Continue with what we have from the database
    
    # Sort by score in descending order
    db_similarities.sort(key=lambda x: x["score"], reverse=True)
    
    # Return the top 'limit' similar releases
    similar_releases = [s["release"] for s in db_similarities[:limit]]
    logger.info(f"Returning {len(similar_releases)} similar releases")
    
    return similar_releases