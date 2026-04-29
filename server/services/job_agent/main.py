"""Job Intelligence Agent — FastAPI service.

Provides:
- POST /v1/extract — Extract structured job intent from JD text
- GET  /health     — Health check
"""

from __future__ import annotations

import logging
from datetime import datetime
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from services.job_agent.extractor import JobIntentBuilder, JobLLMClient
from src.schemas import StructuredJobIntent, AmbiguityWarning

logger = logging.getLogger(__name__)

app = FastAPI(
    title="Job Intelligence Agent",
    version="0.1.0",
    description="Converts job descriptions to structured job intent with ambiguity detection",
)

llm_client = JobLLMClient()
builder = JobIntentBuilder()


class JDExtractRequest(BaseModel):
    jd_text: str
    job_external_id: str | None = None


class JDExtractResponse(BaseModel):
    job: StructuredJobIntent
    ambiguities: list[AmbiguityWarning]
    processing_time_ms: int
    source: str = "llm"


@app.get("/health")
async def health():
    return {"status": "ok", "service": "job-agent", "version": "0.1.0"}


@app.post("/v1/extract", response_model=JDExtractResponse)
async def extract_job(request: JDExtractRequest):
    """Convert job description to structured job intent with ambiguity detection."""
    if not request.jd_text.strip():
        raise HTTPException(400, "jd_text must not be empty")

    try:
        # Step 1: LLM extraction
        raw_job, elapsed = await llm_client.extract(request.jd_text)

        # Step 2: Build validated job intent
        job_id = uuid4()
        raw_job["job_id"] = job_id
        raw_job["created_at"] = datetime.utcnow()

        job, llm_ambiguities = builder.build(raw_job, job_id)

        # Step 3: Local ambiguity detection (catches what LLM might miss)
        local_ambiguities = builder.extract_ambiguities_local(request.jd_text)

        # Step 4: Merge ambiguities (deduplicate by field + description)
        all_ambiguities = _merge_ambiguities(llm_ambiguities + local_ambiguities)

        elapsed_ms = int(elapsed * 1000)

        logger.info(
            f"Job extracted: {job.title}, "
            f"skills={len(job.required_skills)}, ambiguities={len(all_ambiguities)}, "
            f"time={elapsed_ms}ms"
        )

        return JDExtractResponse(
            job=job,
            ambiguities=all_ambiguities,
            processing_time_ms=elapsed_ms,
            source="llm",
        )

    except ImportError:
        logger.warning("LLM client not available, using rule-based fallback")
        return await _fallback_extract(request.jd_text)

    except Exception as e:
        logger.error(f"JD extraction failed: {e}")
        return await _fallback_extract(request.jd_text)


async def _fallback_extract(jd_text: str) -> JDExtractResponse:
    """Rule-based fallback when LLM is unavailable."""
    job = StructuredJobIntent(
        job_id=uuid4(),
        title="Unknown Position",
        required_skills=_extract_keywords(jd_text),
        seniority="mid",
        domains=[],
        confidence_score=0.15,
        created_at=datetime.utcnow(),
    )
    return JDExtractResponse(
        job=job,
        ambiguities=[AmbiguityWarning(
            field="general",
            description="Fallback extraction used — confidence is low",
            severity="warning",
        )],
        processing_time_ms=50,
        source="fallback",
    )


def _extract_keywords(text: str) -> list[str]:
    """Simple keyword extraction fallback."""
    common = [
        "python", "java", "javascript", "typescript", "go", "rust",
        "sql", "aws", "docker", "kubernetes", "react", "node",
        "machine learning", "data science", "agile",
    ]
    text_lower = text.lower()
    return [s for s in common if s in text_lower]


def _merge_ambiguities(ambiguities: list[AmbiguityWarning]) -> list[AmbiguityWarning]:
    """Deduplicate ambiguity warnings by (field, description)."""
    seen = set()
    unique = []
    for a in ambiguities:
        key = (a.field, a.description)
        if key not in seen:
            seen.add(key)
            unique.append(a)
    return unique
