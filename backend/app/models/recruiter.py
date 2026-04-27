import uuid
from datetime import datetime
from typing import Optional
from sqlalchemy import String, DateTime, func
from sqlalchemy.dialects.postgresql import JSONB, ARRAY
from sqlalchemy import Text
from sqlalchemy.orm import Mapped, mapped_column
from app.db.session import Base


class RecruiterFingerprint(Base):
    __tablename__ = "recruiter_fingerprints"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(unique=True, nullable=False)
    seniority_expectation: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    archetype: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    risk_tolerance: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    domain_preferences: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True)
    skill_weighting_bias: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True)
    rejection_patterns: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True)
    rerank_prompts: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True)
    last_reset_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    last_nudge_sent_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class RecruiterSignal(Base):
    __tablename__ = "recruiter_signals"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    req_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    candidate_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    kind: Mapped[str] = mapped_column(String(50), nullable=False)
    rejection_reason: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    rerank_prompt: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class SessionMemory(Base):
    __tablename__ = "session_memory"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    req_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    rerank_prompts: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True)
    rejection_patterns: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
