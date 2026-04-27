import uuid
from datetime import datetime
from typing import Optional
from sqlalchemy import String, DateTime, Text, func
from sqlalchemy.orm import Mapped, mapped_column
from app.db.session import Base


class ConsentRecord(Base):
    __tablename__ = "consent_records"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    candidate_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    granted_by_user_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    scope: Mapped[str] = mapped_column(Text, nullable=False)
    req_id: Mapped[Optional[uuid.UUID]] = mapped_column(nullable=True)
    granted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    revoked_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)


class AccessLog(Base):
    __tablename__ = "access_logs"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    candidate_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    accessed_by_user_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    req_id: Mapped[Optional[uuid.UUID]] = mapped_column(nullable=True)
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    accessed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
