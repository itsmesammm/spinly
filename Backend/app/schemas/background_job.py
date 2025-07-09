from pydantic import BaseModel
import uuid
from typing import Optional, Any
from datetime import datetime

from app.models.background_job import JobStatus

# Shared properties
class JobBase(BaseModel):
    job_type: str
    parameters: Optional[dict] = None

# Properties to receive on job creation
class JobCreate(JobBase):
    user_id: Optional[uuid.UUID] = None

# Properties to receive on job update
class JobUpdate(BaseModel):
    status: Optional[JobStatus] = None
    result: Optional[dict] = None
    completed_at: Optional[datetime] = None
    duration_s: Optional[float] = None

# Properties shared by models stored in DB
class JobInDBBase(JobBase):
    id: uuid.UUID
    user_id: Optional[uuid.UUID] = None
    status: JobStatus
    result: Optional[Any] = None
    created_at: datetime
    updated_at: datetime
    completed_at: Optional[datetime] = None
    duration_s: Optional[float] = None

    class Config:
        orm_mode = True

# Properties to return to client
class Job(JobInDBBase):
    pass

# Properties stored in DB
class JobInDB(JobInDBBase):
    pass
