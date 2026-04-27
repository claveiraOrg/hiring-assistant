import uuid
from datetime import datetime
from typing import Optional
from sqlalchemy import String, DateTime, Float, Integer, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from app.db.session import Base


class Evaluation(Base):
    __tablename__ = "evaluations"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    req_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    candidate_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    score: Mapped[int] = mapped_column(Integer, nullable=False)
    confidence_tier: Mapped[str] = mapped_column(String(50), nullable=False)  # high | medium | low
    confidence_reason: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    score_breakdown: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    evidence_bullets: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True)
    penalty_breakdown: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True)
    pairwise_rank: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    model: Mapped[str] = mapped_column(String(100), nullable=False)
    prompt_version: Mapped[str] = mapped_column(String(50), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
