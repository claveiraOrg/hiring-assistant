"""Matching Agent — FastAPI service.

Provides:
- POST /score — score one candidate-job pair
- POST /batch-score — batch inference over multiple candidates
- GET  /health — health check
"""

from __future__ import annotations

import logging
import time
from uuid import UUID, uuid4

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from services.matching_agent.matcher import batch_score, score_match
from src.schemas import CandidateProfile, MatchConfidence, MatchResult, RankedShortlist, ScoreBreakdown, StructuredJobIntent

logger = logging.getLogger(__name__)

app = FastAPI(
    title="Matching Agent",
    version="0.1.0",
    description="Computes candidate-job relevance scores with explainability",
)


# ─── Request/Response schemas ────────────────────────────────────────────

class ScoreRequest(BaseModel):
    candidate: CandidateProfile
    job: StructuredJobIntent


class BatchScoreRequest(BaseModel):
    candidates: list[CandidateProfile]
    job: StructuredJobIntent


@app.get("/health")
async def health():
    return {"status": "ok", "service": "matching-agent", "version": "0.1.0"}


@app.post("/v1/score")
async def score_endpoint(request: ScoreRequest) -> dict:
    """Score a single candidate-job pair with full breakdown."""
    start = time.monotonic()
    result = score_match(request.candidate, request.job)
    elapsed_ms = int((time.monotonic() - start) * 1000)
    return {
        "match": result,
        "processing_time_ms": elapsed_ms,
    }


@app.post("/v1/batch-score")
async def batch_score_endpoint(request: BatchScoreRequest) -> dict:
    """Batch score all candidates against one job."""
    start = time.monotonic()
    results = batch_score(request.candidates, request.job)
    elapsed_ms = int((time.monotonic() - start) * 1000)
    return {
        "matches": results,
        "total_scored": len(results),
        "processing_time_ms": elapsed_ms,
    }
