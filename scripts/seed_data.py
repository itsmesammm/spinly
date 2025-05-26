import sys
import os
import asyncio
from datetime import datetime

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'Backend')))

from app.models.user import User
from app.models.artist import Artist
from app.models.collection import Collection
from app.models.release import Release
from app.models.track import Track
from app.services.database import engine
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import sessionmaker

async def create_demo_data():
    # Create async session
    async_session = sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )

    async with async_session() as session:
        # Create demo users
        users = [
            User(
                username="sam",
                email="samanthamillows@gmail.com",
                password_hash="demo_password_hash",  # In production, use proper password hashing
            ),
            User(
                username="vinyl_lover",
                email="vinyl@example.com",
                password_hash="demo_password_hash",
            )
        ]
        session.add_all(users)
        await session.flush()

        # Create demo artists
        artists = [
            Artist(
                name="The Beatles",
                discogs_id=123456
            ),
            Artist(
                name="Pink Floyd",
                discogs_id=234567
            ),
            Artist(
                name="Miles Davis",
                discogs_id=345678
            )
        ]
        session.add_all(artists)
        await session.flush()

        # Create demo releases
        releases = [
            Release(
                discogs_id=1234567,
                title="Abbey Road",
                artist="The Beatles",
                style="Rock"
            ),
            Release(
                discogs_id=2345678,
                title="Dark Side of the Moon",
                artist="Pink Floyd",
                style="Progressive Rock"
            ),
            Release(
                discogs_id=3456789,
                title="Kind of Blue",
                artist="Miles Davis",
                style="Jazz"
            )
        ]
        session.add_all(releases)
        await session.flush()

        # Create demo collections
        collections = [
            Collection(
                name="Classic Rock",
                user_id=users[0].id
            ),
            Collection(
                name="Jazz Essentials",
                user_id=users[1].id
            )
        ]
        session.add_all(collections)
        await session.flush()

        # Create demo tracks
        tracks = [
            Track(
                title="Come Together",
                artist_id=artists[0].id,  # The Beatles
                discogs_id=11111,
                youtube_url="https://youtube.com/watch?v=45cYwDMibGo"
            ),
            Track(
                title="Money",
                artist_id=artists[1].id,  # Pink Floyd
                discogs_id=22222,
                youtube_url="https://youtube.com/watch?v=cpbbuaIA3Ds"
            ),
            Track(
                title="So What",
                artist_id=artists[2].id,  # Miles Davis
                discogs_id=33333,
                youtube_url="https://youtube.com/watch?v=zqNTltOGh5c"
            )
        ]
        session.add_all(tracks)

        # Commit all changes
        await session.commit()
        print("✅ Demo data created successfully!")

if __name__ == "__main__":
    asyncio.run(create_demo_data())
