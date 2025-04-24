from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.services.database import get_db
from app.services.discogs_manager import get_or_create_release

router = APIRouter()

@router.get("/release/{release_id}")
async def fetch_release(release_id: int, db: AsyncSession = Depends(get_db)):
    release = await get_or_create_release(release_id, db)
    return {
        "title": release.title,
        "artist": release.artist
    }