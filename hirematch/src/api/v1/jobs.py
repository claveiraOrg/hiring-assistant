import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.auth import ApiKeyDep
from src.core.db import get_db
from src.models.job_posting import JobPosting
from src.schemas.job import JobCreate, JobResponse

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.post("", response_model=JobResponse, status_code=status.HTTP_201_CREATED)
async def create_job(
    body: JobCreate,
    _: str = ApiKeyDep,
    db: AsyncSession = Depends(get_db),
) -> JobResponse:
    job = JobPosting(
        title=body.title,
        description=body.description,
    )
    db.add(job)
    await db.flush()
    await db.refresh(job)
    return JobResponse.model_validate(job)


@router.get("/{job_id}", response_model=JobResponse)
async def get_job(
    job_id: uuid.UUID,
    _: str = ApiKeyDep,
    db: AsyncSession = Depends(get_db),
) -> JobResponse:
    result = await db.execute(select(JobPosting).where(JobPosting.id == job_id))
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    return JobResponse.model_validate(job)
