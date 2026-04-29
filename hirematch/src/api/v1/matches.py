import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.auth import ApiKeyDep
from src.core.db import get_db
from src.models.candidate import Candidate
from src.models.job_posting import JobPosting
from src.models.match_score import MatchScore
from src.schemas.match import (
    MatchRequest,
    MatchResponse,
    MatchResult,
    RankedCandidate,
    RankedCandidatesResponse,
)
from src.services.ai_matching import score_candidate

router = APIRouter(tags=["matches"])


@router.post("/match", response_model=MatchResponse)
async def trigger_match(
    body: MatchRequest,
    _: str = ApiKeyDep,
    db: AsyncSession = Depends(get_db),
) -> MatchResponse:
    """Trigger AI matching for the given job and candidate list."""
    job_result = await db.execute(select(JobPosting).where(JobPosting.id == body.job_id))
    job = job_result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")

    results: list[MatchResult] = []

    for cid in body.candidate_ids:
        cand_result = await db.execute(select(Candidate).where(Candidate.id == cid))
        candidate = cand_result.scalar_one_or_none()
        if not candidate:
            continue

        scored = await score_candidate(
            job_title=job.title,
            job_description=job.description,
            requirements_structured=job.requirements_structured,
            resume_text=candidate.resume_text,
            structured_profile=candidate.structured_profile,
        )

        existing_result = await db.execute(
            select(MatchScore).where(
                MatchScore.job_id == body.job_id, MatchScore.candidate_id == cid
            )
        )
        ms = existing_result.scalar_one_or_none()
        if ms:
            ms.score = scored["score"]
            ms.reasoning = scored["reasoning"]
            ms.evidence = scored["evidence"]
            ms.model = scored["model"]
        else:
            ms = MatchScore(
                job_id=body.job_id,
                candidate_id=cid,
                score=scored["score"],
                reasoning=scored["reasoning"],
                evidence=scored["evidence"],
                model=scored["model"],
            )
            db.add(ms)

        results.append(
            MatchResult(
                candidate_id=cid,
                score=scored["score"],
                reasoning=scored["reasoning"],
                evidence=scored["evidence"],
            )
        )

    await db.flush()
    results.sort(key=lambda r: r.score, reverse=True)
    return MatchResponse(job_id=body.job_id, results=results)


@router.get("/matches/{job_id}", response_model=RankedCandidatesResponse)
async def get_matches(
    job_id: uuid.UUID,
    _: str = ApiKeyDep,
    db: AsyncSession = Depends(get_db),
) -> RankedCandidatesResponse:
    """Retrieve ranked candidates for a job, ordered by match score descending."""
    job_result = await db.execute(select(JobPosting).where(JobPosting.id == job_id))
    if not job_result.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")

    scores_result = await db.execute(
        select(MatchScore, Candidate)
        .join(Candidate, Candidate.id == MatchScore.candidate_id)
        .where(MatchScore.job_id == job_id)
        .order_by(MatchScore.score.desc())
    )
    rows = scores_result.all()

    candidates = [
        RankedCandidate(
            candidate_id=ms.candidate_id,
            name=cand.name,
            email=cand.email,
            score=ms.score,
            reasoning=ms.reasoning,
            evidence=ms.evidence,
            matched_at=ms.created_at,
        )
        for ms, cand in rows
    ]
    return RankedCandidatesResponse(job_id=job_id, candidates=candidates)
