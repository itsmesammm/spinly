import uuid
from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.services.job_service import JobService
from app.schemas.background_job import Job
from app.schemas.recommendations import RecommendationResponse, SimpleTrackRecommendation
from app.services.database import get_db
from app.models.background_job import JobStatus
from app.models.track import Track


router = APIRouter()

@router.get("/{job_id}", response_model=Job)
async def get_job_status(
    job_id: uuid.UUID,
    db: AsyncSession = Depends(get_db)
):
    """
    Retrieve the status and result of a background job.
    """
    job_service = JobService(db)
    job = await job_service.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.get("/{job_id}/result", response_model=RecommendationResponse)
async def get_job_result_as_tracklist(
    job_id: uuid.UUID,
    db: AsyncSession = Depends(get_db)
):
    """
    Retrieve the formatted result of a completed recommendation job.
    """
    job_service = JobService(db)
    job = await job_service.get_job(job_id)

    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")

    if job.status != JobStatus.COMPLETED:
        raise HTTPException(
            status_code=422, 
            detail=f"Job is not complete. Current status: {job.status}."
        )

    if not job.result or "track_ids" not in job.result:
        raise HTTPException(
            status_code=404, 
            detail="Job completed but no track IDs were found in the result."
        )

    track_ids = job.result["track_ids"]
    if not track_ids:
        return RecommendationResponse(recommendations=[])

    # Fetch all recommended tracks from the database in one query
    query = (
        select(Track)
        .where(Track.id.in_(track_ids))
        .options(selectinload(Track.artists), selectinload(Track.release))
    )
    result = await db.execute(query)
    similar_tracks = result.scalars().all()

    # Sort the tracks to maintain the order from the recommendation service if needed
    # This simple sort assumes the IDs were stored in order. For more complex sorting,
    # the result object from the job would need to include scores or order info.
    track_map = {track.id: track for track in similar_tracks}
    ordered_tracks = [track_map[track_id] for track_id in track_ids if track_id in track_map]

    # Transform the full track objects into the simplified response model
    formatted_recommendations = [
        SimpleTrackRecommendation(
            track_id=track.id,
            title=track.title,
            artist_name=track.artists[0].name if track.artists else "Unknown Artist",
            discogs_release_id=track.release.discogs_id if track.release else 0,
        )
        for track in ordered_tracks
    ]

    return RecommendationResponse(recommendations=formatted_recommendations)
