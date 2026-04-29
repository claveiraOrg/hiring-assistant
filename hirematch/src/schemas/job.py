import uuid
from datetime import datetime

from pydantic import BaseModel


class JobCreate(BaseModel):
    title: str
    description: str | None = None


class JobResponse(BaseModel):
    id: uuid.UUID
    title: str
    description: str | None
    requirements_structured: dict | None
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}
