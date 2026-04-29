"""Repository for job CRUD and vector search."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import JobORM


class JobRepository:
    """Data access layer for job descriptions."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, job: JobORM) -> JobORM:
        self.session.add(job)
        await self.session.commit()
        await self.session.refresh(job)
        return job

    async def update(self, job: JobORM) -> JobORM:
        await self.session.merge(job)
        await self.session.commit()
        return job

    async def get_by_id(self, job_id: UUID) -> JobORM | None:
        result = await self.session.execute(
            select(JobORM).where(JobORM.job_id == job_id)
        )
        return result.scalar_one_or_none()

    async def get_by_external_id(self, external_id: str) -> JobORM | None:
        if not external_id:
            return None
        result = await self.session.execute(
            select(JobORM).where(JobORM.external_id == external_id)
        )
        return result.scalar_one_or_none()

    async def delete(self, job_id: UUID) -> bool:
        from sqlalchemy import delete as sa_delete
        result = await self.session.execute(
            sa_delete(JobORM).where(JobORM.job_id == job_id)
        )
        await self.session.commit()
        return result.rowcount > 0
