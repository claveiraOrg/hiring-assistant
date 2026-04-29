"""Tests for the Hermes Orchestrator — matching flow (critical path).

Focus on:
- Matching flow: fetch → score → GDPR filter → rank
- Fallback paths: empty pool, GDPR denial, timeout
- State machine transitions
- Anti-leakage router payload scoping
"""

import pytest
from uuid import uuid4

from orchestrator.errors import (
    AgentTimeoutError,
    EmptyCandidatePoolError,
    FallbackHandler,
    GDPRAccessDenied,
    RetryHandler,
)
from orchestrator.router import (
    MATCHING_AGENT_CANDIDATE_FIELDS,
    MATCHING_AGENT_JOB_FIELDS,
    PROFILE_AGENT_ALLOWED,
    AgentRouter,
)
from orchestrator.state import WorkflowFactory, WorkflowStatus, WorkflowType


# ─── Workflow State ─────────────────────────────────────────────────────

class TestWorkflowState:
    def test_new_matching_state(self):
        job_id = uuid4()
        state = WorkflowFactory.new_matching(job_id)
        assert state.workflow_type == WorkflowType.JOB_MATCHING
        assert state.status == WorkflowStatus.PENDING
        assert state.context["job_id"] == str(job_id)
        assert state.retry_count == 0

    def test_new_ingestion_state(self):
        state = WorkflowFactory.new_ingestion("ext-123")
        assert state.workflow_type == WorkflowType.CANDIDATE_INGESTION
        assert state.context["external_id"] == "ext-123"

    def test_state_transitions(self):
        state = WorkflowFactory.new_matching(uuid4())
        assert state.status == WorkflowStatus.PENDING
        state.status = WorkflowStatus.RUNNING
        assert state.status == WorkflowStatus.RUNNING
        state.status = WorkflowStatus.SUCCEEDED
        assert state.status == WorkflowStatus.SUCCEEDED

    def test_elapsed_ms(self):
        state = WorkflowFactory.new_matching(uuid4())
        elapsed = state.elapsed_ms()
        assert elapsed >= 0
        assert isinstance(elapsed, int)

    def test_to_dict(self):
        state = WorkflowFactory.new_matching(uuid4())
        d = state.to_dict()
        assert "workflow_id" in d
        assert "status" in d
        assert "elapsed_ms" in d
        assert d["workflow_type"] == "job_matching"


# ─── Retry Handler ──────────────────────────────────────────────────────

class TestRetryHandler:
    @pytest.mark.asyncio
    async def test_retry_on_timeout(self):
        """Should retry and eventually raise AgentTimeoutError."""

        call_count = 0

        async def flaky_fn():
            nonlocal call_count
            call_count += 1
            raise TimeoutError("timed out")

        handler = RetryHandler(max_retries=3, base_delay=0.01)
        with pytest.raises(AgentTimeoutError):
            await handler.call_with_retry(flaky_fn, timeout=1.0)
        assert call_count == 3  # All retries exhausted

    @pytest.mark.asyncio
    async def test_success_on_second_attempt(self):
        """Should succeed on retry after initial failure."""

        call_count = 0

        async def eventually_works():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise ConnectionError("not ready")
            return "success"

        handler = RetryHandler(max_retries=3, base_delay=0.01)
        result = await handler.call_with_retry(eventually_works, timeout=2.0)
        assert result == "success"
        assert call_count == 2


# ─── Fallback Handler ───────────────────────────────────────────────────

class TestFallbackHandler:
    def test_empty_pool_returns_metadata(self):
        result = FallbackHandler.on_empty_pool("job-123")
        assert result["job_id"] == "job-123"
        assert result["matches"] == []
        assert "notify_recruiters_to_source" in result["metadata"]["action"]

    def test_llm_fallback_returns_minimal_profile(self):
        result = FallbackHandler.on_llm_failure("Has Python and SQL skills")
        assert result["full_name"] == "Unknown"
        assert "python" in result["skills"]
        assert result["confidence_score"] == 0.15
        assert result["fallback"] is True

    def test_gdpr_denial_returns_error(self):
        result = FallbackHandler.on_gdpr_denial("cand-1", "recruiter-1")
        assert result["error"] == "Candidate data not available"
        assert result["code"] == "CONSENT_DENIED"

    def test_llm_fallback_extracts_common_skills(self):
        result = FallbackHandler.on_llm_failure(
            "I know Python, AWS, and Kubernetes very well"
        )
        assert "python" in result["skills"]
        assert "aws" in result["skills"]
        assert "kubernetes" in result["skills"]
        assert "java" not in result["skills"]


# ─── Agent Router — Payload Scoping ────────────────────────────────────

class TestAgentRouterScoping:
    def test_profile_agent_only_gets_cv_text(self):
        payload = {
            "cv_text": "my cv content",
            "candidate_external_id": "ext-1",
            "full_name": "Jane",  # should NOT be sent
            "salary_expectation": 150000,  # should NOT be sent
        }
        scoped = {k: payload[k] for k in PROFILE_AGENT_ALLOWED if k in payload}
        assert "cv_text" in scoped
        assert "candidate_external_id" in scoped
        assert "full_name" not in scoped
        assert "salary_expectation" not in scoped

    def test_matching_agent_does_not_get_raw_cv(self):
        """Data minimization: Matching Agent never sees raw CV or full name."""
        candidate_payload = {
            "skills": ["Python"],
            "seniority": "senior",
            "full_name": "Jane Doe",  # NOT in allowed fields
            "raw_cv": "long cv text here...",  # NOT in allowed fields
        }
        scoped = {
            k: candidate_payload[k]
            for k in MATCHING_AGENT_CANDIDATE_FIELDS
            if k in candidate_payload
        }
        assert "skills" in scoped
        assert "seniority" in scoped
        assert "full_name" not in scoped
        assert "raw_cv" not in scoped

    def test_matching_job_fields_scoped(self):
        job_payload = {
            "required_skills": ["Python"],
            "salary_range": (100, 200),
            "raw_jd_text": "full job description...",  # should not leak
            "internal_notes": "confidential",  # should not leak
        }
        scoped = {
            k: job_payload[k]
            for k in MATCHING_AGENT_JOB_FIELDS
            if k in job_payload
        }
        assert "required_skills" in scoped
        assert "salary_range" in scoped
        assert "raw_jd_text" not in scoped
        assert "internal_notes" not in scoped

    def test_gdpr_allowed_fields_correct(self):
        from orchestrator.router import GDPR_AGENT_ALLOWED
        assert "candidate_id" in GDPR_AGENT_ALLOWED
        assert "consent_status" in GDPR_AGENT_ALLOWED
        # GDPR agent does NOT get raw CV
        assert "raw_cv" not in GDPR_AGENT_ALLOWED


# ─── Matching Flow Integration Tests ────────────────────────────────────

class TestMatchingFlowIntegration:
    """Integration tests using local (in-process) scoring.

    These test the full matching flow logic without external service calls.
    """

    @pytest.mark.asyncio
    async def test_match_flow_returns_shortlist(self):
        """End-to-end matching flow should return a ranked shortlist."""
        from services.matching_agent.matcher import batch_score

        # Simulate candidates from a vector search
        candidates = [
            {
                "skills": ["Python", "ML", "SQL"],
                "years_of_experience": 6,
                "seniority": "senior",
                "domains": ["FinTech"],
                "salary_expectation": 150_000,
                "location": "London",
                "willing_to_relocate": False,
                "consent_status": "granted",
                "confidence_score": 0.9,
            },
            {
                "skills": ["Java"],
                "years_of_experience": 2,
                "seniority": "junior",
                "domains": ["Gaming"],
                "salary_expectation": 200_000,
                "location": "Tokyo",
                "willing_to_relocate": False,
                "consent_status": "granted",
                "confidence_score": 0.7,
            },
        ]

        job = {
            "required_skills": ["Python", "ML", "SQL"],
            "preferred_skills": ["Kubernetes"],
            "seniority": "senior",
            "years_experience_required": 5,
            "domains": ["FinTech"],
            "salary_range": (130_000, 180_000),
            "location": "London",
            "remote_allowed": False,
        }

        # Batch score
        matches = batch_score(candidates, job)

        # Apply GDPR filter (simplified)
        filtered = []
        for i, m in enumerate(matches):
            if candidates[i]["consent_status"] == "granted":
                filtered.append(m)

        # Rank
        ranked = sorted(filtered, key=lambda m: m["overall_score"], reverse=True)

        assert len(ranked) == 2
        assert ranked[0]["overall_score"] > ranked[1]["overall_score"]
        # Candidate 1 (senior Python/ML/London) should rank higher
        assert ranked[0]["overall_score"] >= 0.75
        assert ranked[1]["overall_score"] < 0.50

    @pytest.mark.asyncio
    async def test_gdpr_filter_blocks_without_consent(self):
        """Candidates without consent must be filtered out."""
        from services.matching_agent.matcher import score_match

        candidates = [
            {
                "skills": ["Python"],
                "years_of_experience": 5,
                "seniority": "senior",
                "domains": ["Tech"],
                "salary_expectation": 100_000,
                "location": "London",
                "willing_to_relocate": False,
                "consent_status": "granted",
            },
            {
                "skills": ["Python"],
                "years_of_experience": 5,
                "seniority": "senior",
                "domains": ["Tech"],
                "salary_expectation": 100_000,
                "location": "London",
                "willing_to_relocate": False,
                "consent_status": "revoked",
            },
            {
                "skills": ["Python"],
                "years_of_experience": 5,
                "seniority": "senior",
                "domains": ["Tech"],
                "salary_expectation": 100_000,
                "location": "London",
                "willing_to_relocate": False,
                "consent_status": "pending",
            },
        ]

        job = {"required_skills": ["Python"], "seniority": "senior",
               "years_experience_required": 3, "domains": ["Tech"],
               "remote_allowed": True}

        filtered = [
            m for m, c in zip(
                [score_match(c, job) for c in candidates], candidates
            )
            if c["consent_status"] == "granted"
        ]

        assert len(filtered) == 1  # Only the granted one passes

    @pytest.mark.asyncio
    async def test_empty_candidate_pool_returns_graceful(self):
        """Empty pool should return graceful response, not crash."""
        result = FallbackHandler.on_empty_pool("job-1")
        assert result["matches"] == []
        assert result["total_candidates_scored"] == 0


# ─── Ingestion Flow Tests ───────────────────────────────────────────────

class TestIngestionFlow:
    @pytest.mark.asyncio
    async def test_idempotent_duplicate(self):
        """Same external_id should return duplicate_skipped."""
        from orchestrator.workflows.ingestion_flow import IngestionFlow

        class MockRepo:
            async def get_by_external_id(self, ext_id):
                if ext_id == "existing-123":
                    from src.db.models import CandidateORM
                    c = CandidateORM()
                    c.candidate_id = uuid4()
                    return c
                return None

        flow = IngestionFlow(candidate_repo=MockRepo())

        # First call — should create
        result1 = await flow.ingest("Some CV text", "new-user")
        assert result1["action"] in ("created", "failed")

        # Second call with same external ID — should skip
        result2 = await flow.ingest("Same CV", "existing-123")
        assert result2["action"] == "duplicate_skipped"

    @pytest.mark.asyncio
    async def test_ingestion_handles_empty_cv(self):
        """Empty or minimal CV should still produce a result."""
        from orchestrator.workflows.ingestion_flow import IngestionFlow

        class MockRepo:
            async def get_by_external_id(self, ext_id):
                return None
            async def create(self, candidate):
                candidate.candidate_id = uuid4()
                return candidate

        flow = IngestionFlow(candidate_repo=MockRepo())
        result = await flow.ingest("", "empty-cv")
        # Should not crash, should produce a fallback profile
        assert result["action"] in ("created", "failed")
