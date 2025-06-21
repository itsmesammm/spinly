from sqlalchemy import Table, Column, ForeignKey, Integer
from app.services.database import Base
from sqlalchemy.dialects.postgresql import UUID

collection_track = Table(
    'collection_track',
    Base.metadata,
    Column('collection_id', UUID(as_uuid=True), ForeignKey('collections.id'), primary_key=True),
    Column('track_id', Integer, ForeignKey('tracks.id'), primary_key=True)
)
