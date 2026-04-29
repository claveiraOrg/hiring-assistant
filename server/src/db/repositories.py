from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import (
    AuditLogDB,
    CandidateDB,
    ConsentLogDB,
    JobDB,
    MatchDB,
)


class CandidateRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, candidate: CandidateDB) -> CandidateDB:
        self.session.add(candidate)
        await self.session.flush()
        return candidate

    async def get_by_id(self, candidate_id) -> CandidateDB | None:
        return await self.session.get(CandidateDB, candidate_id)

    async def delete(self, candidate_id) -> bool:
        obj = await self.get_by_id(candidate_id)
        if obj:
            await self.session.delete(obj)
            return True
        return False


class JobRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, job: JobDB) -> JobDB:
        self.session.add(job)
        await self.session.flush()
        return job

    async def get_by_id(self, job_id) -> JobDB | None:
        return await self.session.get(JobDB, job_id)


class MatchRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, match: MatchDB) -> MatchDB:
        self.session.add(match)
        await self.session.flush()
        return match

    async def get_by_candidate_and_job(self, candidate_id, job_id) -> MatchDB | None:
        from sqlalchemy import select

        stmt = select(MatchDB).where(
            MatchDB.candidate_id == candidate_id,
            MatchDB.job_id == job_id,
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()


class AuditLogRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def log(self, entry: AuditLogDB) -> AuditLogDB:
        self.session.add(entry)
        await self.session.flush()
        return entry


class ConsentLogRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_latest(self, candidate_id) -> ConsentLogDB | None:
        from sqlalchemy import select

        stmt = (
            select(ConsentLogDB)
            .where(ConsentLogDB.candidate_id == candidate_id)
            .order_by(ConsentLogDB.created_at.desc())
            .limit(1)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
