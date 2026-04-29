import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.auth import ApiKeyDep
from src.core.db import get_db
from src.models.candidate import Candidate
from src.schemas.candidate import CandidateCreate, CandidateResponse
from src.services.ai_matching import parse_resume

router = APIRouter(prefix="/candidates", tags=["candidates"])


@router.post("", response_model=CandidateResponse, status_code=status.HTTP_201_CREATED)
async def create_candidate(
    body: CandidateCreate,
    _: str = ApiKeyDep,
    db: AsyncSession = Depends(get_db),
) -> CandidateResponse:
    structured = await parse_resume(body.resume_text)

    candidate = Candidate(
        name=body.name,
        email=body.email,
        resume_text=body.resume_text,
        structured_profile=structured or None,
    )
    db.add(candidate)
    await db.flush()
    await db.refresh(candidate)
    return CandidateResponse.model_validate(candidate)


@router.get("/{candidate_id}", response_model=CandidateResponse)
async def get_candidate(
    candidate_id: uuid.UUID,
    _: str = ApiKeyDep,
    db: AsyncSession = Depends(get_db),
) -> CandidateResponse:
    result = await db.execute(select(Candidate).where(Candidate.id == candidate_id))
    candidate = result.scalar_one_or_none()
    if not candidate:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Candidate not found")
    return CandidateResponse.model_validate(candidate)
