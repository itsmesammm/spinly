import logging
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.services.database import get_db
from app.services.discogs_manager import get_or_create_release
from app.schemas.release import ReleaseResponse, ReleaseCreate
from app.core.exceptions import NotFoundException, DuplicateError
from typing import List, Dict
from sqlalchemy.future import select
from app.models.release import Release
from app.services.discogs import DiscogsService, get_discogs_service
from app.services import music_data_service


logger = logging.getLogger(__name__)


router = APIRouter()

# Static routes first
@router.get("/releases/search/")
async def search_releases(
    query: str,
    page: int = 1,
    discogs_service: DiscogsService = Depends(get_discogs_service)
) -> Dict:
    """Search for releases in Discogs database"""
    return await discogs_service.search_releases(query, page)

@router.get("/releases/", response_model=List[ReleaseResponse])
async def list_releases(db: AsyncSession = Depends(get_db)) -> List[ReleaseResponse]:
    """List all releases in our database"""
    result = await db.execute(select(Release))
    releases = result.scalars().all()
    return releases

# Dynamic routes after static ones
@router.get("/releases/{release_id}", response_model=ReleaseResponse)
async def read_release(
    release_id: int,
    db: AsyncSession = Depends(get_db),
    discogs_service: DiscogsService = Depends(get_discogs_service) # Add Discogs service dependency
) -> ReleaseResponse:
    """Get a specific release by its Discogs ID"""
    try:
        logger.info(f"Fetching release with ID {release_id}")
        release = await music_data_service.get_or_create_release_with_tracks(release_id, db, discogs_service)
        if not release:
            logger.warning(f"Release with ID {release_id} not found")
            raise NotFoundException("Release", str(release_id))
        logger.info(f"Successfully retrieved release: {release.title} (ID: {release.id})")
        return release
    except Exception as e:
        import traceback
        error_detail = traceback.format_exc()
        logger.error(f"Error in read_release: {str(e)}\n{error_detail}")
        # Re-raise the exception to maintain the 500 status code
        # but now we'll see the full traceback in the console
        raise

@router.post("/releases/", response_model=ReleaseResponse, status_code=status.HTTP_201_CREATED)
async def create_release(release_data: ReleaseCreate, db: AsyncSession = Depends(get_db)) -> ReleaseResponse:
    """Create a new release in our database"""
    # Check for duplicate release
    existing_release = await db.get(Release, release_data.id)
    if existing_release:
        raise DuplicateError("Release", str(release_data.id))

    # Create the release
    new_release_db_obj = Release(**release_data.dict())
    db.add(new_release_db_obj)
    await db.commit()
    await db.refresh(new_release_db_obj)
    return new_release_db_obj