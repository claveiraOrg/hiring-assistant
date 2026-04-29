"""Error types, retry logic, and fallback handlers for the orchestrator.

Every agent call goes through retry with exponential backoff.
Timeouts are strict — each agent has a configurable SLA window.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Awaitable, Callable, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


# ─── Custom errors ──────────────────────────────────────────────────────

class OrchestratorError(Exception):
    """Base orchestrator error."""

class AgentCallError(OrchestratorError):
    """Agent returned a non-success response."""

class AgentTimeoutError(OrchestratorError):
    """Agent did not respond within the SLA window."""

class EmptyCandidatePoolError(OrchestratorError):
    """No candidates found matching the criteria."""

class GDPRAccessDenied(OrchestratorError):
    """GDPR filter blocked the data access."""

class LLMFallbackTriggered(OrchestratorError):
    """LLM extraction failed, rule-based fallback used."""


# ─── Retry handler ──────────────────────────────────────────────────────

class RetryHandler:
    """Exponential backoff retry for agent calls.

    Default: 3 retries with 0.5s/1.0s/1.5s delays.
    Total max wait = 3 seconds before giving up.
    """

    def __init__(self, max_retries: int = 3, base_delay: float = 0.5):
        self.max_retries = max_retries
        self.base_delay = base_delay

    async def call_with_retry(
        self,
        fn: Callable[..., Awaitable[T]],
        *args: Any,
        timeout: float = 5.0,
        **kwargs: Any,
    ) -> T:
        """Call an async function with retry + timeout.

        Uses exponential backoff: base_delay * (attempt + 1).
        Raises AgentTimeoutError after all retries exhausted.
        """
        last_error: Exception | None = None

        for attempt in range(self.max_retries):
            try:
                return await asyncio.wait_for(fn(*args, **kwargs), timeout=timeout)
            except asyncio.TimeoutError as e:
                last_error = AgentTimeoutError(
                    f"Timeout after {timeout}s (attempt {attempt + 1}/{self.max_retries})"
                )
                logger.warning(f"Agent call timed out (attempt {attempt + 1}): {e}")
            except Exception as e:
                last_error = e
                logger.warning(f"Agent call failed (attempt {attempt + 1}): {e}")

            if attempt < self.max_retries - 1:
                delay = self.base_delay * (attempt + 1)
                logger.info(f"Retrying in {delay}s...")
                await asyncio.sleep(delay)

        raise AgentTimeoutError(str(last_error)) from last_error


# ─── Fallback handlers ──────────────────────────────────────────────────

class FallbackHandler:
    """Graceful degradation strategies for each failure mode."""

    @staticmethod
    def on_empty_pool(job_id: str) -> dict:
        """Empty candidate pool: return empty shortlist with metadata."""
        logger.info(f"No candidates found for job {job_id}")
        return {
            "job_id": job_id,
            "matches": [],
            "total_candidates_scored": 0,
            "processing_time_ms": 0,
            "metadata": {
                "message": "No candidates found with matching criteria and active consent",
                "action": "notify_recruiters_to_source",
            },
        }

    @staticmethod
    def on_llm_failure(cv_text: str | None = None) -> dict:
        """LLM extraction failure: return minimal rule-based profile."""
        logger.warning("LLM extraction failed, using rule-based fallback")
        # Simple fallback: extract email-like patterns, common skills
        return {
            "full_name": "Unknown",
            "skills": _extract_common_skills(cv_text or ""),
            "years_of_experience": 0,
            "seniority": "mid",
            "domains": [],
            "confidence_score": 0.15,  # low confidence — flag for review
            "fallback": True,
        }

    @staticmethod
    def on_gdpr_denial(candidate_id: str, recruiter_id: str) -> dict:
        """GDPR denied: return error with audit trail metadata."""
        return {
            "error": "Candidate data not available",
            "code": "CONSENT_DENIED",
            "candidate_id": candidate_id,
            "recruiter_id": recruiter_id,
        }


def _extract_common_skills(text: str) -> list[str]:
    """Simple keyword-based skill extraction fallback."""
    common_skills = [
        "python", "java", "javascript", "typescript", "go", "rust",
        "sql", "aws", "docker", "kubernetes", "react", "node",
        "machine learning", "data science", "product management",
        "agile", "leadership", "communication",
    ]
    text_lower = text.lower()
    return [s for s in common_skills if s in text_lower]
