from __future__ import annotations

from uuid import UUID, uuid4
from datetime import datetime, UTC
from pydantic import Field

from src.schemas.base import BaseSchema, SeniorityLevel


class StructuredJobIntent(BaseSchema):
    """Structured job intent extracted from a free-text job description."""

    job_id: UUID = Field(default_factory=uuid4)
    title: str = Field(..., min_length=1, max_length=200)
    required_skills: list[str] = Field(..., min_length=1)
    preferred_skills: list[str] = Field(default_factory=list)
    seniority: SeniorityLevel
    years_experience_required: int = Field(..., ge=0)
    domains: list[str] = Field(default_factory=list)
    salary_range: tuple[float, float] | None = Field(
        None, description="(min_salary, max_salary)"
    )
    location: str | None = Field(None, max_length=200)
    remote_allowed: bool = False
    embedding: list[float] | None = Field(None, description="Vector embedding for similarity search")
    confidence_score: float = Field(..., ge=0, le=1, description="Extraction confidence (0-1)")
    ambiguities: list[str] = Field(
        default_factory=list,
        description="Detected inconsistencies in the original JD",
    )
    raw_jd_s3_key: str | None = Field(None, description="S3 key for raw job description")
    created_at: datetime = Field(default_factory=datetime.lambda: datetime.now(UTC))
