import json
import re

import anthropic
import structlog

from src.core.config import settings

log = structlog.get_logger()

_client: anthropic.AsyncAnthropic | None = None


def get_client() -> anthropic.AsyncAnthropic:
    global _client
    if _client is None:
        _client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
    return _client


PARSE_RESUME_PROMPT = """\
You are an expert resume parser. Extract structured information from the resume text below.

Return ONLY valid JSON with this exact schema:
{
  "skills": ["skill1", "skill2"],
  "years_experience": <integer or null>,
  "education": [{"degree": "...", "field": "...", "institution": "..."}],
  "previous_roles": [{"title": "...", "company": "...", "duration_months": <integer or null>}],
  "summary": "<2-3 sentence professional summary>"
}

Resume:
{resume_text}"""

SCORE_CANDIDATE_PROMPT = """\
You are an expert technical recruiter. Score how well a candidate fits a job posting.

Job Title: {job_title}
Job Description: {job_description}
Job Requirements (structured): {requirements_json}

Candidate Resume: {resume_text}
Candidate Profile (structured): {profile_json}

Return ONLY valid JSON with this exact schema:
{
  "score": <integer 0-100>,
  "reasoning": "<2-3 sentence explanation of the score>",
  "evidence": {
    "strengths": ["strength1", "strength2"],
    "gaps": ["gap1", "gap2"]
  }
}

Score 90-100: exceptional fit. 70-89: strong fit. 50-69: moderate fit. Below 50: poor fit."""


async def parse_resume(resume_text: str) -> dict:
    """Extract structured profile from raw resume text using Claude."""
    client = get_client()
    prompt = PARSE_RESUME_PROMPT.format(resume_text=resume_text)

    response = await client.messages.create(
        model=settings.anthropic_model,
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}],
    )

    raw = response.content[0].text.strip()
    try:
        return json.loads(_extract_json(raw))
    except (json.JSONDecodeError, ValueError):
        log.warning("resume_parse_json_error", raw=raw[:200])
        return {}


async def score_candidate(
    *,
    job_title: str,
    job_description: str | None,
    requirements_structured: dict | None,
    resume_text: str | None,
    structured_profile: dict | None,
) -> dict:
    """Score a candidate against a job using Claude. Returns {score, reasoning, evidence}."""
    client = get_client()
    prompt = SCORE_CANDIDATE_PROMPT.format(
        job_title=job_title,
        job_description=job_description or "(none)",
        requirements_json=json.dumps(requirements_structured or {}),
        resume_text=resume_text or "(none)",
        profile_json=json.dumps(structured_profile or {}),
    )

    response = await client.messages.create(
        model=settings.anthropic_model,
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}],
    )

    raw = response.content[0].text.strip()
    try:
        result = json.loads(_extract_json(raw))
        score = max(0, min(100, int(result.get("score", 0))))
        return {
            "score": score,
            "reasoning": result.get("reasoning"),
            "evidence": result.get("evidence"),
            "model": settings.anthropic_model,
        }
    except (json.JSONDecodeError, ValueError, TypeError):
        log.warning("score_candidate_json_error", raw=raw[:200])
        return {"score": 0, "reasoning": "Scoring failed", "evidence": None, "model": settings.anthropic_model}


def _extract_json(text: str) -> str:
    """Pull the first {...} block from a string (handles markdown code fences)."""
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        return match.group(0)
    return text
