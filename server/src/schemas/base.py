from __future__ import annotations

from enum import Enum
from pydantic import BaseModel, ConfigDict, Field
from uuid import UUID
from datetime import datetime


class SeniorityLevel(str, Enum):
    """Seniority classification for both candidates and job requirements."""
    JUNIOR = "junior"
    MID = "mid"
    SENIOR = "senior"
    STAFF = "staff"
    PRINCIPAL = "principal"
    EXECUTIVE = "executive"


class MatchConfidence(str, Enum):
    """Confidence level of a candidate-job match."""
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class GDPRConsentStatus(str, Enum):
    """Lifecycle states for a candidate's data consent."""
    GRANTED = "granted"
    REVOKED = "revoked"
    PENDING = "pending"
    EXPIRED = "expired"


class BaseSchema(BaseModel):
    """Base schema with common fields."""

    model_config = ConfigDict(
        arbitrary_types_allowed=True,
    )
