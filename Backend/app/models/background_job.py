import enum
import uuid
import datetime
from sqlalchemy import String, ForeignKey, DateTime, func, Float
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship, Mapped, mapped_column

from app.services.database import Base

class JobStatus(str, enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"

class BackgroundJob(Base):
    __tablename__ = "background_jobs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Generic fields for any type of job
    job_type: Mapped[str] = mapped_column(String, index=True)
    parameters: Mapped[dict | None] = mapped_column(JSONB)
    status: Mapped[str] = mapped_column(String, default=JobStatus.PENDING, index=True)
    
    # Link to the user who requested the job, if they were logged in.
    user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), index=True)
    
    # Timestamps and performance tracking.
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    started_at: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True))
    duration_s: Mapped[float | None] = mapped_column(Float)

    # Store the final list of recommended track IDs or other results.
    result: Mapped[dict | None] = mapped_column(JSONB)

    owner = relationship("User")
