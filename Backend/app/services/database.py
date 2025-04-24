from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import declarative_base, sessionmaker

from app.core.config import settings  # where DATABASE_URL lives

engine = create_async_engine(settings.DATABASE_URL, echo=True)
SessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

Base = declarative_base()
