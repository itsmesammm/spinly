from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.services.database import get_db
from app.services.discogs_manager import get_or_create_release
from app.schemas.release import ReleaseResponse, ReleaseCreate
from typing import List
from sqlalchemy.future import select
from app.models.release import Release


router = APIRouter()

@router.get("/releases/{release_id}", response_model=ReleaseResponse)
async def read_release(release_id: int, db: AsyncSession = Depends(get_db)):
    release = await get_or_create_release(release_id, db)
    if not release:
        raise HTTPException(status_code=404, detail="Release not found")
    return release # FastAPI will use ReleaseResponse to serialize this

@router.post("/releases/", response_model=ReleaseResponse, status_code=status.HTTP_201_CREATED)
async def create_release(release_data: ReleaseCreate, db: AsyncSession = Depends(get_db)):
    # You would typically have a service function for creating releases
    # For simplicity, let's just create it directly here as an example
    new_release_db_obj = Release(**release_data.dict()) # Convert Pydantic to SQLAlchemy model
    db.add(new_release_db_obj)
    await db.commit()
    await db.refresh(new_release_db_obj)
    return new_release_db_obj

@router.get("/releases/", response_model=List[ReleaseResponse])
async def list_releases(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Release)) # Assuming Release is imported from app.models.release
    releases = result.scalars().all()
    return releases