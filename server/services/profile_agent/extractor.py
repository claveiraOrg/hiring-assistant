"""Profile Intelligence Agent — LLM Extraction Engine.

Converts raw CV text into a structured CandidateProfile with:
- Skills, seniority, domains, career trajectory
- Confidence scoring on extraction quality
- LLM system prompt for structured output

Supports:
- OpenAI / Claude API integration
- Configurable model selection
- Timeout handling (LLM failure → fallback)
"""

from __future__ import annotations

import json
import logging
import os
import re
from typing import Any

from pydantic import ValidationError

from src.schemas import CandidateProfile, CareerEntry, SeniorityLevel, GDPRConsentStatus

logger = logging.getLogger(__name__)


# ─── System Prompt ──────────────────────────────────────────────────────

CV_EXTRACTION_PROMPT = """You are a CV parsing engine. Extract structured information from the following CV text.

Extract ALL of the following fields. If a field cannot be determined, set it to null.

Return ONLY valid JSON with these exact fields:
{
  "full_name": "string or null",
  "skills": ["skill1", "skill2", ...],
  "years_of_experience": float or null,
  "seniority": "junior" | "mid" | "senior" | "staff" | "principal" | "executive" or null,
  "domains": ["domain1", ...] or [],
  "career_trajectory": [{"role": "string", "company": "string", "start_date": "YYYY-MM" or null, "end_date": "YYYY-MM" or null}],
  "salary_expectation": float or null,
  "location": "string or null",
  "willing_to_relocate": true | false | null,
  "confidence_score": 0.0-1.0,
  "confidence_breakdown": {
    "name_extracted": true | false,
    "skills_found": integer (count),
    "experience_determined": true | false,
    "seniority_determined": true | false,
    "domains_found": integer (count),
    "career_history_complete": true | false
  }
}

Rules:
- confidence_score: 0.0-1.0 based on completeness. 1.0 = all fields populated with high certainty.
  Deduct 0.1 for each missing field. Deduct 0.05 for each ambiguous field.
- skills: extract as many as you can find. Include both hard skills (Python, SQL) and soft skills (leadership).
- years_of_experience: total professional experience. Use career entries if available.
- seniority: infer from roles, years, and responsibilities.
- domains: industry sectors (FinTech, Healthcare, SaaS, etc.)
- career_trajectory: extract ALL roles with companies and dates if available.
- salary_expectation: only if explicitly stated (e.g., "£120k", "$150,000")
- location: city, country, or region. Format as "City, Country".

CV TEXT:
{cv_text}

JSON:"""


# ─── LLM Client ─────────────────────────────────────────────────────────

class LLMClient:
    """Abstraction over OpenAI/Claude API for CV extraction.

    Supports both OpenAI and Claude. Configurable via env vars.
    """

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
        self._client = None

    async def extract(self, cv_text: str, prompt: str = CV_EXTRACTION_PROMPT) -> tuple[dict[str, Any], float]:
        """Extract structured profile from CV text using LLM.

        Returns:
            Tuple of (parsed_profile_dict, elapsed_seconds)
        """
        import time
        start = time.monotonic()

        try:
            result = await self._call_llm(prompt.format(cv_text=cv_text[:10000]))
            elapsed = time.monotonic() - start

            parsed = self._parse_response(result)
            return parsed, elapsed

        except Exception as e:
            elapsed = time.monotonic() - start
            logger.warning(f"LLM extraction failed after {elapsed:.1f}s: {e}")
            raise

    async def _call_llm(self, formatted_prompt: str) -> str:
        """Call the configured LLM provider."""
        if self.provider == "openai":
            return await self._call_openai(formatted_prompt)
        elif self.provider == "claude":
            return await self._call_claude(formatted_prompt)
        else:
            raise ValueError(f"Unsupported provider: {self.provider}")

    async def _call_openai(self, prompt: str) -> str:
        """Call OpenAI API with the extraction prompt."""
        try:
            from openai import AsyncOpenAI
        except ImportError:
            logger.error("openai package not installed. Use: pip install openai")
            raise

        client = self._client or AsyncOpenAI(api_key=self.api_key, timeout=self.timeout)
        response = await client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": "You are a CV parsing engine. Return only valid JSON."},
                {"role": "user", "content": prompt},
            ],
            response_format={"type": "json_object"},
            temperature=0.1,  # Low temperature for deterministic extraction
            max_tokens=2000,
        )
        return response.choices[0].message.content or "{}"

    async def _call_claude(self, prompt: str) -> str:
        """Call Claude API with the extraction prompt."""
        try:
            from anthropic import AsyncAnthropic
        except ImportError:
            logger.error("anthropic package not installed. Use: pip install anthropic")
            raise

        client = self._client or AsyncAnthropic(api_key=self.api_key, timeout=self.timeout)
        response = await client.messages.create(
            model=self.model or "claude-sonnet-4-20250514",
            max_tokens=2000,
            temperature=0.1,
            system="You are a CV parsing engine. Return only valid JSON.",
            messages=[{"role": "user", "content": prompt}],
        )
        return response.content[0].text

    def _parse_response(self, raw: str) -> dict[str, Any]:
        """Parse LLM response, extracting JSON from markdown if needed."""
        # Try direct JSON parse first
        text = raw.strip()

        # Remove markdown code fences if present
        text = re.sub(r'^```(?:json)?\s*', '', text)
        text = re.sub(r'\s*```$', '', text)

        try:
            return json.loads(text)
        except json.JSONDecodeError:
            # Attempt to find JSON object in the response
            match = re.search(r'\{.*\}', text, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group())
                except json.JSONDecodeError:
                    pass
            raise ValueError(f"Failed to parse LLM response as JSON: {text[:200]}")


# ─── Confidence Scorer ──────────────────────────────────────────────────

class ConfidenceScorer:
    """Computes confidence scores from extraction results."""

    @staticmethod
    def compute(extracted: dict) -> CandidateProfile:
        """Convert LLM output dict to validated CandidateProfile.

        The LLM provides its own confidence_score. We also compute
        an internal quality score based on completeness.
        """
        # Map seniority string to enum
        seniority_map = {
            "junior": SeniorityLevel.JUNIOR,
            "mid": SeniorityLevel.MID,
            "senior": SeniorityLevel.SENIOR,
            "staff": SeniorityLevel.STAFF,
            "principal": SeniorityLevel.PRINCIPAL,
            "executive": SeniorityLevel.EXECUTIVE,
        }

        seniority_str = (extracted.get("seniority") or "mid").lower().strip()
        seniority = seniority_map.get(seniority_str, SeniorityLevel.MID)

        # Parse career trajectory
        trajectory = []
        for entry in extracted.get("career_trajectory") or []:
            if isinstance(entry, dict):
                trajectory.append(CareerEntry(
                    role=entry.get("role", "Unknown"),
                    company=entry.get("company", "Unknown"),
                    start_date=entry.get("start_date"),
                    end_date=entry.get("end_date"),
                ))

        # Use LLM's confidence or compute our own
        llm_confidence = extracted.get("confidence_score", 0.5)
        breakdown = extracted.get("confidence_breakdown", {})

        # Internal quality score based on field completeness
        fields_found = sum([
            1 if extracted.get("full_name") else 0,
            1 if len(extracted.get("skills", [])) > 0 else 0,
            1 if extracted.get("years_of_experience") is not None else 0,
            1 if extracted.get("seniority") else 0,
            1 if len(extracted.get("domains", [])) > 0 else 0,
        ])
        quality_score = fields_found / 5.0

        # Weighted blend: LLM confidence (60%) + our quality check (40%)
        final_confidence = round(0.6 * llm_confidence + 0.4 * quality_score, 4)
        final_confidence = max(0.0, min(1.0, final_confidence))

        # Generate embedding text
        embedding_text = " ".join([
            " ".join(extracted.get("skills", [])),
            seniority_str,
            " ".join(extracted.get("domains", [])),
            f"{extracted.get('years_of_experience', 0)} years",
        ])

        return CandidateProfile(
            candidate_id=extracted.get("candidate_id"),  # set by caller
            full_name=extracted.get("full_name") or "Unknown",
            skills=extracted.get("skills") or [],
            years_of_experience=max(0, extracted.get("years_of_experience") or 0),
            seniority=seniority,
            domains=extracted.get("domains", []),
            career_trajectory=trajectory,
            salary_expectation=extracted.get("salary_expectation"),
            location=extracted.get("location"),
            willing_to_relocate=extracted.get("willing_to_relocate", False),
            confidence_score=final_confidence,
            embedding=None,  # generated later by orchestrator
            raw_cv_s3_key=None,
            created_at=extracted.get("created_at"),
            consent_status=GDPRConsentStatus.PENDING,
        )


# ─── Embedding Generator ────────────────────────────────────────────────

class EmbeddingGenerator:
    """Generates embedding vectors for candidate profiles.

    Supports:
    - OpenAI text-embedding-3-small (default)
    - sentence-transformers (local, offline)
    """

    def __init__(self, model: str = "text-embedding-3-small", provider: str = "openai"):
        self.model = model
        self.provider = provider
        self._client = None

    async def generate(self, profile: CandidateProfile) -> list[float]:
        """Generate embedding from structured profile fields.

        The embedding text is built from skills, seniority, domains,
        and experience — a compact semantic representation for vector search.
        """
        embedding_text = "Profile of a {seniority} professional with {years} years experience in {domains}. Skills: {skills}.".format(
            seniority=profile.seniority.value,
            years=profile.years_of_experience,
            domains=", ".join(profile.domains) if profile.domains else "general",
            skills=", ".join(profile.skills) if profile.skills else "N/A",
        )

        if self.provider == "openai":
            return await self._generate_openai(embedding_text)
        else:
            return await self._generate_local(embedding_text)

    async def _generate_openai(self, text: str) -> list[float]:
        """Generate embedding via OpenAI API."""
        try:
            from openai import AsyncOpenAI
        except ImportError:
            logger.warning("openai not installed, returning zero vector")
            return [0.0] * 384

        client = self._client or AsyncOpenAI(api_key=os.getenv("LLM_API_KEY"))
        response = await client.embeddings.create(
            model=self.model,
            input=text,
        )
        return response.data[0].embedding

    async def _generate_local(self, text: str) -> list[float]:
        """Generate embedding via local sentence-transformers model."""
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError:
            logger.warning("sentence-transformers not installed, returning zero vector")
            return [0.0] * 384

        model = SentenceTransformer(self.model or "BAAI/bge-small-en-v1.5")
        embedding = model.encode(text)
        return embedding.tolist()
