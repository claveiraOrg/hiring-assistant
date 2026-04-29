import uuid
from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from src.core.db import Base


class JobPosting(Base):
    __tablename__ = "job_postings"

    id: Mapped[uuid.UUID] = mapped_column(sa.Uuid, primary_key=True, default=uuid.uuid4)
    title: Mapped[str] = mapped_column(sa.String(500), nullable=False)
    description: Mapped[str | None] = mapped_column(sa.Text)
    requirements_structured: Mapped[dict | None] = mapped_column(sa.JSON)
    status: Mapped[str] = mapped_column(sa.String(50), default="active", index=True)
    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
