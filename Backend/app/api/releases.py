from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.services.database import get_db
from app.services.discogs_manager import get_or_create_release
from app.schemas.release import ReleaseResponse, ReleaseCreate
from app.core.exceptions import NotFoundException, DuplicateError
from typing import List, Dict
from sqlalchemy.future import select
from app.models.release import Release
from app.services.discogs import DiscogsService


router = APIRouter()

@router.get("/releases/{release_id}", response_model=ReleaseResponse)
async def read_release(release_id: int, db: AsyncSession = Depends(get_db)):
    release = await get_or_create_release(release_id, db)
    if not release:
        raise NotFoundException("Release", str(release_id))
    return release

@router.post("/releases/", response_model=ReleaseResponse, status_code=status.HTTP_201_CREATED)
async def create_release(release_data: ReleaseCreate, db: AsyncSession = Depends(get_db)):
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

@router.get("/releases/", response_model=List[ReleaseResponse])
async def list_releases(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Release))
    releases = result.scalars().all()
    return releases

@router.get("/releases/search/")
async def search_releases(
    query: str,
    page: int = 1,
    discogs_service: DiscogsService = Depends(DiscogsService)
) -> Dict:
    """Search for releases in Discogs database"""
    return await discogs_service.search_releases(query, page)