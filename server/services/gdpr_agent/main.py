"""GDPR Compliance Agent — FastAPI service.

Provides:
- POST /v1/consent/grant     — Grant consent
- POST /v1/consent/revoke    — Revoke consent
- GET  /v1/consent/{id}      — Check consent status
- POST /v1/verify            — Verify consent before data access
- POST /v1/filter/profile    — Apply data minimization filter
- POST /v1/filter/match      — Apply minimization to match results
- POST /v1/delete/{id}       — Right to deletion (cascade)
- GET  /v1/audit             — Query audit trail
- GET  /health               — Health check
"""

from __future__ import annotations

import logging
from datetime import datetime
from uuid import UUID

from fastapi import FastAPI, HTTPException

from src.schemas import (
    ConsentCheckRequest,
    ConsentCheckResponse,
    DeletionRequest,
    DeletionResponse,
    GDPRFilterRequest,
    GDPRFilterResponse,
)

logger = logging.getLogger(__name__)

app = FastAPI(
    title="GDPR Compliance Agent",
    version="0.1.0",
    description="Enforces GDPR: consent, data minimization, audit, deletion",
)

# Will be set at startup via dependency injection
consent_manager = None
data_minimizer = None
audit_service = None
deletion_service = None


def setup(
    consent_mgr=None,
    data_min_filter=None,
    audit_svc=None,
    delete_svc=None,
):
    global consent_manager, data_minimizer, audit_service, deletion_service
    consent_manager = consent_mgr
    data_minimizer = data_min_filter
    audit_service = audit_svc
    deletion_service = delete_svc


@app.get("/health")
async def health():
    return {"status": "ok", "service": "gdpr-agent", "version": "0.1.0"}


# ─── Consent Endpoints ──────────────────────────────────────────────────

@app.post("/v1/consent/grant")
async def grant_consent(candidate_id: UUID, scope: list[str] | None = None):
    if consent_manager is None:
        raise HTTPException(503, "Consent manager not initialized")
    result = await consent_manager.grant(candidate_id, scope)
    if audit_service:
        await audit_service.log_consent_change(
            actor_id="system",
            candidate_id=candidate_id,
            old_status="pending",
            new_status="granted",
        )
    return result


@app.post("/v1/consent/revoke")
async def revoke_consent(candidate_id: UUID):
    if consent_manager is None:
        raise HTTPException(503, "Consent manager not initialized")
    try:
        result = await consent_manager.revoke(candidate_id)
        if audit_service:
            await audit_service.log_consent_change(
                actor_id="system",
                candidate_id=candidate_id,
                old_status="granted",
                new_status="revoked",
            )
        return result
    except Exception as e:
        raise HTTPException(400, str(e))


@app.get("/v1/consent/{candidate_id}")
async def check_consent(candidate_id: UUID):
    if consent_manager is None:
        raise HTTPException(503, "Consent manager not initialized")
    return await consent_manager.get_status(candidate_id)


@app.post("/v1/verify", response_model=ConsentCheckResponse)
async def verify_access(request: ConsentCheckRequest):
    """Verify consent is active before allowing data access.

    This endpoint is called by the orchestrator's GDPR filtering step.
    """
    if consent_manager is None:
        raise HTTPException(503, "Consent manager not initialized")
    result = await consent_manager.verify(request.candidate_id)

    # Always log the access attempt (granted or denied)
    if audit_service:
        await audit_service.log_access(
            actor_id=request.actor_id,
            action=request.action,
            resource_type="candidate",
            resource_id=request.candidate_id,
            granted=result["allowed"],
            reason=result.get("reason"),
        )

    return ConsentCheckResponse(
        allowed=result["allowed"],
        consent_status=result["consent_status"],
        reason=result.get("reason"),
    )


# ─── Data Minimization Endpoints ────────────────────────────────────────

@app.post("/v1/filter/profile")
async def filter_profile(request: GDPRFilterRequest):
    """Apply data minimization filter based on recruiter role."""
    if data_minimizer is None:
        raise HTTPException(503, "Data minimizer not initialized")
    filtered = data_minimizer.filter_profile(
        request.profile.model_dump(),
        request.recruiter_role,
    )
    if audit_service:
        await audit_service.log_access(
            actor_id="system",
            action="filter_profile",
            resource_type="candidate",
            resource_id=request.profile.candidate_id,
            granted="error" not in filtered,
            reason=f"Role: {request.recruiter_role}",
        )
    return filtered


@app.post("/v1/filter/match")
async def filter_match_result(match: dict, recruiter_role: str):
    """Apply data minimization to a match result."""
    if data_minimizer is None:
        raise HTTPException(503, "Data minimizer not initialized")
    return data_minimizer.filter_match_result(match, recruiter_role)


# ─── Deletion Endpoints ────────────────────────────────────────────────

@app.post("/v1/delete/{candidate_id}", response_model=DeletionResponse)
async def delete_candidate(candidate_id: UUID, actor_id: str = "system"):
    """Right to deletion — full cascade (DB, S3, embeddings, audit logs)."""
    if deletion_service is None:
        raise HTTPException(503, "Deletion service not initialized")
    result = await deletion_service.delete_candidate(candidate_id, actor_id)
    return DeletionResponse(
        status=result["status"],
        candidate_id=result["candidate_id"],
        deleted_records=result.get("deleted_records", []),
    )


# ─── Audit Endpoints ────────────────────────────────────────────────────

@app.get("/v1/audit")
async def query_audit(
    actor_id: str | None = None,
    resource_type: str | None = None,
    action: str | None = None,
    since: datetime | None = None,
    limit: int = 100,
):
    """Query audit trail for compliance review."""
    if audit_service is None:
        raise HTTPException(503, "Audit service not initialized")
    return await audit_service.query_audit_trail(
        actor_id=actor_id,
        resource_type=resource_type,
        action=action,
        since=since,
        limit=limit,
    )
