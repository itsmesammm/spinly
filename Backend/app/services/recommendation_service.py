import logging
from typing import List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from app.models.release import Release
from app.models.track import Track
from app.services.discogs import DiscogsService
from app.services.music_data_service import get_or_create_release_with_tracks
from app.core.exceptions import NotFoundException

logger = logging.getLogger(__name__)

async def calculate_release_similarity(base_release: Release, target_release: Release) -> float:
    """Calculates a similarity score between two releases."""
    score = 0.0
    WEIGHT_STYLE = 4.0
    WEIGHT_LABEL = 3.0
    WEIGHT_YEAR = 2.0
    WEIGHT_ARTIST = 5.0 # Increased artist weight now that we have a proper model

    # 1. Artist (most relevant)
    if base_release.artist_id and target_release.artist_id and \
       base_release.artist_id == target_release.artist_id:
        score += WEIGHT_ARTIST

    # 2. Styles
    if base_release.styles and target_release.styles:
        base_styles_set = set(s.lower() for s in base_release.styles)
        target_styles_set = set(s.lower() for s in target_release.styles)
        common_styles = len(base_styles_set.intersection(target_styles_set))
        score += common_styles * WEIGHT_STYLE

    # 3. Label
    if base_release.label and target_release.label and \
       base_release.label.lower() == target_release.label.lower():
        score += WEIGHT_LABEL

    # 4. Year
    if base_release.year and target_release.year:
        year_diff = abs(base_release.year - target_release.year)
        score += (1 / (1 + year_diff)) * WEIGHT_YEAR

    return score

async def find_base_release_discogs_id_for_track(
    track_title: str,
    artist_name: str | None,
    discogs_service: DiscogsService
) -> int:
    """Searches Discogs and returns the Discogs ID of the most relevant release for a track."""
    query_parts = [f'track:"{track_title}"']
    if artist_name:
        query_parts.append(f'artist:"{artist_name}"')
    
    query = " ".join(query_parts)
    logger.info(f"Searching Discogs with query: {query}")
    search_results = await discogs_service.search_releases(query=query)

    if search_results and search_results.get("results"):
        first_result = search_results["results"][0]
        if "id" in first_result:
            logger.info(f"Found potential base release on Discogs with ID: {first_result['id']}")
            return first_result["id"]
            
    raise NotFoundException(f"Could not find a release for track '{track_title}'")

async def get_track_recommendations(
    db: AsyncSession,
    discogs_service: DiscogsService,
    track_title: str,
    artist_name: str | None,
    limit: int = 5
) -> List[Track]:
    """The main service function to generate track recommendations from a track title."""
    # 1. Find the base release on Discogs
    base_release_discogs_id = await find_base_release_discogs_id_for_track(
        track_title, artist_name, discogs_service
    )

    # 2. Get or create this base release (and its tracks) in our DB
    base_release = await get_or_create_release_with_tracks(base_release_discogs_id, db, discogs_service)
    if not base_release:
        raise Exception("Failed to process the base release.")

    # 3. Find similar releases and get their tracks
    # This combines the logic from your old `get_similar_releases` endpoint
    all_db_releases = (await db.execute(
        select(Release).options(selectinload(Release.tracks))
    )).scalars().all()

    db_similarities = []
    for target_release in all_db_releases:
        if base_release.id == target_release.id:
            continue
        score = await calculate_release_similarity(base_release, target_release)
        # For now, let's set a low minimum score to get some results
        if score > 0.1: 
            db_similarities.append({"release": target_release, "score": score})

    # You can add the logic to fetch more from Discogs here if needed, like in your old endpoint
    
    db_similarities.sort(key=lambda x: x["score"], reverse=True)

    # 4. Collect tracks from the top similar releases
    recommended_tracks: List[Track] = []
    for sim_item in db_similarities[:limit]:
        similar_release: Release = sim_item["release"]
        if similar_release.tracks:
            recommended_tracks.extend(similar_release.tracks)
            
    return recommended_tracks