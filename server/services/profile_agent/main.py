"""Profile Intelligence Agent — FastAPI service.

Provides:
- POST /v1/extract — Extract structured profile from CV text
- POST /v1/embed   — Generate embedding for an existing profile
- GET  /health     — Health check
"""

from __future__ import annotations

import logging
import time
from uuid import uuid4
from datetime import datetime

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from services.profile_agent.extractor import ConfidenceScorer, EmbeddingGenerator, LLMClient
from src.schemas import CandidateProfile

logger = logging.getLogger(__name__)

app = FastAPI(
    title="Profile Intelligence Agent",
    version="0.1.0",
    description="Converts CV text to structured candidate profiles with confidence scoring",
)

# Service instances (configured at startup)
llm_client = LLMClient()
scorer = ConfidenceScorer()
embedder = EmbeddingGenerator()


# ─── Request/Response schemas ───────────────────────────────────────────

class ExtractRequest(BaseModel):
    cv_text: str
    candidate_external_id: str | None = None


class ExtractResponse(BaseModel):
    profile: CandidateProfile
    processing_time_ms: int
    source: str = "llm"  # "llm" or "fallback"


class EmbedRequest(BaseModel):
    profile: CandidateProfile


class EmbedResponse(BaseModel):
    embedding: list[float]
    processing_time_ms: int


# ─── Endpoints ──────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    return {"status": "ok", "service": "profile-agent", "version": "0.1.0"}


@app.post("/v1/extract", response_model=ExtractResponse)
async def extract_profile(request: ExtractRequest):
    """Convert CV text to structured candidate profile.

    Uses LLM for extraction with fallback to rule-based extraction.
    Returns the profile with confidence score and processing time.
    """
    if not request.cv_text.strip():
        raise HTTPException(400, "cv_text must not be empty")

    try:
        # Step 1: LLM extraction
        raw_profile, elapsed = await llm_client.extract(request.cv_text)

        # Step 2: Convert to validated CandidateProfile
        raw_profile["candidate_id"] = uuid4()
        raw_profile["created_at"] = datetime.utcnow()

        profile = scorer.compute(raw_profile)

        elapsed_ms = int(elapsed * 1000)

        logger.info(
            f"Profile extracted: {profile.full_name}, "
            f"skills={len(profile.skills)}, confidence={profile.confidence_score}, "
            f"time={elapsed_ms}ms"
        )

        return ExtractResponse(
            profile=profile,
            processing_time_ms=elapsed_ms,
            source="llm",
        )

    except ImportError:
        # LLM client not installed — use rule-based fallback
        logger.warning("LLM client not available, using rule-based fallback")
        profile = await _fallback_extract(request.cv_text)
        return ExtractResponse(
            profile=profile,
            processing_time_ms=50,
            source="fallback",
        )

    except Exception as e:
        logger.error(f"Extraction failed: {e}")
        # Use fallback on any extraction error
        profile = await _fallback_extract(request.cv_text)
        return ExtractResponse(
            profile=profile,
            processing_time_ms=100,
            source="fallback",
        )


@app.post("/v1/embed", response_model=EmbedResponse)
async def generate_embedding(request: EmbedRequest):
    """Generate embedding vector for a candidate profile."""
    start = time.monotonic()
    try:
        embedding = await embedder.generate(request.profile)
        elapsed_ms = int((time.monotonic() - start) * 1000)
        return EmbedResponse(embedding=embedding, processing_time_ms=elapsed_ms)
    except Exception as e:
        logger.error(f"Embedding generation failed: {e}")
        raise HTTPException(500, f"Embedding generation failed: {e}")


# ─── Fallback extraction ────────────────────────────────────────────────

async def _fallback_extract(cv_text: str) -> CandidateProfile:
    """Rule-based fallback when LLM is unavailable."""
    from orchestrator.errors import _extract_common_skills

    # Simple keyword-based extraction
    skills = _extract_common_skills(cv_text)

    # Extract name-like patterns
    name_match = re.search(r"^([A-Z][a-z]+ [A-Z][a-z]+)", cv_text.strip())

    return CandidateProfile(
        candidate_id=uuid4(),
        full_name=name_match.group(1) if name_match else "Unknown",
        skills=skills,
        years_of_experience=0,
        seniority="mid",
        domains=[],
        career_trajectory=[],
        confidence_score=0.15,
        created_at=datetime.utcnow(),
    )


import re  # needed for fallback
