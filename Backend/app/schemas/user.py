from pydantic import BaseModel, EmailStr
from typing import Optional
from uuid import UUID

class UserBase(BaseModel):
    username: str
    email: EmailStr

class UserCreate(UserBase):
    password: str  # Raw password, will be hashed before storage

class UserUpdate(BaseModel):
    username: Optional[str] = None
    email: Optional[EmailStr] = None
    password: Optional[str] = None  # Optional password update

class UserResponse(UserBase):
    id: UUID

    class Config:
        from_attributes = True  # Allows Pydantic to convert SQLAlchemy models to JSON