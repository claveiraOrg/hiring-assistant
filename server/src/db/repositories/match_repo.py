"""Repository for match results — read/write/query."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import MatchORM


class MatchRepository:
    """Data access layer for candidate-job match records."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, match: MatchORM) -> MatchORM:
        self.session.add(match)
        await self.session.commit()
        await self.session.refresh(match)
        return match

    async def create_batch(self, matches: list[MatchORM]) -> list[MatchORM]:
        self.session.add_all(matches)
        await self.session.commit()
        for m in matches:
            await self.session.refresh(m)
        return matches

    async def get_by_job(self, job_id: UUID, limit: int = 50) -> list[MatchORM]:
        result = await self.session.execute(
            select(MatchORM)
            .where(MatchORM.job_id == job_id)
            .order_by(MatchORM.overall_score.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_by_candidate(self, candidate_id: UUID) -> list[MatchORM]:
        result = await self.session.execute(
            select(MatchORM).where(MatchORM.candidate_id == candidate_id)
            .order_by(MatchORM.overall_score.desc())
        )
        return list(result.scalars().all())

    async def delete_by_candidate(self, candidate_id: UUID) -> int:
        result = await self.session.execute(
            delete(MatchORM).where(MatchORM.candidate_id == candidate_id)
        )
        await self.session.commit()
        return result.rowcount

    async def delete_by_job(self, job_id: UUID) -> int:
        result = await self.session.execute(
            delete(MatchORM).where(MatchORM.job_id == job_id)
        )
        await self.session.commit()
        return result.rowcount
