import uuid
from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from src.core.db import Base


class MatchScore(Base):
    __tablename__ = "match_scores"

    id: Mapped[uuid.UUID] = mapped_column(sa.Uuid, primary_key=True, default=uuid.uuid4)
    job_id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid, sa.ForeignKey("job_postings.id", ondelete="CASCADE"), nullable=False, index=True
    )
    candidate_id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid, sa.ForeignKey("candidates.id", ondelete="CASCADE"), nullable=False, index=True
    )
    score: Mapped[int] = mapped_column(sa.Integer, nullable=False)  # 0-100
    reasoning: Mapped[str | None] = mapped_column(sa.Text)
    evidence: Mapped[dict | None] = mapped_column(sa.JSON)  # {strengths: [], gaps: []}
    model: Mapped[str | None] = mapped_column(sa.Text)
    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=func.now())
