"""Repository for candidate CRUD, vector search, and cascade deletion."""

from __future__ import annotations

import logging
from uuid import UUID

from sqlalchemy import delete, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import CandidateORM, ConsentORM

logger = logging.getLogger(__name__)


class CandidateRepository:
    """Data access layer for candidates with GDPR-aware operations."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, candidate: CandidateORM) -> CandidateORM:
        self.session.add(candidate)
        await self.session.commit()
        await self.session.refresh(candidate)
        return candidate

    async def update(self, candidate: CandidateORM) -> CandidateORM:
        await self.session.merge(candidate)
        await self.session.commit()
        return candidate

    async def get_by_id(self, candidate_id: UUID) -> CandidateORM | None:
        result = await self.session.execute(
            select(CandidateORM).where(CandidateORM.candidate_id == candidate_id)
        )
        return result.scalar_one_or_none()

    async def get_by_external_id(self, external_id: str) -> CandidateORM | None:
        if not external_id:
            return None
        result = await self.session.execute(
            select(CandidateORM).where(CandidateORM.external_id == external_id)
        )
        return result.scalar_one_or_none()

    async def search_by_embedding(
        self, embedding: list[float], limit: int = 200
    ) -> list[CandidateORM]:
        """Cosine-distance vector search, filtered to consented candidates only."""
        stmt = (
            select(CandidateORM)
            .where(CandidateORM.embedding.isnot(None))
            .where(CandidateORM.consent_status == "granted")
            .order_by(CandidateORM.embedding.cosine_distance(embedding))  # type: ignore[arg-type]
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_recent_consented(self, limit: int = 50) -> list[CandidateORM]:
        """Fallback: most recent consented candidates when vector search fails."""
        stmt = (
            select(CandidateORM)
            .where(CandidateORM.consent_status == "granted")
            .order_by(CandidateORM.created_at.desc())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def update_consent_status(self, candidate_id: UUID, status: str) -> None:
        await self.session.execute(
            text(
                "UPDATE hiring.candidates SET consent_status = :status WHERE candidate_id = :cid"
            ).bindparams(status=status, cid=candidate_id)
        )
        await self.session.commit()

    async def cascade_delete(self, candidate_id: UUID) -> list[str]:
        """GDPR Article 17 right to deletion — cascade across all tables."""
        deleted = []

        # 1. Delete consent record
        result = await self.session.execute(
            delete(ConsentORM).where(ConsentORM.candidate_id == candidate_id)
        )
        if result.rowcount:
            deleted.append("consent")

        # 2. Delete matches referencing this candidate
        from src.db.models import MatchORM
        result = await self.session.execute(
            delete(MatchORM).where(MatchORM.candidate_id == candidate_id)
        )
        if result.rowcount:
            deleted.append("matches")

        # 3. Delete candidate record (cascades to embedding)
        result = await self.session.execute(
            delete(CandidateORM).where(CandidateORM.candidate_id == candidate_id)
        )
        if result.rowcount:
            deleted.append("candidate")

        await self.session.commit()
        return deleted
