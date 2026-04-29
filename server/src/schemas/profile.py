from __future__ import annotations

from uuid import UUID, uuid4
from datetime import datetime, UTC
from pydantic import Field

from src.schemas.base import BaseSchema, SeniorityLevel, GDPRConsentStatus


class CandidateProfile(BaseSchema):
    """Structured professional profile extracted from a CV."""

    candidate_id: UUID = Field(default_factory=uuid4)
    external_id: str | None = Field(None, description="External system reference ID")
    full_name: str = Field(..., min_length=1, max_length=200)
    skills: list[str] = Field(..., min_length=1)
    years_of_experience: float = Field(..., ge=0)
    seniority: SeniorityLevel
    domains: list[str] = Field(default_factory=list)
    career_trajectory: list[dict] = Field(
        default_factory=list,
        description="List of {role, company, start_date, end_date} entries",
    )
    salary_expectation: float | None = Field(None, ge=0)
    location: str | None = Field(None, max_length=200)
    willing_to_relocate: bool = False
    embedding: list[float] | None = Field(None, description="Vector embedding for similarity search")
    confidence_score: float = Field(..., ge=0, le=1, description="Extraction confidence (0-1)")
    raw_cv_s3_key: str | None = Field(None, description="S3 key for raw CV document")
    created_at: datetime = Field(default_factory=datetime.lambda: datetime.now(UTC))
    consent_status: GDPRConsentStatus = GDPRConsentStatus.PENDING
