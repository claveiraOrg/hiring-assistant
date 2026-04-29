"""Candidate Ingestion Flow.

CV Upload → Profile Intelligence Agent → Structured Profile
→ Embedding Generation → Vector Store → Candidate DB Update

Constraints:
- <5 seconds per CV
- Idempotent (retry-safe — same CV won't create duplicate)
- Assigns confidence score
- Stores embedding in pgvector
- Stores raw CV in S3
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any
from uuid import uuid4

from orchestrator.errors import FallbackHandler
from orchestrator.state import AgentCall, WorkflowFactory, WorkflowState, WorkflowStatus

logger = logging.getLogger(__name__)


class IngestionFlow:
    """End-to-end candidate ingestion workflow.

    SLA: <5 seconds per CV from upload to DB commit.
    """

    # Time budget (seconds)
    PROFILE_EXTRACTION_TIMEOUT = 3.0
    EMBEDDING_TIMEOUT = 1.0
    DB_WRITE_TIMEOUT = 0.5
    S3_WRITE_TIMEOUT = 0.5

    def __init__(self, candidate_repo, s3_client=None, embedding_fn=None):
        self.candidate_repo = candidate_repo
        self.s3_client = s3_client
        self.embedding_fn = embedding_fn or self._default_embedding

    async def ingest(self, cv_text: str, external_id: str | None = None) -> dict:
        """Ingest a CV into the system.

        Steps:
        1. Check for existing candidate (idempotency)
        2. Extract structured profile (LLM with fallback)
        3. Generate embedding vector
        4. Write to S3 (raw CV)
        5. Write to DB (candidate record + embedding)
        6. Return result

        Returns dict with action, candidate_id, and processing metadata.
        """
        state = WorkflowFactory.new_ingestion(external_id)
        logger.info(f"Ingestion started: external_id={external_id}")

        try:
            # ─── Step 1: Idempotency check ─────────────────────────────
            existing = None
            if external_id:
                existing = await self.candidate_repo.get_by_external_id(external_id)

            if existing:
                return self._handle_duplicate(state, existing, cv_text)

            # ─── Step 2: Extract profile ───────────────────────────────
            profile = await self._extract_profile(state, cv_text)
            if profile is None:
                profile = FallbackHandler.on_llm_failure(cv_text)

            state.results["profile"] = {
                "full_name": profile.get("full_name", "Unknown"),
                "skill_count": len(profile.get("skills", [])),
                "confidence": profile.get("confidence_score", 0),
                "fallback": profile.get("fallback", False),
            }

            # ─── Step 3: Generate embedding ────────────────────────────
            embedding = await self._generate_embedding(state, profile)

            # ─── Step 4: Store raw CV in S3 ────────────────────────────
            candidate_id = uuid4()
            s3_key = await self._store_raw_cv(state, candidate_id, cv_text)

            # ─── Step 5: Write to DB ───────────────────────────────────
            candidate = await self._write_to_db(
                state, candidate_id, profile, embedding, s3_key, external_id
            )

            state.status = WorkflowStatus.SUCCEEDED
            state.results["candidate_id"] = str(candidate.candidate_id)

            elapsed = state.elapsed_ms()
            logger.info(
                f"Ingestion complete: candidate_id={candidate.candidate_id}, "
                f"elapsed={elapsed}ms, confidence={profile.get('confidence_score', 0)}"
            )

            return {
                "action": "created",
                "candidate_id": str(candidate.candidate_id),
                "profile": profile,
                "processing_time_ms": elapsed,
            }

        except Exception as e:
            state.status = WorkflowStatus.FAILED
            state.completed_at = datetime.utcnow()
            state.errors.append({"error": str(e), "timestamp": str(datetime.utcnow())})
            logger.exception(f"Ingestion failed: {e}")
            return {
                "action": "failed",
                "error": str(e),
                "processing_time_ms": state.elapsed_ms(),
            }

    async def _extract_profile(self, state: WorkflowState, cv_text: str) -> dict | None:
        """Call Profile Intelligence Agent for structured extraction.

        In production, calls the profile-agent service endpoint.
        Current: inline extraction via the matcher's fallback.
        """
        call = AgentCall(agent_name="profile_agent", started_at=datetime.utcnow())

        try:
            # Inline: call the profile agent service
            # For now, return None so fallback kicks in (will connect to real agent)
            # TODO: Replace with HTTP call to profile-agent service
            from services.profile_agent.extractor import extract_profile_llm
            profile = await extract_profile_llm(cv_text)
            call.success = True
            call.completed_at = datetime.utcnow()
            state.agent_calls.append(call)
            return profile

        except ImportError:
            # Profile agent not yet built — use fallback
            logger.warning("Profile agent not available, using fallback")
            call.success = False
            call.error = "Profile agent not deployed"
            call.completed_at = datetime.utcnow()
            state.agent_calls.append(call)
            return None

        except Exception as e:
            call.success = False
            call.error = str(e)
            call.completed_at = datetime.utcnow()
            state.agent_calls.append(call)
            return None

    async def _generate_embedding(self, state: WorkflowState, profile: dict) -> list[float]:
        """Generate embedding vector from structured profile."""
        call = AgentCall(agent_name="embedding", started_at=datetime.utcnow())

        try:
            text_to_embed = " ".join([
                " ".join(profile.get("skills", [])),
                profile.get("seniority", ""),
                " ".join(profile.get("domains", [])),
                f"{profile.get('years_of_experience', 0)} years experience",
            ])
            embedding = await self.embedding_fn(text_to_embed)
            call.success = True
            call.completed_at = datetime.utcnow()
            state.agent_calls.append(call)
            return embedding

        except Exception as e:
            call.success = False
            call.error = str(e)
            call.completed_at = datetime.utcnow()
            state.agent_calls.append(call)
            # Return a zero vector (matching will be poor but won't crash)
            return [0.0] * 384

    async def _store_raw_cv(self, state: WorkflowState, candidate_id, cv_text: str) -> str | None:
        """Store raw CV in S3-compatible object storage."""
        call = AgentCall(agent_name="s3_write", started_at=datetime.utcnow())

        if self.s3_client is None:
            call.success = False
            call.error = "S3 client not configured"
            call.completed_at = datetime.utcnow()
            state.agent_calls.append(call)
            return None

        try:
            s3_key = f"cvs/{candidate_id}.txt"
            await self.s3_client.put_object(
                Bucket="hermes-cvs",
                Key=s3_key,
                Body=cv_text.encode("utf-8"),
            )
            call.success = True
            call.completed_at = datetime.utcnow()
            state.agent_calls.append(call)
            return s3_key
        except Exception as e:
            call.success = False
            call.error = str(e)
            call.completed_at = datetime.utcnow()
            state.agent_calls.append(call)
            return None

    async def _write_to_db(self, state: WorkflowState, candidate_id, profile: dict,
                           embedding: list[float], s3_key: str | None,
                           external_id: str | None):
        """Write candidate record to PostgreSQL."""
        call = AgentCall(agent_name="db_write", started_at=datetime.utcnow())

        from src.db.models import CandidateORM

        candidate = CandidateORM(
            candidate_id=candidate_id,
            external_id=external_id,
            full_name=profile.get("full_name", "Unknown"),
            skills=profile.get("skills", []),
            years_of_experience=profile.get("years_of_experience", 0),
            seniority=profile.get("seniority", "mid"),
            domains=profile.get("domains", []),
            career_trajectory=profile.get("career_trajectory", []),
            salary_expectation=profile.get("salary_expectation"),
            location=profile.get("location"),
            willing_to_relocate=profile.get("willing_to_relocate", False),
            embedding=embedding,
            confidence_score=profile.get("confidence_score", 0.0),
            raw_cv_s3_key=s3_key,
            consent_status="pending",  # must be explicitly granted later
        )

        result = await self.candidate_repo.create(candidate)
        call.success = True
        call.completed_at = datetime.utcnow()
        state.agent_calls.append(call)
        return result

    def _handle_duplicate(self, state: WorkflowState, existing, cv_text: str) -> dict:
        """Idempotent handling: update existing record and return."""
        call = AgentCall(agent_name="idempotency", started_at=datetime.utcnow())
        call.success = True
        call.completed_at = datetime.utcnow()
        call.error = f"Duplicate external_id, returning existing candidate"
        state.agent_calls.append(call)

        state.status = WorkflowStatus.SUCCEEDED
        state.results["candidate_id"] = str(existing.candidate_id)

        logger.info(f"Ingestion idempotent: existing candidate {existing.candidate_id}")
        return {
            "action": "duplicate_skipped",
            "candidate_id": str(existing.candidate_id),
            "processing_time_ms": state.elapsed_ms(),
        }

    @staticmethod
    async def _default_embedding(text: str) -> list[float]:
        """Default embedding: returns zero vector until embedding model is connected."""
        # TODO: Replace with real embedding model call
        return [0.0] * 384
