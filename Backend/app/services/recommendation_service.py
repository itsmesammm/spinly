import asyncio
import logging
from typing import List, Optional, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from app.models.release import Release
from app.models.track import Track
from app.services.discogs import DiscogsService
from app.services.music_data_service import get_or_create_release_with_tracks, get_all_releases_with_details
from app.core.exceptions import NotFoundException
from app.services.job_service import JobService
from app.schemas.background_job import JobUpdate
from app.models.background_job import JobStatus
import uuid
import time

logger = logging.getLogger(__name__)

# --- Recommendation Service Constants ---
# For Discogs search when finding *similar* releases (not the base release)
DISCOGS_SIMILAR_SEARCH_PAGES = 1
DISCOGS_SIMILAR_SEARCH_PER_PAGE = 50 # Discogs default is 50, max 100

# Minimum similarity score for a release to be considered a candidate for recommendations
MIN_SCORE_FOR_CANDIDACY = 0.7

# Default number of releases to fetch tracks from if not specified by the caller
DEFAULT_LIMIT_RELEASES_FOR_TRACK_COLLECTION = 10

# Weightings for similarity calculation (can be tuned)
WEIGHT_STYLE = 4.0
WEIGHT_LABEL = 2.5
WEIGHT_YEAR = 2.5
WEIGHT_ARTIST = 1.0
STYLE_COMPLETENESS_BONUS = 2.0 # Bonus for having all base styles

async def calculate_release_similarity(base_release: Release, target_release: Release) -> float:
    """Calculates a similarity score between two releases using weighted factors and Jaccard similarity for styles."""
    score = 0.0

    # 1. Styles (Jaccard Similarity)
    if base_release.styles and target_release.styles:
        base_styles_set = set(s.lower() for s in base_release.styles)
        target_styles_set = set(s.lower() for s in target_release.styles)
        intersection = len(base_styles_set.intersection(target_styles_set))
        union = len(base_styles_set.union(target_styles_set))
        if union > 0:
            jaccard_similarity = intersection / union
            score += jaccard_similarity * WEIGHT_STYLE

            # Add a bonus if all base styles are present in the target
            if base_styles_set.issubset(target_styles_set):
                score += STYLE_COMPLETENESS_BONUS

    # 2. Label
    if base_release.label and target_release.label and \
    base_release.label.lower() == target_release.label.lower():
        score += WEIGHT_LABEL

    # 3. Year
    if base_release.year and target_release.year:
        year_diff = abs(base_release.year - target_release.year)
        # Score diminishes as the year difference increases. Capped at 10 years diff.
        year_score = max(0, 1 - (year_diff / 10.0))
        score += year_score * WEIGHT_YEAR

    # 4. Artist
    if base_release.artist_id and target_release.artist_id and \
       base_release.artist_id == target_release.artist_id:
        score += WEIGHT_ARTIST

    return score

async def find_base_release_discogs_id_for_track(
    track_title: str,
    artist_name: str | None,
    discogs_service: DiscogsService
) -> int:
    """Searches Discogs and returns the Discogs ID of the most relevant release for a track."""
    # Using a simpler query format. The 'field:"value"' syntax can be too strict.
    # A general query with just the keywords is often more effective for finding a base release.
    query_parts = [track_title]
    if artist_name:
        query_parts.append(artist_name)
    query = " ".join(query_parts)
    logger.info(f"Searching Discogs with query: {query}")
    search_results = await discogs_service.search_releases(query=query)

    if search_results and search_results.get("results"):
        first_result = search_results["results"][0]
        if "id" in first_result:
            logger.info(f"Found potential base release on Discogs with ID: {first_result['id']}")
            return first_result["id"]
            
    raise NotFoundException(resource="Discogs release for track", resource_id=track_title)

async def find_similar_releases_in_db(base_release: Release, db: AsyncSession, min_score_threshold: float) -> List[Tuple[Release, float]]:
    """Finds releases in the local DB similar to the base_release, with score > 0.6."""
    logger.info(f"LOCAL DB SEARCH: For releases similar to '{base_release.title}' (ID: {base_release.id}).")
    all_db_releases = await get_all_releases_with_details(db)

    similar_db_releases_with_scores: List[Tuple[Release, float]] = []
    for target_release in all_db_releases:
        # Exclude the base release itself from the comparison
        if target_release.id == base_release.id:
            continue


        score = await calculate_release_similarity(base_release, target_release)
        if score > min_score_threshold: 
            logger.debug(f"  Local DB: '{target_release.title}' (ID: {target_release.id}) similarity: {score:.2f}")
            similar_db_releases_with_scores.append((target_release, score))

    similar_db_releases_with_scores.sort(key=lambda x: x[1], reverse=True)

    logger.info(f"LOCAL DB SEARCH: Found {len(similar_db_releases_with_scores)} releases with score > {min_score_threshold}.")

    return similar_db_releases_with_scores

async def get_track_recommendations(
    db: AsyncSession,
    discogs_service: DiscogsService,
    track_title: str,
    artist_name: Optional[str] = None,
) -> List[Track]:
    """Generates track recommendations based on a seed track.
    Prioritizes Discogs for discovering similar releases, then enriches with local DB data."""
    logger.info(f"RECOMMENDATION PIPELINE for '{track_title}' by '{artist_name}': START")

    # STEP 1: Identify and fetch base release (unchanged)
    logger.info("STEP 1.1: Identifying Discogs ID for base release.")
    try:
        base_release_discogs_id = await find_base_release_discogs_id_for_track(
            track_title, artist_name, discogs_service
        )
    except NotFoundException:
        logger.warning(f"Could not find base release on Discogs for '{track_title}'. Aborting.")
        return []
    
    logger.info(f"STEP 1.2: Getting/creating base release (Discogs ID: {base_release_discogs_id}) in local DB.")
    base_release = await get_or_create_release_with_tracks(base_release_discogs_id, db, discogs_service)
    if not base_release:
        logger.error(f"Failed to get or create base_release with Discogs ID {base_release_discogs_id}. Aborting.")
        return []
    logger.info(f"  Base release: '{base_release.title}' (Local ID: {base_release.id}, Styles: {base_release.styles})")

    # --- Candidate Collection --- 
    # Using a dictionary keyed by local release.id to automatically handle de-duplication.
    # Stores (Release, score) tuples.
    all_candidates_map: dict[int, Tuple[Release, float]] = {}

    # STEP 2: Discogs Search for Similar Releases (Primary Source)
    logger.info("STEP 2: Querying Discogs for similar releases based on base release style(s).")
    raw_discogs_search_results = []
    if base_release.styles:
        # If a release has more than 3 styles, use only the first 3 to avoid an overly restrictive query.
        styles_to_query = base_release.styles
        if len(styles_to_query) > 3:
            logger.info(f"  Release has {len(styles_to_query)} styles. Using the first 3 for the Discogs query.")
            styles_to_query = styles_to_query[:3]

        style_queries = [f'style:"{style}"' for style in styles_to_query]
        
        # Combine all style queries for the search.
        # NOTE: Genre is intentionally omitted as Postman tests showed it overly restricts results.
        discogs_query = " ".join(style_queries)
        logger.info(f"  Discogs query: {discogs_query}")

        for page_num in range(1, DISCOGS_SIMILAR_SEARCH_PAGES + 1):
            try:
                search_page_data = await discogs_service.search_releases(
                    query=discogs_query, page=page_num, per_page=DISCOGS_SIMILAR_SEARCH_PER_PAGE
                )
                if search_page_data and search_page_data.get("results"):
                    raw_discogs_search_results.extend(search_page_data["results"])
                # Stop if no more pages indicated by Discogs
                if not (search_page_data and search_page_data.get("pagination", {}).get("urls", {}).get("next")):
                    break
            except Exception as e:
                logger.error(f"  Error fetching page {page_num} from Discogs: {e}", exc_info=False)
                break # Stop trying if a page fetch fails
        
        logger.info(f"  Found {len(raw_discogs_search_results)} raw candidate items from Discogs style search.")

        if raw_discogs_search_results:
            logger.info("Raw candidates from Discogs (before local DB check/processing):")
            for cand_data in raw_discogs_search_results:
                logger.info(f"  - Title: {cand_data.get('title')}, Discogs ID: {cand_data.get('id')}, Styles: {cand_data.get('style')}, Year: {cand_data.get('year')}, Label: {cand_data.get('label')}")

    # Process Discogs candidates: get/create them in local DB and calculate scores
        for raw_release_data in raw_discogs_search_results:
            discogs_id = raw_release_data.get("id")
            if not discogs_id or discogs_id == base_release.discogs_id:
                continue # Skip self or items without ID

            try:
                # This ensures the release is in our DB and details are loaded for scoring.
                release_obj = await get_or_create_release_with_tracks(discogs_id, db, discogs_service)
                if release_obj and release_obj.id not in all_candidates_map: # Check if already processed
                    score = await calculate_release_similarity(base_release, release_obj)
                    if score >= MIN_SCORE_FOR_CANDIDACY:
                        all_candidates_map[release_obj.id] = (release_obj, score)
                        logger.debug(f"    Added Discogs candidate '{release_obj.title}' (Local ID: {release_obj.id}), Score: {score:.2f}")
            except Exception as e:
                logger.warning(f"    Error processing Discogs candidate ID {discogs_id} (e.g. release details fetch failed): {e}", exc_info=False)

            # Add a delay to respect Discogs API rate limits (60/min -> ~1/sec)
            await asyncio.sleep(1.1)
    else:
        logger.warning("  Base release has no styles. Skipping Discogs style-based search for similar releases.")

    # STEP 3: Local DB Search for Additional/Enriching Similar Releases
    logger.info("STEP 3: Searching local DB for additional/enriching similar releases.")
    # find_similar_releases_in_db returns List[Tuple[Release, float]] already scored and filtered by its threshold.
    # We pass MIN_SCORE_FOR_CANDIDACY to ensure consistent filtering.
    local_db_candidates = await find_similar_releases_in_db(base_release, db, min_score_threshold=MIN_SCORE_FOR_CANDIDACY)
    
    logger.info(f"  Found {len(local_db_candidates)} candidates from local DB with score >= {MIN_SCORE_FOR_CANDIDACY}.")
    for rel_obj, score in local_db_candidates:
        if rel_obj.id not in all_candidates_map: # Add if not already present from Discogs search
            all_candidates_map[rel_obj.id] = (rel_obj, score)
            logger.debug(f"    Added Local DB candidate '{rel_obj.title}' (Local ID: {rel_obj.id}), Score: {score:.2f}")
        # If already present, the one from Discogs (potentially fresher) or first one encountered is kept.
        # Current map logic will keep the first one encountered if IDs are the same.

    # STEP 4: Consolidate, Sort, and Limit Final Candidates
    logger.info("STEP 4: Consolidating, sorting, and limiting final candidates.")
    consolidated_candidates_with_scores = list(all_candidates_map.values())
    
    # Sort all collected candidates by score
    consolidated_candidates_with_scores.sort(key=lambda item: item[1], reverse=True)
    
    # Limit to the number of releases requested for track collection
    top_releases_with_scores = consolidated_candidates_with_scores[:DEFAULT_LIMIT_RELEASES_FOR_TRACK_COLLECTION]
    logger.info(f"  Limiting to top {len(top_releases_with_scores)} of {len(consolidated_candidates_with_scores)} candidates for track extraction.")

    # STEP 5: Collect and Eagerly Load Tracks from Final Releases
    logger.info(f"STEP 5: Collecting and eagerly loading tracks from top {len(top_releases_with_scores)} releases.")
    
    if not top_releases_with_scores:
        logger.info("  No top releases found, returning empty list of tracks.")
        return []

    top_release_ids = [rel.id for rel, score in top_releases_with_scores]
    
    # A single query to get all tracks from the top releases, with their artists and parent release loaded.
    # This is crucial for the API response schema to work correctly without N+1 queries.
    stmt = (
        select(Track)
        .where(Track.release_id.in_(top_release_ids))
        .options(
            selectinload(Track.artists), # Eagerly load the artists for each track
            selectinload(Track.release)  # Eagerly load the parent release for each track
        )
    )
    
    result = await db.execute(stmt)
    recommended_tracks = result.scalars().all()
    
    logger.info(f"RECOMMENDATION PIPELINE: END. Collected {len(recommended_tracks)} tracks from {len(top_releases_with_scores)} releases.")
    return recommended_tracks


async def run_recommendation_pipeline_and_update_job(
    job_id: uuid.UUID,
    db: AsyncSession,
    discogs_service: DiscogsService,
    track_title: str,
    artist_name: Optional[str],
):
    """Runs the full recommendation pipeline and updates the job status and result."""
    job_service = JobService(db)
    logger.info(f"[Job ID: {job_id}] Starting recommendation pipeline.")
    start_time = time.time()

    await job_service.update_job(job_id, JobUpdate(status=JobStatus.RUNNING))

    try:
        recommended_tracks = await get_track_recommendations(
            db=db,
            discogs_service=discogs_service,
            track_title=track_title,
            artist_name=artist_name,
        )

        track_ids = [track.id for track in recommended_tracks]
        duration = time.time() - start_time
        logger.info(f"[Job ID: {job_id}] Pipeline completed successfully in {duration:.2f}s. Found {len(track_ids)} tracks.")
        
        await job_service.update_job(
            job_id,
            JobUpdate(
                status=JobStatus.COMPLETED,
                result={"track_ids": track_ids},
                duration_s=duration
            )
        )

    except Exception as e:
        duration = time.time() - start_time
        error_message = f"An unexpected error occurred: {str(e)}"
        logger.error(f"[Job ID: {job_id}] Pipeline failed after {duration:.2f}s. Error: {error_message}", exc_info=True)
        await job_service.update_job(
            job_id,
            JobUpdate(
                status=JobStatus.FAILED,
                result={"error": error_message},
                duration_s=duration
            )
        )