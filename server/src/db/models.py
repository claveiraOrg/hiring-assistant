"""SQLAlchemy ORM models for the hiring platform.

Maps to `hiring.*` and `audit.*` schemas in PostgreSQL.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Enum as SAEnum, Float, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import DeclarativeBase, relationship
from pgvector.sqlalchemy import Vector


class Base(DeclarativeBase):
    pass


# ─── Candidates ──────────────────────────────────────────────────────────

class CandidateORM(Base):
    __tablename__ = "candidates"
    __table_args__ = {"schema": "hiring"}

    candidate_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    external_id = Column(String, nullable=True, unique=True)
    full_name = Column(String, nullable=False)
    skills = Column(ARRAY(String), nullable=False, default=list)
    years_of_experience = Column(Float, nullable=False, default=0)
    seniority = Column(String, nullable=False)
    domains = Column(ARRAY(String), nullable=False, default=list)
    career_trajectory = Column(JSON, nullable=False, default=list)
    salary_expectation = Column(Float, nullable=True)
    location = Column(String, nullable=True)
    willing_to_relocate = Column(Boolean, default=False)
    embedding = Column(Vector(384), nullable=True)
    confidence_score = Column(Float, nullable=False, default=0.0)
    raw_cv_s3_key = Column(String, nullable=True)
    consent_status = Column(String, nullable=False, default="pending")
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    consent = relationship("ConsentORM", back_populates="candidate", uselist=False)


# ─── Jobs ────────────────────────────────────────────────────────────────

class JobORM(Base):
    __tablename__ = "jobs"
    __table_args__ = {"schema": "hiring"}

    job_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    external_id = Column(String, nullable=True, unique=True)
    title = Column(String, nullable=False)
    required_skills = Column(ARRAY(String), nullable=False, default=list)
    preferred_skills = Column(ARRAY(String), nullable=False, default=list)
    seniority = Column(String, nullable=False)
    years_experience_required = Column(Integer, nullable=False, default=0)
    domains = Column(ARRAY(String), nullable=False, default=list)
    salary_min = Column(Float, nullable=True)
    salary_max = Column(Float, nullable=True)
    location = Column(String, nullable=True)
    remote_allowed = Column(Boolean, default=False)
    embedding = Column(Vector(384), nullable=True)
    raw_jd_s3_key = Column(String, nullable=True)
    confidence_score = Column(Float, nullable=False, default=0.0)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)


# ─── Matches ─────────────────────────────────────────────────────────────

class MatchORM(Base):
    __tablename__ = "matches"
    __table_args__ = {"schema": "hiring"}

    match_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_id = Column(UUID(as_uuid=True), ForeignKey("hiring.jobs.job_id"), nullable=False)
    candidate_id = Column(UUID(as_uuid=True), ForeignKey("hiring.candidates.candidate_id"), nullable=False)
    overall_score = Column(Float, nullable=False)
    confidence = Column(String, nullable=False)
    skills_score = Column(Float, nullable=False, default=0.0)
    experience_score = Column(Float, nullable=False, default=0.0)
    domain_score = Column(Float, nullable=False, default=0.0)
    salary_fit_score = Column(Float, nullable=False, default=0.0)
    location_fit_score = Column(Float, nullable=False, default=0.0)
    explanation = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)


# ─── Consent ─────────────────────────────────────────────────────────────

class ConsentORM(Base):
    __tablename__ = "consent"
    __table_args__ = {"schema": "hiring"}

    consent_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    candidate_id = Column(UUID(as_uuid=True), ForeignKey("hiring.candidates.candidate_id"), nullable=False, unique=True)
    status = Column(String, nullable=False, default="pending")
    granted_at = Column(DateTime, nullable=True)
    revoked_at = Column(DateTime, nullable=True)
    expires_at = Column(DateTime, nullable=True)
    data_scope = Column(ARRAY(String), nullable=False, default=list)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    candidate = relationship("CandidateORM", back_populates="consent")


# ─── Audit Trail ─────────────────────────────────────────────────────────

class AccessAuditORM(Base):
    __tablename__ = "access_audit"
    __table_args__ = {"schema": "audit"}

    event_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    timestamp = Column(DateTime, nullable=False, default=datetime.utcnow)
    actor_id = Column(String, nullable=False)
    action = Column(String, nullable=False)
    resource_type = Column(String, nullable=False)
    resource_id = Column(UUID(as_uuid=True), nullable=False)
    granted = Column(Boolean, nullable=False)
    reason = Column(String, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)


# ─── Feedback / Weight Adjustments (Phase 2) ────────────────────────────

class RecruiterActionORM(Base):
    __tablename__ = "recruiter_actions"
    __table_args__ = {"schema": "hiring"}

    action_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    recruiter_id = Column(String, nullable=False)
    candidate_id = Column(UUID(as_uuid=True), ForeignKey("hiring.candidates.candidate_id"), nullable=False)
    job_id = Column(UUID(as_uuid=True), ForeignKey("hiring.jobs.job_id"), nullable=False)
    action = Column(String, nullable=False)
    timestamp = Column(DateTime, nullable=False, default=datetime.utcnow)
