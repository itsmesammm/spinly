import logging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from app.models.release import Release
from app.api.discogs import fetch_release_from_discogs

logger = logging.getLogger(__name__)

async def get_or_create_release(release_id: int, db: AsyncSession):
    try:
        # 1. Check DB
        logger.info(f"Checking database for release with discogs_id={release_id}")
        result = await db.execute(select(Release).where(Release.discogs_id == release_id))
        release = result.scalars().first()
        if release:
            logger.info(f"Found existing release in database: {release.title}")
            return release

        # 2. Fetch from Discogs
        logger.info(f"Fetching release {release_id} from Discogs API")
        data = await fetch_release_from_discogs(release_id)
        logger.debug(f"Received data from Discogs: {data}")

        # 3. Store in DB
        new_release = Release(
            discogs_id=release_id,
            title=data.get("title", "Unknown Title"),
            artist=data.get("artist", "Unknown Artist"),
            styles=data.get("styles", []),
            year=data.get("year"),
            label=data.get("label")
        )

        logger.info(f"Created new release object: {new_release.title}")
        db.add(new_release)
        await db.commit()
        await db.refresh(new_release)
        logger.info(f"Saved new release to database with id={new_release.id}")

        return new_release
    except Exception as e:
        import traceback
        logger.error(f"Error in get_or_create_release: {str(e)}")
        logger.error(traceback.format_exc())
        raise
