import logging
from typing import List, Tuple
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
    WEIGHT_STYLE = 5.0
    WEIGHT_LABEL = 4.0
    WEIGHT_YEAR = 3.0
    WEIGHT_ARTIST = 2.0 

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

async def find_similar_releases_in_db(
    db: AsyncSession,
    base_release: Release
) -> List[Tuple[Release, float]]: # Returns list of (Release, score) tuples, sorted by score
    """Finds releases in the local DB similar to the base_release, with score > 0.6."""
    logger.info(f"LOCAL DB SEARCH: For releases similar to '{base_release.title}' (ID: {base_release.id}).")
    all_db_releases_stmt = select(Release).options(
        selectinload(Release.tracks).selectinload(Track.artists),
        selectinload(Release.artist) # Eager load primary artist for all releases
    )
    result = await db.execute(all_db_releases_stmt)
    all_db_releases = result.scalars().unique().all()

    similar_db_releases_with_scores: List[Tuple[Release, float]] = []
    for target_release in all_db_releases:
        if target_release.id == base_release.id: # Prevent self-comparison
            continue

        score = await calculate_release_similarity(base_release, target_release)
        if score > 0.6:
            logger.debug(f"  Local DB: '{target_release.title}' (ID: {target_release.id}) similarity: {score:.2f}")
            similar_db_releases_with_scores.append((target_release, score))

    similar_db_releases_with_scores.sort(key=lambda item: item[1], reverse=True)
    logger.info(f"LOCAL DB SEARCH: Found {len(similar_db_releases_with_scores)} releases with score > 0.6.")
    return similar_db_releases_with_scores

async def get_track_recommendations(
    db: AsyncSession,
    discogs_service: DiscogsService,
    track_title: str,
    artist_name: str | None,
    limit: int = 10 # Default to 10 releases for track collection
) -> List[Track]:
    """Generates track recommendations based on a seed track, prioritizing local DB then Discogs."""
    # STEP 1: Base Release Identification
    logger.info(f"RECOMMENDATION PIPELINE for '{track_title}' by '{artist_name}': START")
    logger.info(f"Step 1.1: Identifying Discogs ID for base release.")
    base_release_discogs_id = await find_base_release_discogs_id_for_track(
        track_title, artist_name, discogs_service
    )
    logger.info(f"Step 1.2: Getting/creating base release (Discogs ID: {base_release_discogs_id}) in local DB.")
    base_release = await get_or_create_release_with_tracks(
        discogs_release_id=base_release_discogs_id, db=db, discogs_service=discogs_service
    )
    if not base_release:
        logger.error("Failed to get or create the base release. Cannot continue.")
        raise Exception("Base release processing failed.")
    logger.info(f"Base release: '{base_release.title}' (Local ID: {base_release.id}, Styles: {base_release.styles})")

    # STEP 2: Local DB Search
    db_similar_releases_with_scores = await find_similar_releases_in_db(db, base_release)
    
    all_candidate_releases_with_scores: List[Tuple[Release, float]] = list(db_similar_releases_with_scores)
    processed_discogs_ids = {base_release.discogs_id}
    for rel, _ in db_similar_releases_with_scores:
        if rel.discogs_id: # Ensure discogs_id is not None before adding
            processed_discogs_ids.add(rel.discogs_id)

    # STEP 3: Discogs Search (if needed)
    if len(all_candidate_releases_with_scores) < limit:
        needed_from_discogs = limit - len(all_candidate_releases_with_scores)
        logger.info(f"DISCOGS SEARCH: Local DB yielded {len(all_candidate_releases_with_scores)} candidates. Need {needed_from_discogs} more. Querying Discogs.")
        
        primary_style_for_search = None
        if base_release.styles and len(base_release.styles) > 0:
            primary_style_for_search = base_release.styles[0]
        
        if not primary_style_for_search:
            logger.warning("DISCOGS SEARCH: Base release has no styles. Skipping Discogs style-based search.")
        else:
            # The 'type:"release"' is handled by the discogs_service.search_releases method directly.
            discogs_query = f'style:"{primary_style_for_search}" genre:"Electronic"'
            logger.info(f"DISCOGS SEARCH: Querying with: {discogs_query}")
            try:
                # Fetching more results. Discogs default per_page is 50.
                # We'll request two pages to get up to 100 candidates.
                discogs_search_page_1 = await discogs_service.search_releases(query=discogs_query, page=1, per_page=50)
                discogs_search_page_2 = await discogs_service.search_releases(query=discogs_query, page=2, per_page=50)
                
                potential_discogs_candidates = []
                if discogs_search_page_1 and discogs_search_page_1.get("results"):
                    potential_discogs_candidates.extend(discogs_search_page_1["results"])
                if discogs_search_page_2 and discogs_search_page_2.get("results"):
                    potential_discogs_candidates.extend(discogs_search_page_2["results"])
                
                logger.info(f"DISCOGS SEARCH: Got {len(potential_discogs_candidates)} potential candidates from Discogs search.")
                discogs_sourced_count = 0
                for potential_release_data in potential_discogs_candidates:
                    if len(all_candidate_releases_with_scores) >= limit: # Check if we've met the overall limit of releases
                        break
                    
                    potential_discogs_id = potential_release_data.get("id")
                    if not potential_discogs_id or potential_discogs_id in processed_discogs_ids:
                        continue
                    
                    logger.debug(f"  Discogs candidate: '{potential_release_data.get('title')}' (ID: {potential_discogs_id}). Fetching details.")
                    new_discogs_release = await get_or_create_release_with_tracks(
                        discogs_release_id=potential_discogs_id, db=db, discogs_service=discogs_service
                    )
                    if new_discogs_release:
                        processed_discogs_ids.add(new_discogs_release.discogs_id)
                        score = await calculate_release_similarity(base_release, new_discogs_release)
                        logger.debug(f"    Discogs release '{new_discogs_release.title}' (Local ID: {new_discogs_release.id}) similarity: {score:.2f}")
                        if score > 0.6:
                            all_candidate_releases_with_scores.append((new_discogs_release, score))
                            discogs_sourced_count += 1
                logger.info(f"DISCOGS SEARCH: Added {discogs_sourced_count} new releases from Discogs with score > 0.6.")
            except Exception as e:
                logger.error(f"DISCOGS SEARCH: Error during Discogs search or processing: {e}", exc_info=True)
    else:
        logger.info("DISCOGS SEARCH: Not needed. Local DB provided enough candidates.")

    # STEP 4: Combine and Sort (already combined, just sort)
    all_candidate_releases_with_scores.sort(key=lambda item: item[1], reverse=True)
    logger.info(f"FINAL SORT: Total {len(all_candidate_releases_with_scores)} candidates sorted.")

    # STEP 5: Collect Tracks
    recommended_tracks: List[Track] = []
    final_selected_releases_count = 0
    logger.info(f"TRACK COLLECTION: Collecting tracks from top {limit} releases.")
    for rel_obj, score in all_candidate_releases_with_scores:
        if final_selected_releases_count >= limit:
            break
        if rel_obj.tracks:
            logger.debug(f"  Adding {len(rel_obj.tracks)} tracks from '{rel_obj.title}' (Score: {score:.2f}, DB ID: {rel_obj.id})")
            recommended_tracks.extend(rel_obj.tracks)
        final_selected_releases_count += 1
        
    logger.info(f"RECOMMENDATION PIPELINE: END. Collected {len(recommended_tracks)} tracks from {final_selected_releases_count} releases.")
    return recommended_tracks