import uuid
from datetime import datetime
from typing import Optional
from sqlalchemy import String, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column
from app.db.session import Base


class ReqCandidate(Base):
    __tablename__ = "req_candidates"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    req_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    candidate_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    upload_source: Mapped[str] = mapped_column(
        String(50), default="direct_upload"
    )  # direct_upload | network_suggestion
    already_seen_by_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(nullable=True)
    added_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
