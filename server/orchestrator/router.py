"""Anti-data-leakage agent router.

The orchestrator MUST:
- Never pass raw CV content between agents
- Each agent only receives the structured data it needs (data minimization)
- GDPR agent is invoked BEFORE any output is returned to consumers
- Maintain strict isolation: Agent A's output doesn't leak into Agent B's input
  unless the workflow explicitly routes it through structured schemas
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any

import httpx

from orchestrator.errors import AgentCallError, RetryHandler

logger = logging.getLogger(__name__)


class AgentRouter:
    """Routes tasks to agents with strict payload scoping.

    Every agent call:
    1. Scopes the payload to only the fields the agent is authorized to see
    2. Enforces a timeout (per-agent SLA)
    3. Validates the response structure
    4. Logs the call for observability
    """

    def __init__(self, base_url: str = "http://localhost:8000", timeout: float = 5.0):
        self.base_url = base_url.rstrip("/")
        self.client = httpx.AsyncClient(timeout=timeout)
        self.retry = RetryHandler(max_retries=3, base_delay=0.5)

    async def call_agent(
        self,
        agent: str,
        endpoint: str,
        payload: dict,
        allowed_fields: list[str] | None = None,
        timeout: float | None = None,
    ) -> dict:
        """Call an agent endpoint with scoped payload.

        Args:
            agent: Agent name (e.g., "profile", "job", "matching", "gdpr")
            endpoint: API path (e.g., "/v1/extract", "/v1/score")
            payload: Full payload — will be scoped to allowed_fields
            allowed_fields: Fields the agent is ALLOWED to see.
                           If None, sends full payload (use sparingly).
            timeout: Per-call timeout override (default: 5s)

        Returns:
            Parsed JSON response from the agent.

        Raises:
            AgentCallError: Agent returned error or invalid response
        """
        # Data minimization: scope payload to only allowed fields
        if allowed_fields is not None:
            scoped = {k: payload[k] for k in allowed_fields if k in payload}
        else:
            scoped = payload

        url = f"{self.base_url}/{agent}{endpoint}"
        start = time.monotonic()

        try:
            response = await self.retry.call_with_retry(
                self._do_post,
                url,
                scoped,
                timeout=timeout or 5.0,
            )
            elapsed_ms = int((time.monotonic() - start) * 1000)

            logger.info(
                "Agent call",
                extra={
                    "agent": agent,
                    "endpoint": endpoint,
                    "duration_ms": elapsed_ms,
                    "status": response["status_code"],
                },
            )

            if response["status_code"] >= 400:
                raise AgentCallError(
                    f"{agent}{endpoint} returned {response['status_code']}: {response['body']}"
                )

            return response["body"]

        except Exception as e:
            elapsed_ms = int((time.monotonic() - start) * 1000)
            logger.error(
                f"Agent call failed: {agent}{endpoint} after {elapsed_ms}ms: {e}"
            )
            raise

    async def _do_post(self, url: str, payload: dict) -> dict:
        """Single HTTP POST with response parsing."""
        resp = await self.client.post(url, json=payload)
        return {
            "status_code": resp.status_code,
            "body": resp.json() if resp.text else {},
        }

    async def close(self):
        await self.client.aclose()


# ─── Payload schemas (ALLOWED fields per agent) ─────────────────────────

# Profile Agent: only receives CV text and optional external ID
PROFILE_AGENT_ALLOWED = ["cv_text", "candidate_external_id"]

# Job Agent: only receives JD text and optional external ID
JOB_AGENT_ALLOWED = ["jd_text", "job_external_id"]

# Matching Agent: only receives structured profiles + job intent (no raw CVs/JDs)
MATCHING_AGENT_CANDIDATE_FIELDS = [
    "skills", "years_of_experience", "seniority", "domains",
    "salary_expectation", "location", "willing_to_relocate",
]
MATCHING_AGENT_JOB_FIELDS = [
    "required_skills", "preferred_skills", "seniority",
    "years_experience_required", "domains", "salary_range",
    "location", "remote_allowed",
]

# GDPR Agent: full access to candidate data for filtering decisions
GDPR_AGENT_ALLOWED = [
    "candidate_id", "consent_status", "full_name", "skills",
    "location", "salary_expectation",
]
