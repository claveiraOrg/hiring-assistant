import uuid
from datetime import datetime
from sqlalchemy import String, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column
from app.db.session import Base


class HiringManagerDecision(Base):
    __tablename__ = "hiring_manager_decisions"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    req_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    candidate_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    decided_by_user_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    action: Mapped[str] = mapped_column(String(50), nullable=False)  # advance | hold | pass
    decided_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
