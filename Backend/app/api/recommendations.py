import logging
from typing import List
from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession

# Use correct, existing paths for dependencies
from app.services.database import get_db
from app.services.discogs import get_discogs_service, DiscogsService
from app.core.security import get_current_user_optional

# Imports for background job logic
from app.services import recommendation_service
from app.services.job_service import JobService
from app.schemas.background_job import Job, JobCreate
from app.models.user import User

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Recommendations"])  # Prefix is handled in main.py

@router.post("/recommendations/request", response_model=Job, status_code=202)
async def request_recommendations_from_track(
    background_tasks: BackgroundTasks,
    track_title: str = Query(...),
    artist_name: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
    discogs_service: DiscogsService = Depends(get_discogs_service),
    current_user: User | None = Depends(get_current_user_optional),
):
    """Accepts a recommendation request and starts a background job to process it."""
    job_service = JobService(db)

    job_create = JobCreate(
        job_type="track_recommendation",
        parameters={"track_title": track_title, "artist_name": artist_name},
        user_id=current_user.id if current_user else None
    )
    job = await job_service.create_job(job_create)

    # Add the long-running task to FastAPI's background runner
    background_tasks.add_task(
        recommendation_service.run_recommendation_pipeline_and_update_job,
        job_id=job.id,
        db=db,
        discogs_service=discogs_service,
        track_title=track_title,
        artist_name=artist_name
    )

    logger.info(f"Created and dispatched background job {job.id} for track '{track_title}'.")
    return job



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