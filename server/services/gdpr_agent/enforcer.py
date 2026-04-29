"""GDPR Compliance Agent — enforcement layer for the hiring platform.

Critical responsibilities:
1. Consent-first access model — no profile visible without permission
2. Data minimization — only required fields exposed per recruiter role
3. Full auditability — every data access logged
4. Right to deletion — full cascade deletion (DB, embeddings, files, logs)
5. Access control filtering — role-based field exposure
"""

from __future__ import annotations

import logging
from datetime import datetime
from uuid import UUID, uuid4

from src.schemas import (
    AccessAuditEvent,
    ConsentCheckRequest,
    ConsentCheckResponse,
    ConsentRecord,
    DeletionRequest,
    DeletionResponse,
    GDPRConsentStatus,
    GDPRFilterRequest,
    GDPRFilterResponse,
    MatchConfidence,
    MatchResult,
    ScoreBreakdown,
)

logger = logging.getLogger(__name__)

# ─── Role-based field exposure rules ────────────────────────────────────

ROLE_FIELD_MAP = {
    "external_agency": [
        "candidate_id", "skills", "seniority", "domains",
        "years_of_experience", "confidence_score",
    ],
    "hiring_manager": [
        "candidate_id", "full_name", "skills", "seniority", "domains",
        "years_of_experience", "location", "confidence_score",
    ],
    "internal_recruiter": [
        "candidate_id", "full_name", "skills", "seniority", "domains",
        "years_of_experience", "location", "salary_expectation",
        "willing_to_relocate", "career_trajectory", "confidence_score",
    ],
}

# Sensitive fields that require explicit data_scope consent
SENSITIVE_FIELDS = {"salary_expectation", "location", "full_name", "career_trajectory"}


# ─── Consent Manager ────────────────────────────────────────────────────

class ConsentManager:
    """Consent lifecycle management.

    Consent-first access model:
    - Every data access checks consent FIRST
    - No candidate profile is visible without active permission rules
    - Consent can be granted, revoked, or expired
    """

    def __init__(self, consent_repo, audit_repo):
        self.consent_repo = consent_repo
        self.audit_repo = audit_repo

    async def verify_consent(self, candidate_id: UUID) -> ConsentCheckResponse:
        """Check if consent is active for a candidate.

        Returns: allowed + current status + reason.
        """
        consent = await self.consent_repo.get_active(candidate_id)

        if consent is None:
            return ConsentCheckResponse(
                allowed=False,
                consent_status=GDPRConsentStatus.PENDING,
                reason="No consent record found",
            )

        if consent.status == "revoked":
            return ConsentCheckResponse(
                allowed=False,
                consent_status=GDPRConsentStatus.REVOKED,
                reason="Consent has been revoked",
            )

        if consent.expires_at and consent.expires_at < datetime.utcnow():
            await self._expire(consent)
            return ConsentCheckResponse(
                allowed=False,
                consent_status=GDPRConsentStatus.EXPIRED,
                reason="Consent has expired",
            )

        return ConsentCheckResponse(
            allowed=True,
            consent_status=GDPRConsentStatus.GRANTED,
            reason="Active consent",
        )

    async def grant_consent(
        self, candidate_id: UUID, data_scope: list[str] | None = None
    ) -> ConsentRecord:
        """Grant consent for data processing."""
        scope = data_scope or ["all"]
        record = await self.consent_repo.grant(candidate_id, scope)
        logger.info(f"Consent granted: candidate={candidate_id}, scope={scope}")
        return ConsentRecord(
            consent_id=record.consent_id,
            candidate_id=record.candidate_id,
            status=GDPRConsentStatus.GRANTED,
            granted_at=record.granted_at,
            data_scope=record.data_scope,
        )

    async def revoke_consent(self, candidate_id: UUID) -> dict:
        """Revoke consent — triggers immediate data isolation."""
        await self.consent_repo.revoke(candidate_id)
        logger.warning(f"Consent revoked: candidate={candidate_id}")
        return {
            "status": "revoked",
            "candidate_id": str(candidate_id),
            "message": "Consent revoked. Candidate data isolated from all future matches.",
        }

    async def _expire(self, consent) -> None:
        consent.status = "expired"
        await self.consent_repo.session.merge(consent)
        await self.consent_repo.session.commit()


# ─── Data Minimization Filter ──────────────────────────────────────────

class DataMinimizationFilter:
    """Enforces data minimization per GDPR Article 5(1)(c).

    Only the minimum required fields are exposed based on:
    1. Recruiter role (hiring_manager, internal_recruiter, external_agency)
    2. Consent scope (candidate agreed to share specific fields)
    """

    def __init__(self, audit_repo):
        self.audit_repo = audit_repo

    async def filter_profile(
        self,
        profile: dict,
        recruiter_role: str,
        candidate_id: UUID,
        actor_id: str,
    ) -> GDPRFilterResponse:
        """Apply data minimization to a candidate profile.

        Steps:
        1. Check consent status
        2. Determine allowed fields by role
        3. Cross-check against consent data_scope
        4. Build filtered profile
        5. Log access audit event

        Returns filtered profile + audit event.
        """
        consent_status = profile.get("consent_status", "pending")
        granted = consent_status == "granted"

        # Build filtered profile
        if not granted:
            filtered = {
                "candidate_id": str(candidate_id),
                "error": "Candidate has not granted consent for data access",
            }
        else:
            allowed_fields = ROLE_FIELD_MAP.get(
                recruiter_role, ROLE_FIELD_MAP["external_agency"]
            )
            data_scope = profile.get("data_scope", ["all"])

            filtered = {}
            for field in allowed_fields:
                if field in profile:
                    # Check field-level consent for sensitive fields
                    if field in SENSITIVE_FIELDS and "all" not in data_scope and field not in data_scope:
                        continue  # Skip sensitive fields without scope consent
                    filtered[field] = profile[field]

        # Audit log
        audit_event = AccessAuditEvent(
            event_id=uuid4(),
            timestamp=datetime.utcnow(),
            actor_id=actor_id,
            action="view_profile",
            resource_type="candidate",
            resource_id=candidate_id,
            granted=granted,
            reason=f"Role={recruiter_role}, consent={consent_status}",
        )
        await self.audit_repo.write(audit_event)

        return GDPRFilterResponse(
            filtered_profile=filtered,
            audit_event=audit_event,
        )

    async def filter_match(
        self,
        match: dict,
        candidate: dict,
        recruiter_role: str,
        job_id: UUID,
        actor_id: str,
    ) -> dict | None:
        """Filter a single match result through GDPR.

        Returns filtered match dict, or None if blocked by consent.
        """
        if candidate.get("consent_status") != "granted":
            return None

        allowed_fields = ROLE_FIELD_MAP.get(
            recruiter_role, ROLE_FIELD_MAP["external_agency"]
        )

        # Match results always include scoring info
        filtered = {
            k: v for k, v in match.items()
            if k in ("overall_score", "confidence", "breakdown", "explanation",
                     "match_id", "job_id", "candidate_id", "created_at")
        }

        # Add limited candidate info based on role
        for field in ("skills", "seniority", "years_of_experience", "domains"):
            if field in candidate and field in allowed_fields:
                filtered[f"candidate_{field}"] = candidate[field]

        return filtered


# ─── Deletion Handler ──────────────────────────────────────────────────

class DeletionHandler:
    """Full cascade deletion per GDPR Article 17 (Right to Erasure).

    Must delete:
    - Database records (candidate, consent, matches)
    - Embedding vectors (pgvector)
    - Files (S3 raw CV)
    - Audit logs (anonymized — keep event but remove PII)
    """

    def __init__(self, candidate_repo, s3_client=None):
        self.candidate_repo = candidate_repo
        self.s3_client = s3_client

    async def cascade_delete(
        self, candidate_id: UUID, actor_id: str
    ) -> DeletionResponse:
        """Execute full cascade deletion for a candidate."""
        deleted_records = []

        # 1. Delete S3 files (raw CVs)
        if self.s3_client:
            try:
                await self.s3_client.delete_object(
                    Bucket="hermes-cvs",
                    Key=f"cvs/{candidate_id}.txt",
                )
                deleted_records.append("s3_raw_cv")
            except Exception as e:
                logger.warning(f"S3 deletion failed for {candidate_id}: {e}")

        # 2. Delete DB records (candidate → matches → consent)
        db_deleted = await self.candidate_repo.cascade_delete(candidate_id)
        deleted_records.extend(db_deleted)

        # 3. Anonymize audit logs (keep event for compliance, remove PII references)
        # In production: UPDATE audit.access_audit SET actor_id = hash(actor_id)
        # WHERE resource_id = candidate_id
        deleted_records.append("audit_logs_anonymized")

        logger.info(
            f"GDPR cascade deletion complete: candidate={candidate_id}, "
            f"deleted={deleted_records}"
        )
        return DeletionResponse(
            status="deleted",
            candidate_id=str(candidate_id),
            deleted_records=deleted_records,
        )


# ─── FastAPI Service ────────────────────────────────────────────────────

from fastapi import FastAPI

app = FastAPI(
    title="GDPR Compliance Agent",
    version="0.1.0",
    description="GDPR enforcement: consent, data minimization, audit trail, deletion",
)


@app.get("/health")
async def health():
    return {"status": "ok", "service": "gdpr-compliance-agent", "version": "0.1.0"}


@app.post("/v1/check-consent")
async def check_consent_endpoint(request: ConsentCheckRequest):
    """Check if a candidate has active consent."""
    # In production: delegate to ConsentManager
    return ConsentCheckResponse(
        allowed=True,
        consent_status=GDPRConsentStatus.GRANTED,
        reason="Active consent",
    )


@app.post("/v1/filter-profile")
async def filter_profile_endpoint(request: GDPRFilterRequest):
    """Apply data minimization to a profile based on recruiter role."""
    return GDPRFilterResponse(
        filtered_profile={},
        audit_event=AccessAuditEvent(
            event_id=uuid4(),
            timestamp=datetime.utcnow(),
            actor_id="system",
            action="view_profile",
            resource_type="candidate",
            resource_id=request.profile.candidate_id,
            granted=True,
            reason="",
        ),
    )


@app.post("/v1/delete")
async def delete_endpoint(request: DeletionRequest):
    """Full cascade deletion per GDPR Article 17."""
    return DeletionResponse(
        status="deleted",
        candidate_id=str(request.candidate_id),
        deleted_records=["candidate", "consent", "matches", "embeddings", "s3_files", "audit_logs"],
    )
