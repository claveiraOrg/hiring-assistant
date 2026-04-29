from __future__ import annotations

from uuid import UUID, uuid4
from datetime import datetime, UTC
from pydantic import Field

from src.schemas.base import BaseSchema, MatchConfidence


class ScoreBreakdown(BaseSchema):
    """Per-dimension score breakdown for explainability."""

    skills_score: float = Field(..., ge=0, le=1, description="Weight: 40%")
    experience_score: float = Field(..., ge=0, le=1, description="Weight: 25%")
    domain_score: float = Field(..., ge=0, le=1, description="Weight: 15%")
    salary_fit_score: float = Field(..., ge=0, le=1, description="Weight: 10%")
    location_fit_score: float = Field(..., ge=0, le=1, description="Weight: 10%")


class MatchResult(BaseSchema):
    """Single candidate-job match result with explanation."""

    match_id: UUID = Field(default_factory=uuid4)
    job_id: UUID
    candidate_id: UUID
    overall_score: float = Field(..., ge=0, le=1)
    confidence: MatchConfidence
    breakdown: ScoreBreakdown
    explanation: str = Field(..., description="Human-readable explanation of the match")
    created_at: datetime = Field(default_factory=datetime.lambda: datetime.now(UTC))


class RankedShortlist(BaseSchema):
    """Ranked shortlist of candidates for a job, post-GDPR filtering."""

    job_id: UUID
    matches: list[MatchResult] = Field(default_factory=list)
    total_candidates_scored: int = 0
    processing_time_ms: int = 0
    metadata: dict = Field(
        default_factory=dict,
        description="Additional context (e.g., fallback reason, warnings)",
    )
