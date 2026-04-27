import uuid
from datetime import datetime
from typing import Optional
from sqlalchemy import String, DateTime, Float, Text, func, Index
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from pgvector.sqlalchemy import Vector
from app.db.session import Base


class Candidate(Base):
    __tablename__ = "candidates"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    file_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)  # SHA-256
    visibility: Mapped[str] = mapped_column(
        String(50), default="anonymous"
    )  # anonymous | consent_pending | visible
    consent_scope: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    extraction_status: Mapped[str] = mapped_column(
        String(50), default="pending"
    )  # pending | complete | failed
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)


class CandidateProfile(Base):
    __tablename__ = "candidate_profiles"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    candidate_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    raw_text: Mapped[str] = mapped_column(Text, nullable=False)
    extraction_confidence: Mapped[float] = mapped_column(Float, nullable=False)
    structured: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    structured_raw: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    extraction_model: Mapped[str] = mapped_column(String(100), nullable=False)
    extraction_prompt_version: Mapped[str] = mapped_column(String(50), nullable=False)
    synonym_map_version: Mapped[str] = mapped_column(String(50), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class CandidateEmbedding(Base):
    __tablename__ = "candidate_embeddings"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    candidate_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    embedding: Mapped[list[float]] = mapped_column(Vector(1536), nullable=False)
    model_version: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index(
            "ix_candidate_embeddings_ivfflat",
            "embedding",
            postgresql_using="ivfflat",
            postgresql_with={"lists": 100},
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )
