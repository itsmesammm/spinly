import logging
from typing import List
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.release import Release
from app.services.discogs import DiscogsService
from app.services.discogs_manager import get_or_create_release

logger = logging.getLogger(__name__)

async def calculate_release_similarity(base_release: Release, target_release: Release) -> float:
    """
    Calculates a similarity score between two releases based on weighted matches
    of Style, Label, Year, and Artist.
    """
    score = 0.0

    # Define your weights based on your proposed order of relevance
    # Higher number means higher importance
    WEIGHT_STYLE = 4.0
    WEIGHT_LABEL = 3.0
    WEIGHT_YEAR = 2.0
    WEIGHT_ARTIST = 1.0

    # 1. Styles (most relevant)
    # Compare common styles. The more styles in common, the higher the score.
    if base_release.styles and target_release.styles:
        # Convert lists to sets for efficient intersection
        base_styles_set = set(s.lower() for s in base_release.styles)
        target_styles_set = set(s.lower() for s in target_release.styles)

        common_styles = len(base_styles_set.intersection(target_styles_set))

        # You could normalize this by the number of styles in the base release
        # For simplicity, let's just add common_styles * WEIGHT_STYLE
        score += common_styles * WEIGHT_STYLE

    # 2. Label
    if base_release.label and target_release.label and \
            base_release.label.lower() == target_release.label.lower():
        score += WEIGHT_LABEL

    # 3. Year
    if base_release.year is not None and target_release.year is not None:
        year_diff = abs(base_release.year - target_release.year)
        # Closer years get a higher contribution.
        # Example: 0 diff -> +WEIGHT_YEAR, 1 year diff -> +WEIGHT_YEAR * 0.5, etc.
        # Using a simple inverse relationship: 1 / (1 + difference)
        score += (1 / (1 + year_diff)) * WEIGHT_YEAR

    # 4. Artist (least relevant for 'similar' if not the same artist)
    if base_release.artist and target_release.artist and \
            base_release.artist.lower() == target_release.artist.lower():
        score += WEIGHT_ARTIST

    return score


async def find_similar_releases_on_discogs(base_release: Release, discogs_service: DiscogsService, 
                                          db: AsyncSession, limit: int = 5) -> List[Release]:
    """
    Find similar releases on Discogs API based on the base release's styles and artist.
    Fetches the releases from Discogs and stores them in our database.
    
    Args:
        base_release: The release to find similar releases for
        discogs_service: The Discogs API service
        db: Database session
        limit: Maximum number of similar releases to return
        
    Returns:
        List of Release objects that were fetched from Discogs and stored in our database
    """
    logger.info(f"Finding similar releases on Discogs for {base_release.title} by {base_release.artist}")
    
    similar_releases = []
    
    # Strategy 1: Search by style + artist
    if base_release.styles and len(base_release.styles) > 0:
        primary_style = base_release.styles[0]
        search_query = f"{primary_style} {base_release.artist}"
        
        try:
            logger.info(f"Searching Discogs with query: {search_query}")
            search_results = await discogs_service.search_releases(search_query)
            
            # Process results
            if "results" in search_results and len(search_results["results"]) > 0:
                logger.info(f"Found {len(search_results['results'])} results from Discogs")
                
                # Process each result, but limit to avoid too many API calls
                for result in search_results["results"][:limit*2]:  # Fetch more than needed in case some fail
                    if len(similar_releases) >= limit:
                        break
                        
                    # Extract the Discogs ID from the resource URL
                    if "id" in result:
                        discogs_id = result["id"]
                        
                        # Skip if it's the same as our base release
                        if discogs_id == base_release.discogs_id:
                            continue
                            
                        try:
                            # Get or create the release in our database
                            release = await get_or_create_release(discogs_id, db)
                            if release and release.id != base_release.id:
                                similar_releases.append(release)
                                logger.debug(f"Added similar release: {release.title} by {release.artist}")
                        except Exception as e:
                            logger.error(f"Error fetching release {discogs_id} from Discogs: {str(e)}")
                            continue
        except Exception as e:
            logger.error(f"Error searching Discogs: {str(e)}")
    
    # Strategy 2: If we don't have enough results, try searching by label
    if len(similar_releases) < limit and base_release.label:
        try:
            search_query = f"label:\"{base_release.label}\""  # Search by exact label
            
            logger.info(f"Searching Discogs by label: {search_query}")
            search_results = await discogs_service.search_releases(search_query)
            
            # Process results
            if "results" in search_results and len(search_results["results"]) > 0:
                logger.info(f"Found {len(search_results['results'])} results from Discogs by label")
                
                for result in search_results["results"][:limit*2]:
                    if len(similar_releases) >= limit:
                        break
                        
                    # Extract the Discogs ID
                    if "id" in result:
                        discogs_id = result["id"]
                        
                        # Skip if it's the same as our base release or already in our results
                        if discogs_id == base_release.discogs_id or any(r.discogs_id == discogs_id for r in similar_releases):
                            continue
                            
                        try:
                            # Get or create the release in our database
                            release = await get_or_create_release(discogs_id, db)
                            if release and release.id != base_release.id:
                                similar_releases.append(release)
                                logger.debug(f"Added similar release by label: {release.title} by {release.artist}")
                        except Exception as e:
                            logger.error(f"Error fetching release {discogs_id} from Discogs: {str(e)}")
                            continue
        except Exception as e:
            logger.error(f"Error searching Discogs by label: {str(e)}")