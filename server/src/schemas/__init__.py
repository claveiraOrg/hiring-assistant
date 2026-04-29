"""Shared Pydantic schemas — cross-agent communication contracts.

Every agent's input and output must be validated against these schemas.
This is the canonical contract for all inter-service communication.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


# ─── Enums ───────────────────────────────────────────────────────────────

class SeniorityLevel(str, Enum):
    JUNIOR = "junior"
    MID = "mid"
    SENIOR = "senior"
    STAFF = "staff"
    PRINCIPAL = "principal"
    EXECUTIVE = "executive"


class MatchConfidence(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class GDPRConsentStatus(str, Enum):
    GRANTED = "granted"
    REVOKED = "revoked"
    PENDING = "pending"
    EXPIRED = "expired"


class WorkflowType(str, Enum):
    CANDIDATE_INGESTION = "candidate_ingestion"
    JOB_MATCHING = "job_matching"
    BATCH_MATCHING = "batch_matching"
    DATA_DELETION = "data_deletion"


# ─── Common ──────────────────────────────────────────────────────────────

class HealthResponse(BaseModel):
    status: str = Field(default="ok", description="Service health status")


# ─── Candidate Profile ───────────────────────────────────────────────────

class CareerEntry(BaseModel):
    role: str
    company: str
    start_date: str | None = None
    end_date: str | None = None


class CandidateProfile(BaseModel):
    candidate_id: UUID
    external_id: str | None = None
    full_name: str
    skills: list[str]
    years_of_experience: int
    seniority: SeniorityLevel
    domains: list[str]
    career_trajectory: list[CareerEntry] = Field(default_factory=list)
    salary_expectation: float | None = None
    location: str | None = None
    willing_to_relocate: bool = False
    embedding: list[float] | None = None
    confidence_score: float = Field(ge=0.0, le=1.0)
    raw_cv_s3_key: str | None = None
    created_at: datetime
    consent_status: GDPRConsentStatus = GDPRConsentStatus.PENDING


class CVIngestRequest(BaseModel):
    cv_text: str
    candidate_external_id: str | None = None


class CVIngestResponse(BaseModel):
    profile: CandidateProfile
    processing_time_ms: int


# ─── Job Intent ──────────────────────────────────────────────────────────

class StructuredJobIntent(BaseModel):
    job_id: UUID
    title: str
    required_skills: list[str]
    preferred_skills: list[str] = Field(default_factory=list)
    seniority: SeniorityLevel
    years_experience_required: int = 0
    domains: list[str]
    salary_range: tuple[float, float] | None = None
    location: str | None = None
    remote_allowed: bool = False
    embedding: list[float] | None = None
    raw_jd_s3_key: str | None = None
    confidence_score: float = Field(ge=0.0, le=1.0)
    created_at: datetime


class JDExtractRequest(BaseModel):
    jd_text: str
    job_external_id: str | None = None


class AmbiguityWarning(BaseModel):
    field: str
    description: str
    severity: str = "info"  # info, warning, error


class JDExtractResponse(BaseModel):
    job: StructuredJobIntent
    ambiguities: list[AmbiguityWarning] = Field(default_factory=list)
    processing_time_ms: int


# ─── Matching ────────────────────────────────────────────────────────────

class ScoreBreakdown(BaseModel):
    skills_score: float = Field(ge=0.0, le=1.0)
    experience_score: float = Field(ge=0.0, le=1.0)
    domain_score: float = Field(ge=0.0, le=1.0)
    salary_fit_score: float = Field(ge=0.0, le=1.0)
    location_fit_score: float = Field(ge=0.0, le=1.0)


class MatchResult(BaseModel):
    match_id: UUID
    job_id: UUID
    candidate_id: UUID
    overall_score: float = Field(ge=0.0, le=1.0)
    confidence: MatchConfidence
    breakdown: ScoreBreakdown
    explanation: str
    created_at: datetime


class MatchRequest(BaseModel):
    job_id: UUID
    candidate_ids: list[UUID]


class MatchResponse(BaseModel):
    matches: list[MatchResult]
    total_scored: int
    processing_time_ms: int


class RankedShortlist(BaseModel):
    job_id: UUID
    matches: list[MatchResult]
    total_candidates_scored: int
    processing_time_ms: int
    metadata: dict = Field(default_factory=dict)


# ─── GDPR ────────────────────────────────────────────────────────────────

class ConsentRecord(BaseModel):
    consent_id: UUID
    candidate_id: UUID
    status: GDPRConsentStatus
    granted_at: datetime | None = None
    revoked_at: datetime | None = None
    expires_at: datetime | None = None
    data_scope: list[str] = Field(default_factory=list)


class AccessAuditEvent(BaseModel):
    event_id: UUID
    timestamp: datetime
    actor_id: str
    action: str  # view_profile, query_match, delete, consent_change
    resource_type: str  # candidate, job, match
    resource_id: UUID
    granted: bool
    reason: str


class ConsentCheckRequest(BaseModel):
    candidate_id: UUID
    actor_id: str
    action: str


class ConsentCheckResponse(BaseModel):
    allowed: bool
    consent_status: GDPRConsentStatus
    reason: str | None = None


class GDPRFilterRequest(BaseModel):
    profile: CandidateProfile
    recruiter_role: str  # hiring_manager, internal_recruiter, external_agency


class GDPRFilterResponse(BaseModel):
    filtered_profile: dict
    audit_event: AccessAuditEvent


class DeletionRequest(BaseModel):
    candidate_id: UUID
    actor_id: str


class DeletionResponse(BaseModel):
    status: str
    candidate_id: str
    deleted_records: list[str] = Field(default_factory=list)


# ─── Feedback (Phase 2) ─────────────────────────────────────────────────

class RecruiterAction(BaseModel):
    recruiter_id: str
    candidate_id: UUID
    job_id: UUID
    action: str  # viewed, shortlisted, interviewed, rejected, hired
    timestamp: datetime


class WeightUpdate(BaseModel):
    skills_weight: float | None = None
    experience_weight: float | None = None
    domain_weight: float | None = None
    salary_fit_weight: float | None = None
    location_fit_weight: float | None = None


__all__ = [
    "SeniorityLevel",
    "MatchConfidence",
    "GDPRConsentStatus",
    "WorkflowType",
    "HealthResponse",
    "CandidateProfile",
    "CVIngestRequest",
    "CVIngestResponse",
    "CareerEntry",
    "StructuredJobIntent",
    "JDExtractRequest",
    "JDExtractResponse",
    "AmbiguityWarning",
    "ScoreBreakdown",
    "MatchResult",
    "MatchRequest",
    "MatchResponse",
    "RankedShortlist",
    "ConsentRecord",
    "AccessAuditEvent",
    "ConsentCheckRequest",
    "ConsentCheckResponse",
    "GDPRFilterRequest",
    "GDPRFilterResponse",
    "DeletionRequest",
    "DeletionResponse",
    "RecruiterAction",
    "WeightUpdate",
]
