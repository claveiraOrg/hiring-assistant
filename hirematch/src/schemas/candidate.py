import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr


class CandidateCreate(BaseModel):
    name: str | None = None
    email: str | None = None
    resume_text: str


class CandidateResponse(BaseModel):
    id: uuid.UUID
    name: str | None
    email: str | None
    structured_profile: dict | None
    created_at: datetime

    model_config = {"from_attributes": True}
