from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from app.models.release import Release
from app.api.discogs import fetch_release_from_discogs

async def get_or_create_release(release_id: int, db: AsyncSession):
    # 1. Check DB
    result = await db.execute(select(Release).where(Release.discogs_id == release_id))
    release = result.scalars().first()
    if release:
        return release

    # 2. Fetch from Discogs
    data = await fetch_release_from_discogs(release_id)

    # 3. Store in DB
    new_release = Release(
        discogs_id=release_id,
        title=data.get("title", "Unknown Title"),
        artist=data["artists"][0]["name"] if data.get("artists") else "Unknown Artist"
    )

    db.add(new_release)
    await db.commit()
    await db.refresh(new_release)

    return new_release
