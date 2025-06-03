from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from typing import List

from app.services.database import get_db
from app.models.release import Release
from app.schemas.release import ReleaseResponse  # Re-use your existing schema
from app.core.exceptions import NotFoundException

# Import your new similarity logic
from app.services.similarity import calculate_release_similarity
from app.services.discogs_manager import get_or_create_release  # To ensure base release exists

router = APIRouter()


@router.get("/releases/{base_release_id}/similar", response_model = List[ReleaseResponse])
async def get_similar_releases(
        base_release_id: int,
        db: AsyncSession = Depends(get_db),
        limit: int = 10,  # Optional: add a limit for the number of similar releases
        min_score: float = 0.5  # Optional: only return releases above a certain score
):
    # 1. Get the base release. Use get_or_create_release to ensure it exists in your DB.
    base_release = await get_or_create_release(base_release_id, db)
    if not base_release:
        raise NotFoundException("Release", str(base_release_id))

    # 2. Get all other releases from your database
    # For a large database, you might want to fetch only a subset or implement more advanced filtering.
    result = await db.execute(select(Release))
    all_releases = result.scalars().all()

    similarities = []
    for target_release in all_releases:
        # Don't compare a release to itself
        if base_release.id == target_release.id:
            continue

        # Calculate similarity score using your new function
        score = await calculate_release_similarity(base_release, target_release)

        # Only add if score meets a minimum threshold
        if score >= min_score:
            similarities.append({"release": target_release, "score": score})

    # 3. Sort by score in descending order
    similarities.sort(key = lambda x: x["score"], reverse = True)

    # 4. Return the top 'limit' similar releases
    return [s["release"] for s in similarities[:limit]]