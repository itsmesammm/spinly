from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from typing import List

from app.services.database import get_db
from app.models.collection import Collection
from app.schemas.collection import CollectionCreate, CollectionResponse, CollectionUpdate
from app.core.exceptions import NotFoundException
from app.core.security import get_current_user
from app.models.user import User

router = APIRouter()

@router.post("/collections/", response_model=CollectionResponse, status_code=status.HTTP_201_CREATED)
async def create_collection(collection_data: CollectionCreate, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    # Create new collection, automatically assigning it to the logged-in user
    db_collection = Collection(
        name=collection_data.name,
        user_id=current_user.id
    )
    
    db.add(db_collection)
    await db.commit()
    await db.refresh(db_collection)
    return db_collection

@router.get("/collections/", response_model=List[CollectionResponse])
async def list_collections(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Collection))
    collections = result.scalars().all()
    return collections

@router.get("/collections/{collection_id}", response_model=CollectionResponse)
async def get_collection(collection_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Collection).where(Collection.id == collection_id))
    collection = result.scalar_one_or_none()
    if collection is None:
        raise NotFoundException("Collection", collection_id)
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
    # Get existing collection
    result = await db.execute(select(Collection).where(Collection.id == collection_id))
    collection = result.scalar_one_or_none()
    if collection is None:
        raise NotFoundException("Collection", collection_id)

    # Check if the current user is the owner of the collection
    if collection.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to update this collection"
        )
    
    # Update name if provided
    if collection_data.name:
        collection.name = collection_data.name
    
    await db.commit()
    await db.refresh(collection)
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