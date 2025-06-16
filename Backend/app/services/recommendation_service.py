import asyncio
import logging
from typing import List, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from app.models.release import Release
from app.models.track import Track
from app.services.discogs import DiscogsService
from app.services.music_data_service import get_or_create_release_with_tracks, get_all_releases_with_details
from app.core.exceptions import NotFoundException

logger = logging.getLogger(__name__)

# --- Recommendation Service Constants ---
# For Discogs search when finding *similar* releases (not the base release)
DISCOGS_SIMILAR_SEARCH_PAGES = 1
DISCOGS_SIMILAR_SEARCH_PER_PAGE = 50 # Discogs default is 50, max 100

# Minimum similarity score for a release to be considered a candidate for recommendations
MIN_SCORE_FOR_CANDIDACY = 0.6

# Default number of releases to fetch tracks from if not specified by the caller
DEFAULT_LIMIT_RELEASES_FOR_TRACK_COLLECTION = 10

# Weightings for similarity calculation (can be tuned)
WEIGHT_STYLE = 4.0
WEIGHT_LABEL = 2.0
WEIGHT_YEAR = 1.0
WEIGHT_ARTIST = 3.0

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
        if target_release.id == base_release.id: # Prevent self-comparison
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
    artist_name: str | None,
    limit: int = DEFAULT_LIMIT_RELEASES_FOR_TRACK_COLLECTION
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
        # Use all styles from the base release for a more specific search
        style_queries = [f'style:"{style}"' for style in base_release.styles]
        
        # Combine all style queries with a fallback genre
        discogs_query = " ".join(style_queries) + ' genre:"Electronic"'
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

        for raw_release_data in raw_discogs_search_results:
            discogs_id = raw_release_data.get("id")
            if not discogs_id or discogs_id == base_release.discogs_id:
                continue # Skip self or items without ID

            try:
                # This ensures the release is in our DB and details are loaded for scoring.
                release_obj = await get_or_create_release_with_tracks(discogs_id, db, discogs_service)
                if release_obj and release_obj.id not in all_candidates_map: # Check if already processed (e.g., from local DB first if order changed)
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
    top_releases_with_scores = consolidated_candidates_with_scores[:limit]
    logger.info(f"  Selected top {len(top_releases_with_scores)} releases from {len(consolidated_candidates_with_scores)} candidates (limit: {limit}).")

    # STEP 5: Collect Tracks (Unchanged from current logic)
    recommended_tracks: List[Track] = []
    logger.info(f"STEP 5: Collecting tracks from top {len(top_releases_with_scores)} releases.")
    for rel_obj, score in top_releases_with_scores:
        if not rel_obj.tracks:
            # This might happen if tracks weren't loaded, e.g., if get_or_create_release_with_tracks had an issue
            # or if the release genuinely has no tracks listed on Discogs.
            logger.warning(f"  Release '{rel_obj.title}' (ID: {rel_obj.id}) has no tracks loaded or available. Skipping.")
            # Attempt to reload tracks if they are missing and should be there
            # stmt = select(Release).where(Release.id == rel_obj.id).options(selectinload(Release.tracks).selectinload(Track.artists), selectinload(Release.artist))
            # fresh_rel_obj_result = await db.execute(stmt)
            # fresh_rel_obj = fresh_rel_obj_result.scalar_one_or_none()
            # if fresh_rel_obj and fresh_rel_obj.tracks:
            #    rel_obj = fresh_rel_obj # Use the freshly loaded object
            # else:
            #    continue # Still no tracks, skip
            continue

        logger.debug(f"  Adding {len(rel_obj.tracks)} tracks from '{rel_obj.title}' (Score: {score:.2f}, DB ID: {rel_obj.id}, Discogs ID: {rel_obj.discogs_id})")
        for track_to_add in rel_obj.tracks:
            recommended_tracks.append(track_to_add)
            
    logger.info(f"RECOMMENDATION PIPELINE: END. Collected {len(recommended_tracks)} tracks from {len(top_releases_with_scores)} releases.")
    return recommended_tracks