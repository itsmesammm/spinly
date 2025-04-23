from sqlalchemy.ext.asyncio import (AsyncSession, create_async_engine)
from sqlalchemy.orm import sessionmaker
from app.core.config import settings

engine = create_async_engine(settings.DATABASE_URL, future = True, echo = True)

AsyncSessionLocal = sessionmaker(
    bind = engine,
    class_ = AsyncSession,
    expire_on_commit = False
)


async def get_db():
    async with AsyncSessionLocal() as session:
        yield session  #ensures that the session is properly closed after use.
