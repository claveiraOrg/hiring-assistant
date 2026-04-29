import uuid
from datetime import datetime

from pydantic import BaseModel


class MatchRequest(BaseModel):
    job_id: uuid.UUID
    candidate_ids: list[uuid.UUID]


class MatchResult(BaseModel):
    candidate_id: uuid.UUID
    score: int
    reasoning: str | None
    evidence: dict | None


class MatchResponse(BaseModel):
    job_id: uuid.UUID
    results: list[MatchResult]


class RankedCandidate(BaseModel):
    candidate_id: uuid.UUID
    name: str | None
    email: str | None
    score: int
    reasoning: str | None
    evidence: dict | None
    matched_at: datetime

    model_config = {"from_attributes": True}


class RankedCandidatesResponse(BaseModel):
    job_id: uuid.UUID
    candidates: list[RankedCandidate]
