from __future__ import annotations

from uuid import UUID, uuid4
from datetime import datetime, UTC
from pydantic import Field

from src.schemas.base import BaseSchema, GDPRConsentStatus


class ConsentRecord(BaseSchema):
    """A candidate's consent record for data processing."""

    consent_id: UUID = Field(default_factory=uuid4)
    candidate_id: UUID
    status: GDPRConsentStatus = GDPRConsentStatus.PENDING
    granted_at: datetime | None = None
    revoked_at: datetime | None = None
    expires_at: datetime | None = None
    data_scope: list[str] = Field(
        default_factory=list,
        description="Data fields consented for (e.g., ['profile', 'skills', 'location'])",
    )


class AccessAuditEvent(BaseSchema):
    """Immutable audit log entry for every data access."""

    event_id: UUID = Field(default_factory=uuid4)
    timestamp: datetime = Field(default_factory=datetime.now(UTC))
    actor_id: str = Field(..., description="Recruiter or system user ID")
    action: str = Field(
        ..., description="One of: view_profile, query_match, delete, export"
    )
    resource_type: str = Field(
        ..., description="One of: candidate, job, match, consent"
    )
    resource_id: UUID
    granted: bool = Field(..., description="Was the access authorized")
    reason: str = Field(..., description="Why access was granted or denied")
    request_details: dict | None = Field(
        None, description="Additional context (IP, role, query params)"
    )
