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

async def calculate_release_similarity(base_release: Release, target_release: Release) -> float:
    """Calculates a similarity score between two releases using weighted factors and Jaccard similarity for styles."""
    score = 0.0
    WEIGHT_STYLE = 4.0  # Normalized, so can be weighted higher
    WEIGHT_LABEL = 2.0
    WEIGHT_YEAR = 1.0
    WEIGHT_ARTIST = 3.0

    # 1. Artist
    if base_release.artist_id and target_release.artist_id and \
       base_release.artist_id == target_release.artist_id:
        score += WEIGHT_ARTIST

    # 2. Styles (Jaccard Similarity)
    if base_release.styles and target_release.styles:
        base_styles_set = set(s.lower() for s in base_release.styles)
        target_styles_set = set(s.lower() for s in target_release.styles)
        intersection = len(base_styles_set.intersection(target_styles_set))
        union = len(base_styles_set.union(target_styles_set))
        if union > 0:
            jaccard_similarity = intersection / union
            score += jaccard_similarity * WEIGHT_STYLE

    # 3. Label
    if base_release.label and target_release.label and \
       base_release.label.lower() == target_release.label.lower():
        score += WEIGHT_LABEL

    # 4. Year
    if base_release.year and target_release.year:
        year_diff = abs(base_release.year - target_release.year)
        # Score diminishes as the year difference increases. Capped at 10 years diff.
        year_score = max(0, 1 - (year_diff / 10.0))
        score += year_score * WEIGHT_YEAR

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
    limit: int = 10 # Default to 10 releases for track collection
) -> List[Track]:
    """Generates track recommendations based on a seed track, prioritizing local DB then Discogs."""
    logger.info(f"RECOMMENDATION PIPELINE for '{track_title}' by '{artist_name}': START")
    
    # STEP 1: Base Release Identification
    logger.info("Step 1.1: Identifying Discogs ID for base release.")
    base_release_discogs_id = await find_base_release_discogs_id_for_track(track_title, artist_name, discogs_service)
    logger.info(f"Step 1.2: Getting/creating base release (Discogs ID: {base_release_discogs_id}) in local DB.")
    base_release = await get_or_create_release_with_tracks(discogs_release_id=base_release_discogs_id, db=db, discogs_service=discogs_service)
    if not base_release:
        logger.error("Failed to get or create the base release. Cannot continue.")
        raise Exception("Base release processing failed.")
    logger.info(f"Base release: '{base_release.title}' (Local ID: {base_release.id}, Styles: {base_release.styles})")

    # STEP 2: Local DB Search
    min_score_threshold = 0.6  # Standard threshold for local DB search
    MIN_SIMILARITY_FOR_DISCOGS_RESULTS = 0.6  # Threshold for filtering Discogs results after fetching
    all_candidate_releases_with_scores = await find_similar_releases_in_db(base_release, db, min_score_threshold)

    # STEP 3: Discogs Search (if needed)
    if len(all_candidate_releases_with_scores) < limit:
        needed_from_discogs = limit - len(all_candidate_releases_with_scores)
        logger.info(f"DISCOGS SEARCH: Local DB yielded {len(all_candidate_releases_with_scores)} candidates. Need {needed_from_discogs} more. Querying Discogs.")
        
        primary_style_for_search = base_release.styles[0] if base_release.styles else None
        if not primary_style_for_search:
            logger.warning("DISCOGS SEARCH: Base release has no styles. Skipping Discogs style-based search.")
        else:
            discogs_query = f'style:"{primary_style_for_search}" genre:"Electronic"'
            logger.info(f"DISCOGS SEARCH: Querying with: {discogs_query}")
            try:
                potential_discogs_candidates = []
                discogs_search_page_1 = await discogs_service.search_releases(query=discogs_query, page=1, per_page=50)
                if discogs_search_page_1 and discogs_search_page_1.get("results"):
                    potential_discogs_candidates.extend(discogs_search_page_1["results"])
                    pagination_info = discogs_search_page_1.get("pagination", {})
                    total_pages = pagination_info.get("pages", 1)
                    if total_pages > 1:
                        discogs_search_page_2 = await discogs_service.search_releases(query=discogs_query, page=2, per_page=50)
                        if discogs_search_page_2 and discogs_search_page_2.get("results"):
                            potential_discogs_candidates.extend(discogs_search_page_2["results"])

                logger.info(f"DISCOGS SEARCH: Got {len(potential_discogs_candidates)} potential candidates from Discogs search.")
                discogs_sourced_count = 0
                for potential_release_data in potential_discogs_candidates:
                    if len(all_candidate_releases_with_scores) >= limit:
                        break
                    potential_discogs_id = potential_release_data.get("id")
                    if not potential_discogs_id or any(r.discogs_id == potential_discogs_id for r, s in all_candidate_releases_with_scores):
                        continue
                    
                    new_discogs_release = await get_or_create_release_with_tracks(potential_discogs_id, db, discogs_service)
                    if new_discogs_release:
                        score = await calculate_release_similarity(base_release, new_discogs_release)
                        if score >= MIN_SIMILARITY_FOR_DISCOGS_RESULTS:
                            all_candidate_releases_with_scores.append((new_discogs_release, score))
                            discogs_sourced_count += 1
                logger.info(f"DISCOGS SEARCH: Added {discogs_sourced_count} new releases from Discogs.")
            except Exception as e:
                logger.error(f"DISCOGS SEARCH: Error during Discogs search or processing: {e}", exc_info=True)
    else:
        logger.info("DISCOGS SEARCH: Not needed. Local DB provided enough candidates.")

    # STEP 4: Sort and Limit
    all_candidate_releases_with_scores.sort(key=lambda item: item[1], reverse=True)
    logger.info(f"FINAL SORT: Total {len(all_candidate_releases_with_scores)} candidates sorted.")
    top_releases_with_scores = all_candidate_releases_with_scores[:limit]

    # STEP 5: Collect Tracks
    recommended_tracks: List[Track] = []
    logger.info(f"TRACK COLLECTION: Collecting tracks from top {len(top_releases_with_scores)} releases.")
    for rel_obj, score in top_releases_with_scores:
        if not rel_obj.tracks:
            logger.warning(f"Release '{rel_obj.title}' (ID: {rel_obj.id}) has no tracks loaded.")
            continue
        logger.debug(f"  Adding {len(rel_obj.tracks)} tracks from '{rel_obj.title}' (Score: {score:.2f}, DB ID: {rel_obj.id}, Discogs ID: {rel_obj.discogs_id})")
        for track_to_add in rel_obj.tracks:
            recommended_tracks.append(track_to_add)
            
    logger.info(f"RECOMMENDATION PIPELINE: END. Collected {len(recommended_tracks)} tracks from {len(top_releases_with_scores)} releases.")
    return recommended_tracks