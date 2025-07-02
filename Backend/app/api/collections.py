from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from typing import List, Optional
from sqlalchemy.orm import selectinload, joinedload, attributes

from app.services.database import get_db
from app.models.collection import Collection
from app.models.track import Track
from app.schemas.collection import CollectionCreate, CollectionResponse, CollectionUpdate
from app.core.exceptions import NotFoundException
from app.core.security import get_current_user, get_current_user_optional
from app.models.user import User

router = APIRouter()

@router.post("/collections/", response_model=CollectionResponse, status_code=status.HTTP_201_CREATED)
async def create_collection(collection_data: CollectionCreate, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    # Create new collection, automatically assigning it to the logged-in user
    db_collection = Collection(
        name=collection_data.name,
        user_id=current_user.id,
        is_public=collection_data.is_public
    )
    
    db.add(db_collection)
    await db.commit()
    await db.refresh(db_collection)

    # Manually set the 'tracks' relationship to an empty list.
    # This prevents a lazy load attempt when the response is serialized,
    # as we know a new collection has no tracks.
    attributes.set_committed_value(db_collection, "tracks", [])
    
    return db_collection

@router.get("/collections/", response_model=List[CollectionResponse])
async def list_collections(db: AsyncSession = Depends(get_db), current_user: Optional[User] = Depends(get_current_user_optional)):
    query = select(Collection).options(
        selectinload(Collection.tracks).selectinload(Track.artists),
        selectinload(Collection.tracks).joinedload(Track.release)
    )
    if current_user:
        # If user is logged in, show their collections (public and private) and all other public collections
        query = query.where(
            (Collection.is_public == True) | (Collection.user_id == current_user.id)
        )
    else:
        # If user is not logged in, only show public collections
        query = query.where(Collection.is_public == True)
    
    result = await db.execute(query)
    collections = result.scalars().unique().all()
    return collections

@router.get("/collections/{collection_id}", response_model=CollectionResponse)
async def get_collection(collection_id: str, db: AsyncSession = Depends(get_db), current_user: Optional[User] = Depends(get_current_user_optional)):
    query = select(Collection).where(Collection.id == collection_id).options(
        selectinload(Collection.tracks).selectinload(Track.artists),
        selectinload(Collection.tracks).joinedload(Track.release)
    )
    result = await db.execute(query)
    collection = result.scalar_one_or_none()

    if collection is None:
        raise NotFoundException("Collection", collection_id)

    # Check privacy
    if not collection.is_public:
        if not current_user or collection.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to view this collection"
            )

    return collection

@router.get("/users/{user_id}/collections/", response_model=List[CollectionResponse])
async def get_user_collections(user_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Collection).where(Collection.user_id == user_id)
    )
    collections = result.scalars().all()
    return collections

@router.patch("/collections/{collection_id}", response_model=CollectionResponse)
async def update_collection(collection_id: str, collection_data: CollectionUpdate, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    # Get existing collection with all relationships pre-loaded for the response
    result = await db.execute(
        select(Collection).where(Collection.id == collection_id).options(
            selectinload(Collection.tracks).selectinload(Track.artists),
            selectinload(Collection.tracks).joinedload(Track.release)
        )
    )
    collection = result.scalar_one_or_none()
    if collection is None:
        raise NotFoundException("Collection", collection_id)

    # Check if the current user is the owner of the collection
    if collection.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to update this collection"
        )
    
    # Update fields if provided
    update_data = collection_data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(collection, key, value)
    
    await db.commit()
    # No refresh needed, the in-memory object is up-to-date and fully loaded.
    return collection

@router.delete("/collections/{collection_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_collection(collection_id: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    result = await db.execute(select(Collection).where(Collection.id == collection_id))
    collection = result.scalar_one_or_none()
    if not collection:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Collection not found"
        )

    # Check if the current user is the owner of the collection
    if collection.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to delete this collection"
        )
    
    await db.delete(collection)
    await db.commit()

@router.post("/collections/{collection_id}/tracks/{track_id}", response_model=CollectionResponse)
async def add_track_to_collection(
    collection_id: str,
    track_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # Get collection with all nested relationships pre-loaded for the response model
    result = await db.execute(
        select(Collection).where(Collection.id == collection_id).options(
            selectinload(Collection.tracks).selectinload(Track.artists),
            selectinload(Collection.tracks).joinedload(Track.release)
        )
    )
    collection = result.scalar_one_or_none()
    if not collection:
        raise NotFoundException("Collection", collection_id)

    # Check ownership
    if collection.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")

    # Get the track to add, also pre-loading its relationships
    track_result = await db.execute(
        select(Track).where(Track.id == track_id).options(
            selectinload(Track.artists),
            joinedload(Track.release)
        )
    )
    track = track_result.scalar_one_or_none()
    if not track:
        raise NotFoundException("Track", track_id)

    # Add track to collection if not already present
    if track not in collection.tracks:
        collection.tracks.append(track)
        await db.commit()
        # No refresh needed, the in-memory object is up-to-date and fully loaded.

    return collection


@router.delete("/collections/{collection_id}/tracks/{track_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_track_from_collection(
    collection_id: str,
    track_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # Get collection with its tracks pre-loaded
    result = await db.execute(
        select(Collection).where(Collection.id == collection_id).options(selectinload(Collection.tracks))
    )
    collection = result.scalar_one_or_none()
    if not collection:
        raise NotFoundException("Collection", collection_id)

    # Check ownership
    if collection.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")

    # Find and remove the track
    track_to_remove = next((t for t in collection.tracks if t.id == track_id), None)
    if track_to_remove:
        collection.tracks.remove(track_to_remove)
        await db.commit()
    else:
        # Even if track wasn't in the collection, the outcome is the same (it's not there).
        # Returning a 404 might reveal whether a track is in a private collection.
        # So we silently succeed.
        pass