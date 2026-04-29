"""Matching Flow — Critical Path.

Job Request → Hermes Orchestrator → Fetch candidate pool
→ Matching Agent (batch scoring) → GDPR Agent filter
→ Ranked shortlist output

Performance: <10 seconds end-to-end.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from orchestrator.errors import (
    AgentTimeoutError,
    EmptyCandidatePoolError,
    FallbackHandler,
    GDPRAccessDenied,
)
from orchestrator.router import AgentRouter
from orchestrator.state import (
    AgentCall,
    WorkflowFactory,
    WorkflowState,
    WorkflowStatus,
)
from src.schemas import RankedShortlist

logger = logging.getLogger(__name__)


class MatchingFlow:
    """End-to-end matching workflow orchestrator.

    SLA: <10 seconds end-to-end from job request to ranked shortlist.
    The orchestrator reserves 1.5s for orchestration overhead, leaving
    8.5s for agent calls (vector search, batch scoring, GDPR filter).

    Flow:
    1. Fetch job from DB
    2. Vector similarity search for candidate pool
       (fallback: recent consented candidates)
    3. Batch scoring via Matching Agent
    4. GDPR filter on results
    5. Rank by overall_score descending
    6. Return top 50 as RankedShortlist
    """

    # Time budget (seconds)
    VECTOR_SEARCH_TIMEOUT = 2.0
    MATCHING_TIMEOUT = 4.0
    GDPR_TIMEOUT = 1.5
    OVERHEAD_BUFFER = 1.5
    TOTAL_SLA = 10.0  # Hard limit

    MAX_CANDIDATES_IN_POOL = 200
    FALLBACK_POOL_SIZE = 50
    FINAL_SHORTLIST_SIZE = 50

    def __init__(self, router: AgentRouter, candidate_repo, job_repo):
        self.router = router
        self.candidate_repo = candidate_repo
        self.job_repo = job_repo

    async def execute(self, job_id: UUID) -> dict:
        """Execute matching flow for a single job.

        Returns RankedShortlist-compatible dict.
        Raises on total failure; returns partial shortlist on degradation.
        """
        state = WorkflowFactory.new_matching(job_id)
        logger.info(f"Matching flow started: job_id={job_id}")

        try:
            # ─── Step 1: Fetch job ─────────────────────────────────────
            job = await self._fetch_job(state, job_id)
            if job is None:
                return self._fail(state, f"Job {job_id} not found")

            # ─── Step 2: Fetch candidate pool ──────────────────────────
            candidates = await self._fetch_candidate_pool(state, job)
            if not candidates:
                return self._empty_shortlist(state, job_id)

            # ─── Step 3: Batch scoring ─────────────────────────────────
            matches = await self._batch_score(state, candidates, job)

            # ─── Step 4: GDPR filter ───────────────────────────────────
            filtered = await self._gdpr_filter(state, matches)

            # ─── Step 5: Rank + return ─────────────────────────────────
            shortlist = self._rank_and_build(state, job_id, filtered, candidates)

            state.status = WorkflowStatus.SUCCEEDED
            state.completed_at = datetime.utcnow()
            logger.info(
                f"Matching flow succeeded: job_id={job_id}, "
                f"pool={len(candidates)}, scored={len(matches)}, "
                f"shortlist={len(shortlist['matches'])}, "
                f"elapsed={state.elapsed_ms()}ms"
            )
            return shortlist

        except AgentTimeoutError as e:
            state.status = WorkflowStatus.TIMED_OUT
            state.errors.append({"error": str(e), "timestamp": str(datetime.utcnow())})
            state.completed_at = datetime.utcnow()
            logger.error(f"Matching flow timed out: {e}")
            return self._partial_shortlist(
                state, job_id, "Matching timed out — partial results may be available"
            )

        except Exception as e:
            state.status = WorkflowStatus.FAILED
            state.errors.append({
                "error": str(e),
                "timestamp": str(datetime.utcnow()),
            })
            state.completed_at = datetime.utcnow()
            logger.exception(f"Matching flow failed: {e}")
            raise

    async def _fetch_job(self, state: WorkflowState, job_id: UUID):
        """Fetch job from DB with tracking."""
        call = AgentCall(agent_name="job_repo", started_at=datetime.utcnow())
        try:
            job_orm = await self.job_repo.get_by_id(job_id)
            call.completed_at = datetime.utcnow()
            call.success = job_orm is not None
            state.agent_calls.append(call)
            return job_orm
        except Exception as e:
            call.completed_at = datetime.utcnow()
            call.success = False
            call.error = str(e)
            state.agent_calls.append(call)
            raise

    async def _fetch_candidate_pool(self, state: WorkflowState, job: Any) -> list[dict]:
        """Vector similarity search with fallback logic.

        Primary: pgvector ANN search using job embedding.
        Fallback: most recent consented candidates.
        """
        call = AgentCall(agent_name="vector_search", started_at=datetime.utcnow())

        try:
            embedding = job.embedding if hasattr(job, "embedding") else None

            if embedding:
                candidates = await asyncio.wait_for(
                    self.candidate_repo.search_by_embedding(
                        embedding, limit=self.MAX_CANDIDATES_IN_POOL
                    ),
                    timeout=self.VECTOR_SEARCH_TIMEOUT,
                )
                if candidates:
                    call.success = True
                    call.completed_at = datetime.utcnow()
                    state.agent_calls.append(call)
                    logger.info(f"Vector search: {len(candidates)} candidates found")
                    return self._orms_to_dicts(candidates)

            # Fallback
            logger.info("Vector search returned empty or unavailable; using fallback")
            candidates = await self.candidate_repo.get_recent_consented(
                limit=self.FALLBACK_POOL_SIZE
            )
            call.success = bool(candidates)
            call.completed_at = datetime.utcnow()
            call.error = "Vector search empty, used recent-consented fallback"
            state.agent_calls.append(call)
            return self._orms_to_dicts(candidates)

        except asyncio.TimeoutError:
            call.success = False
            call.error = "Vector search timed out"
            call.completed_at = datetime.utcnow()
            state.agent_calls.append(call)

            # Fallback on timeout too
            candidates = await self.candidate_repo.get_recent_consented(
                limit=self.FALLBACK_POOL_SIZE
            )
            logger.info(f"Vector search timed out; fallback: {len(candidates)} candidates")
            return self._orms_to_dicts(candidates)

    async def _batch_score(self, state: WorkflowState, candidates: list[dict], job: Any) -> list[dict]:
        """Score all candidates against the job via Matching Agent."""
        call = AgentCall(agent_name="matching_agent", started_at=datetime.utcnow())

        job_dict = self._job_to_dict(job)

        try:
            results = await asyncio.wait_for(
                self._score_batch(candidates, job_dict),
                timeout=self.MATCHING_TIMEOUT,
            )
            call.success = True
            call.completed_at = datetime.utcnow()
            state.agent_calls.append(call)
            state.results["matches_scored"] = len(results)
            return results

        except asyncio.TimeoutError:
            call.success = False
            call.error = "Matching agent timed out"
            call.completed_at = datetime.utcnow()
            state.agent_calls.append(call)
            raise AgentTimeoutError("matching_agent", "Batch scoring timed out")

    async def _score_batch(self, candidates: list[dict], job_dict: dict) -> list[dict]:
        """Local scoring (avoids network call — matcher is stateless and fast)."""
        from services.matching_agent.matcher import batch_score
        return batch_score(candidates, job_dict)

    async def _gdpr_filter(self, state: WorkflowState, matches: list[dict]) -> list[dict]:
        """Apply GDPR compliance filter before returning matches.

        In production, calls GDPR Agent service.
        Current: inline filter by consent_status and data minimization.
        """
        call = AgentCall(agent_name="gdpr_agent", started_at=datetime.utcnow())
        filtered = []
        blocked_count = 0

        for match in matches:
            candidate = match.get("_candidate", {})
            consent = candidate.get("consent_status", "")

            if consent != "granted":
                blocked_count += 1
                continue

            # Data minimization: strip raw PII from match output
            safe_match = {
                k: v for k, v in match.items()
                if k != "_candidate"  # remove internal reference
            }
            filtered.append(safe_match)

        call.success = True
        call.completed_at = datetime.utcnow()
        call.error = f"Blocked {blocked_count} candidates without consent"
        state.agent_calls.append(call)
        state.results["gdpr_blocked"] = blocked_count

        if not filtered and blocked_count > 0:
            logger.warning(f"All {blocked_count} candidates blocked by GDPR filter")
        else:
            logger.info(f"GDPR filter: {len(filtered)} passed, {blocked_count} blocked")

        return filtered

    def _rank_and_build(
        self,
        state: WorkflowState,
        job_id: UUID,
        filtered: list[dict],
        all_candidates: list[dict],
    ) -> dict:
        """Sort by overall_score descending and build shortlist."""
        ranked = sorted(filtered, key=lambda m: m.get("overall_score", 0), reverse=True)
        top = ranked[:self.FINAL_SHORTLIST_SIZE]

        return {
            "job_id": str(job_id),
            "matches": top,
            "total_candidates_scored": len(all_candidates),
            "processing_time_ms": state.elapsed_ms(),
            "metadata": {
                "workflow_id": str(state.workflow_id),
                "status": state.status.value,
                "gdpr_blocked": state.results.get("gdpr_blocked", 0),
            },
        }

    # ─── Helpers ────────────────────────────────────────────────────────

    def _empty_shortlist(self, state: WorkflowState, job_id: UUID) -> dict:
        state.status = WorkflowStatus.SUCCEEDED
        state.completed_at = datetime.utcnow()
        return FallbackHandler.on_empty_pool(str(job_id))

    def _partial_shortlist(self, state: WorkflowState, job_id: UUID,
                           message: str) -> dict:
        return {
            "job_id": str(job_id),
            "matches": [],
            "total_candidates_scored": 0,
            "processing_time_ms": state.elapsed_ms(),
            "metadata": {
                "workflow_id": str(state.workflow_id),
                "status": state.status.value,
                "message": message,
            },
        }

    def _fail(self, state: WorkflowState, message: str) -> dict:
        state.status = WorkflowStatus.FAILED
        state.completed_at = datetime.utcnow()
        state.errors.append({"error": message, "timestamp": str(datetime.utcnow())})
        return FallbackHandler.on_empty_pool(str(state.context.get("job_id", "")))

    @staticmethod
    def _orms_to_dicts(orms: list) -> list[dict]:
        result = []
        for o in orms:
            d = {
                "candidate_id": str(o.candidate_id),
                "skills": list(o.skills) if o.skills else [],
                "years_of_experience": o.years_of_experience or 0,
                "seniority": o.seniority or "mid",
                "domains": list(o.domains) if o.domains else [],
                "salary_expectation": o.salary_expectation,
                "location": o.location,
                "willing_to_relocate": o.willing_to_relocate or False,
                "consent_status": o.consent_status or "pending",
                "confidence_score": o.confidence_score or 0.0,
            }
            result.append(d)
        return result

    @staticmethod
    def _job_to_dict(job: Any) -> dict:
        return {
            "required_skills": list(job.required_skills) if hasattr(job, "required_skills") and job.required_skills else [],
            "preferred_skills": list(job.preferred_skills) if hasattr(job, "preferred_skills") and job.preferred_skills else [],
            "seniority": getattr(job, "seniority", "mid"),
            "years_experience_required": getattr(job, "years_experience_required", 0),
            "domains": list(job.domains) if hasattr(job, "domains") and job.domains else [],
            "salary_range": (
                (job.salary_min, job.salary_max)
                if hasattr(job, "salary_min") and job.salary_min is not None
                else None
            ),
            "location": getattr(job, "location", None),
            "remote_allowed": getattr(job, "remote_allowed", False),
        }
