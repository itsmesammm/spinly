import logging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from app.models.release import Release
from app.models.track import Track
from app.models.artist import Artist
from app.services.discogs import DiscogsService

logger = logging.getLogger(__name__)

async def get_or_create_artist(discogs_artist: dict, db: AsyncSession) -> Artist:
    """Finds an artist in the DB or creates them."""
    # This is a simplified version, assuming Discogs provides a unique artist ID
    discogs_id = discogs_artist.get("id")
    artist = None
    if discogs_id:
        result = await db.execute(select(Artist).where(Artist.discogs_id == discogs_id))
        artist = result.scalars().first()

    if not artist:
        # Fallback to check by name if no ID or not found by ID
        name = discogs_artist.get("name")
        result = await db.execute(select(Artist).where(Artist.name == name))
        artist = result.scalars().first()

    if artist:
        return artist

    # Create new artist if not found
    new_artist = Artist(
        name=discogs_artist.get("name"),
        discogs_id=discogs_artist.get("id")
    )
    db.add(new_artist)
    await db.flush()  # Use flush to get the ID before commit
    await db.refresh(new_artist)
    return new_artist


async def get_or_create_release_with_tracks(
    discogs_release_id: int,
    db: AsyncSession,
    discogs_service: DiscogsService
) -> Release | None:
    """
    The main function to get a release from our DB or fetch it from Discogs,
    including its primary artist and all its tracks with their artists.
    """
    try:
        # 1. Check DB for the release
        result = await db.execute(
            select(Release).options(
                selectinload(Release.tracks).selectinload(Track.artists),
                selectinload(Release.artist)
            ).where(Release.discogs_id == discogs_release_id)
        )
        release = result.scalars().first()
        if release:
            logger.info(f"Found existing release in DB: {release.title}")
            return release

        # 2. Fetch from Discogs API using the DiscogsService
        logger.info(f"Fetching release {discogs_release_id} from Discogs API")
        data = await discogs_service.get_release(discogs_release_id)

        # 3. Get or create the primary artist for the release
        main_artist_obj = None
        if data.get("artists"):
            main_artist_data = data["artists"][0]
            main_artist_obj = await get_or_create_artist(main_artist_data, db)

        # 4. Create the Release object
        new_release = Release(
            discogs_id=discogs_release_id,
            title=data.get("title", "Unknown Title"),
            year=data.get("year"),
            label=data.get("labels")[0].get("name") if data.get("labels") else None,
            styles=data.get("styles", []),
            artist_id=main_artist_obj.id if main_artist_obj else None
        )
        db.add(new_release)
        await db.flush() # Flush to get the new_release.id

        # 5. Create Track objects and link artists
        if data.get("tracklist"):
            for track_item in data["tracklist"]:
                if track_item.get("type_") == "track":
                    new_track = Track(
                        title=track_item.get("title"),
                        position=track_item.get("position"),
                        duration=track_item.get("duration"),
                        release_id=new_release.id
                    )
                    # Link artists to the track
                    if track_item.get("artists"):
                        for track_artist_data in track_item["artists"]:
                            track_artist_obj = await get_or_create_artist(track_artist_data, db)
                            new_track.artists.append(track_artist_obj)
                    db.add(new_track)

        await db.commit()
        await db.refresh(new_release)
        logger.info(f"Saved new release to database with id={new_release.id}")
        return new_release

    except Exception as e:
        import traceback
        logger.error(f"Error in get_or_create_release_with_tracks: {str(e)}")
        logger.error(traceback.format_exc())
        await db.rollback()
        raise

