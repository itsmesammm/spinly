import logging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from app.models.release import Release
from app.models.track import Track
from app.models.artist import Artist
from app.services.discogs import DiscogsService

logger = logging.getLogger(__name__)

async def get_or_create_artist(artist_data: dict, db: AsyncSession) -> Artist:
    # Treat a discogs_id of 0 as None (NULL in the database)
    discogs_id = artist_data.get("id") if artist_data.get("id") != 0 else None

    # 1. Try to find by Discogs ID if it's a valid, non-zero ID
    if discogs_id:
        stmt = select(Artist).where(Artist.discogs_id == discogs_id)
        result = await db.execute(stmt)
        db_artist = result.scalar_one_or_none()
        if db_artist:
            logger.debug(f"Found existing artist in DB by discogs_id={discogs_id}: {db_artist.name}")
            return db_artist

    # 2. If no valid Discogs ID or not found, try to find by name.
    # This is crucial for artists with discogs_id=0 or for general data consistency.
    stmt = select(Artist).where(Artist.name == artist_data.get("name"))
    result = await db.execute(stmt)
    db_artist = result.scalar_one_or_none()

    if db_artist:
        logger.debug(f"Found existing artist in DB by name: {db_artist.name}")
        # If we found an artist by name that was missing a discogs_id, update it.
        if not db_artist.discogs_id and discogs_id:
            logger.debug(f"Updating artist '{db_artist.name}' with new discogs_id={discogs_id}")
            db_artist.discogs_id = discogs_id
            # The session will be flushed/committed by the calling function.
        return db_artist

    # 3. If not found by either, create a new artist.
    logger.debug(f"Creating new artist: {artist_data.get('name')} with discogs_id={discogs_id}")
    db_artist = Artist(name=artist_data.get("name"), discogs_id=discogs_id)
    db.add(db_artist)
    await db.flush()  # Use flush to get the ID before the transaction commits.
    await db.refresh(db_artist)
    return db_artist


async def get_all_releases_with_details(db: AsyncSession) -> list[Release]:
    """Fetches all releases from the DB, eager-loading their tracks and artists."""
    stmt = select(Release).options(
        selectinload(Release.tracks).selectinload(Track.artists),
        selectinload(Release.artist)
    )
    result = await db.execute(stmt)
    return result.scalars().unique().all()


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
                    if new_release.discogs_id == 3490219:
                        logger.info(f"[DEBUG 3490219] Raw track data from Discogs: {track_item}")
                    new_track = Track(
                        title=track_item.get("title"),
                        position=track_item.get("position"),
                        release_id=new_release.id
                    )
                    # Link artists to the track
                    if track_item.get("artists"):
                        for track_artist_data in track_item["artists"]:
                            track_artist_obj = await get_or_create_artist(track_artist_data, db)
                            if track_artist_obj: # Ensure artist was found/created
                                new_track.artists.append(track_artist_obj)
                    elif main_artist_obj: # If no track-specific artists, link the main release artist
                        new_track.artists.append(main_artist_obj)
                    db.add(new_track)

        await db.commit()
        logger.info(f"Saved new release to database: ID={new_release.id}, Title='{new_release.title}'")
        return new_release

    except Exception as e:
        import traceback
        logger.error(f"Error in get_or_create_release_with_tracks: {str(e)}")
        logger.error(traceback.format_exc())
        await db.rollback()
        raise

