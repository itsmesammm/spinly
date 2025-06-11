from sqlalchemy import Table, Column, Integer, ForeignKey
from app.services.database import Base

# This is NOT a model class, it's a direct Table definition
track_artist_association = Table(
    'track_artist', 
    Base.metadata,
    Column('track_id', Integer, ForeignKey('tracks.id'), primary_key=True),
    Column('artist_id', Integer, ForeignKey('artists.id'), primary_key=True)
)