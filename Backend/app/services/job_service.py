from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
import uuid
from typing import Optional

from app.models.background_job import BackgroundJob, JobStatus
from app.schemas.background_job import JobCreate, JobUpdate

class JobService:
    def __init__(self, db_session: AsyncSession):
        self.db = db_session

    async def get_job(self, job_id: uuid.UUID) -> Optional[BackgroundJob]:
        """Retrieve a job by its ID."""
        result = await self.db.execute(
            select(BackgroundJob).where(BackgroundJob.id == job_id)
        )
        return result.scalar_one_or_none()

    async def create_job(self, job_create: JobCreate) -> BackgroundJob:
        """Create a new background job record."""
        db_job = BackgroundJob(
            job_type=job_create.job_type,
            parameters=job_create.parameters,
            user_id=job_create.user_id,
            status=JobStatus.PENDING
        )
        self.db.add(db_job)
        await self.db.commit()
        await self.db.refresh(db_job)
        return db_job

    async def update_job(self, job_id: uuid.UUID, job_update: JobUpdate) -> Optional[BackgroundJob]:
        """Update a job's status, result, or other fields."""
        db_job = await self.get_job(job_id)
        if not db_job:
            return None

        update_data = job_update.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(db_job, field, value)

        await self.db.commit()
        await self.db.refresh(db_job)
        return db_job

async def get_job_service(db: AsyncSession):
    return JobService(db)
