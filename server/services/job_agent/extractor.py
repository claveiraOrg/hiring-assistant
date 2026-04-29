"""Job Intelligence Agent — LLM Extraction Engine.

Converts free-text job descriptions into structured StructuredJobIntent with:
- Required/preferred skills, seniority, constraints, salary range
- Ambiguity and inconsistency detection
- Confidence scoring
"""

from __future__ import annotations

import json
import logging
import os
import re
from datetime import datetime
from typing import Any
from uuid import UUID

from src.schemas import SeniorityLevel, StructuredJobIntent, AmbiguityWarning

logger = logging.getLogger(__name__)


# ─── System Prompt ──────────────────────────────────────────────────────

JD_EXTRACTION_PROMPT = """You are a job description parsing engine. Extract structured information from the following job description.

Extract ALL of the following fields. If a field cannot be determined, set it to null.
Also detect any AMBIGUITIES or INCONSISTENCIES in the job description.

Return ONLY valid JSON with these exact fields:
{
  "title": "string",
  "required_skills": ["skill1", ...],
  "preferred_skills": ["skill1", ...] or [],
  "seniority": "junior" | "mid" | "senior" | "staff" | "principal" | "executive" or null,
  "years_experience_required": integer or null,
  "domains": ["domain1", ...] or [],
  "salary_min": float or null,
  "salary_max": float or null,
  "location": "string or null",
  "remote_allowed": true | false | null,
  "confidence_score": 0.0-1.0,
  "ambiguities": [
    {
      "field": "string",
      "description": "Description of the ambiguity or inconsistency",
      "severity": "info" | "warning" | "error"
    }
  ]
}

Ambiguity Detection Rules:
- "Senior role, 1 year experience required" → field: "years_experience_required", severity: "warning"
- "Remote" + "Must work in office 5 days/week" → field: "remote_allowed", severity: "error"
- Missing salary range → field: "salary_range", severity: "info"
- Conflicting seniority signals → field: "seniority", severity: "warning"
- "Entry-level" + "5 years required" → field: "seniority", severity: "error"
- Vague skill descriptions ("knowledge of") → field: "required_skills", severity: "info"

JOB DESCRIPTION:
{jd_text}

JSON:"""


# ─── Job LLM Client ────────────────────────────────────────────────────

class JobLLMClient:
    """Abstraction over OpenAI/Claude API for job description extraction."""

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        provider: str = "openai",
        timeout: float = 10.0,
    ):
        self.api_key = api_key or os.getenv("LLM_API_KEY", "")
        self.model = model or os.getenv("LLM_MODEL", "gpt-4o")
        self.provider = provider
        self.timeout = timeout

    async def extract(self, jd_text: str) -> tuple[dict[str, Any], float]:
        """Extract structured job intent from job description text.

        Returns:
            Tuple of (parsed_job_dict, elapsed_seconds)
        """
        import time
        start = time.monotonic()

        try:
            result = await self._call_llm(JD_EXTRACTION_PROMPT.format(jd_text=jd_text[:10000]))
            elapsed = time.monotonic() - start
            parsed = self._parse_response(result)
            return parsed, elapsed

        except Exception as e:
            elapsed = time.monotonic() - start
            logger.warning(f"JD extraction failed after {elapsed:.1f}s: {e}")
            raise

    async def _call_llm(self, formatted_prompt: str) -> str:
        if self.provider == "openai":
            return await self._call_openai(formatted_prompt)
        elif self.provider == "claude":
            return await self._call_claude(formatted_prompt)
        else:
            raise ValueError(f"Unsupported provider: {self.provider}")

    async def _call_openai(self, prompt: str) -> str:
        from openai import AsyncOpenAI
        client = AsyncOpenAI(api_key=self.api_key, timeout=self.timeout)
        response = await client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": "You are a job description parser. Return only valid JSON."},
                {"role": "user", "content": prompt},
            ],
            response_format={"type": "json_object"},
            temperature=0.1,
            max_tokens=2000,
        )
        return response.choices[0].message.content or "{}"

    async def _call_claude(self, prompt: str) -> str:
        from anthropic import AsyncAnthropic
        client = AsyncAnthropic(api_key=self.api_key, timeout=self.timeout)
        response = await client.messages.create(
            model=self.model or "claude-sonnet-4-20250514",
            max_tokens=2000,
            temperature=0.1,
            system="You are a job description parser. Return only valid JSON.",
            messages=[{"role": "user", "content": prompt}],
        )
        return response.content[0].text

    def _parse_response(self, raw: str) -> dict[str, Any]:
        text = raw.strip()
        text = re.sub(r'^```(?:json)?\s*', '', text)
        text = re.sub(r'\s*```$', '', text)
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            match = re.search(r'\{.*\}', text, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group())
                except json.JSONDecodeError:
                    pass
            raise ValueError(f"Failed to parse LLM response as JSON: {text[:200]}")


# ─── Job Intent Builder ─────────────────────────────────────────────────

class JobIntentBuilder:
    """Converts raw LLM output to validated StructuredJobIntent."""

    SENIORITY_MAP = {
        "junior": SeniorityLevel.JUNIOR,
        "mid": SeniorityLevel.MID,
        "senior": SeniorityLevel.SENIOR,
        "staff": SeniorityLevel.STAFF,
        "principal": SeniorityLevel.PRINCIPAL,
        "executive": SeniorityLevel.EXECUTIVE,
    }

    def build(self, extracted: dict, job_id: UUID | None = None) -> tuple[StructuredJobIntent, list[AmbiguityWarning]]:
        """Build validated job intent from LLM extraction result."""
        seniority_str = (extracted.get("seniority") or "mid").lower().strip()
        seniority = self.SENIORITY_MAP.get(seniority_str, SeniorityLevel.MID)

        salary_min = extracted.get("salary_min")
        salary_max = extracted.get("salary_max")
        salary_range = None
        if salary_min is not None and salary_max is not None:
            salary_range = (float(salary_min), float(salary_max))
        elif salary_min is not None:
            salary_range = (float(salary_min), float(salary_min) * 1.3)
        elif salary_max is not None:
            salary_range = (float(salary_max) * 0.7, float(salary_max))

        # Build ambiguity warnings
        ambiguities = []
        for amb in extracted.get("ambiguities", []):
            if isinstance(amb, dict):
                ambiguities.append(AmbiguityWarning(
                    field=amb.get("field", "unknown"),
                    description=amb.get("description", ""),
                    severity=amb.get("severity", "info"),
                ))

        job = StructuredJobIntent(
            job_id=job_id or extracted.get("job_id"),
            title=extracted.get("title", "Unknown Position"),
            required_skills=extracted.get("required_skills", []),
            preferred_skills=extracted.get("preferred_skills", []),
            seniority=seniority,
            years_experience_required=extracted.get("years_experience_required") or 0,
            domains=extracted.get("domains", []),
            salary_range=salary_range,
            location=extracted.get("location"),
            remote_allowed=extracted.get("remote_allowed", False),
            confidence_score=min(1.0, max(0.0, extracted.get("confidence_score", 0.5))),
            created_at=extracted.get("created_at") or datetime.utcnow(),
        )

        return job, ambiguities

    @staticmethod
    def extract_ambiguities_local(jd_text: str) -> list[AmbiguityWarning]:
        """Client-side ambiguity checks (runs alongside LLM extraction).

        Catches additional inconsistencies the LLM might miss.
        """
        warnings = []
        text_lower = jd_text.lower()

        # Check for seniority vs experience mismatch
        seniority_keywords = {
            "junior": ["junior", "entry", "graduate", "intern"],
            "senior": ["senior", "lead", "principal", "staff"],
        }
        has_junior = any(kw in text_lower for kw in seniority_keywords["junior"])
        has_senior = any(kw in text_lower for kw in seniority_keywords["senior"])

        if has_junior and has_senior:
            warnings.append(AmbiguityWarning(
                field="seniority",
                description="Both junior and senior keywords detected — conflicting seniority levels",
                severity="warning",
            ))

        # Check for remote vs on-site conflict
        remote_positive = ["remote", "work from home", "wfh", "distributed"]
        on_site_positive = ["on-site", "in office", "on site", "office-based", "must be in"]
        has_remote = any(kw in text_lower for kw in remote_positive)
        has_on_site = any(kw in text_lower for kw in on_site_positive)

        if has_remote and has_on_site:
            warnings.append(AmbiguityWarning(
                field="remote_allowed",
                description="Both remote and on-site requirements detected",
                severity="error",
            ))

        # Check for salary mention
        salary_patterns = [r"£\d+k", r"\$\d+k", r"€\d+k", r"£\d+,\d+", r"\$\d+,\d+"]
        has_salary = any(re.search(p, jd_text, re.IGNORECASE) for p in salary_patterns)
        if not has_salary:
            warnings.append(AmbiguityWarning(
                field="salary_range",
                description="No salary range mentioned in job description",
                severity="info",
            ))

        return warnings
