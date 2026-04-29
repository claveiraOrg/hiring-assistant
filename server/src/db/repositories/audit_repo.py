"""Repository for GDPR audit trail — append-only log of all access events."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import AccessAuditORM, ConsentORM
from src.schemas import AccessAuditEvent


class AuditRepository:
    """Append-only audit trail for GDPR compliance."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def write(self, event: AccessAuditEvent) -> AccessAuditORM:
        orm = AccessAuditORM(
            event_id=event.event_id,
            timestamp=event.timestamp,
            actor_id=event.actor_id,
            action=event.action,
            resource_type=event.resource_type,
            resource_id=event.resource_id,
            granted=event.granted,
            reason=event.reason,
        )
        self.session.add(orm)
        await self.session.commit()
        return orm

    async def query(
        self,
        actor_id: str | None = None,
        resource_type: str | None = None,
        action: str | None = None,
        since: datetime | None = None,
        limit: int = 100,
    ) -> list[AccessAuditORM]:
        stmt = select(AccessAuditORM)
        if actor_id:
            stmt = stmt.where(AccessAuditORM.actor_id == actor_id)
        if resource_type:
            stmt = stmt.where(AccessAuditORM.resource_type == resource_type)
        if action:
            stmt = stmt.where(AccessAuditORM.action == action)
        if since:
            stmt = stmt.where(AccessAuditORM.timestamp >= since)
        stmt = stmt.order_by(AccessAuditORM.timestamp.desc()).limit(limit)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())


class ConsentRepository:
    """Consent record management."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_active(self, candidate_id: UUID) -> ConsentORM | None:
        result = await self.session.execute(
            select(ConsentORM).where(ConsentORM.candidate_id == candidate_id)
        )
        return result.scalar_one_or_none()

    async def grant(self, candidate_id: UUID, scope: list[str] | None = None) -> ConsentORM:
        consent = ConsentORM(
            candidate_id=candidate_id,
            status="granted",
            granted_at=datetime.utcnow(),
            data_scope=scope or ["all"],
        )
        self.session.add(consent)
        await self.session.commit()
        await self.session.refresh(consent)
        return consent

    async def revoke(self, candidate_id: UUID) -> None:
        from sqlalchemy import update
        await self.session.execute(
            update(ConsentORM)
            .where(ConsentORM.candidate_id == candidate_id)
            .values(status="revoked", revoked_at=datetime.utcnow())
        )
        await self.session.commit()
