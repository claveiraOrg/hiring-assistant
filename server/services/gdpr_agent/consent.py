"""GDPR Compliance Agent — Consent Lifecycle Manager.

Enforces:
- Consent-first access model: no data accessible without active consent
- Full consent lifecycle: grant, revoke, verify, expire
- Auto-expiration handling
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from uuid import UUID, uuid4

from src.db.repositories.audit_repo import ConsentRepository
from src.schemas import GDPRConsentStatus

logger = logging.getLogger(__name__)

# Default consent duration if not specified (e.g., 365 days)
DEFAULT_CONSENT_DURATION_DAYS = 365


class ConsentError(Exception):
    """Base error for consent operations."""

class ConsentNotFoundError(ConsentError):
    """No consent record found for candidate."""

class ConsentAlreadyRevokedError(ConsentError):
    """Attempt to revoke already-revoked consent."""


class ConsentManager:
    """Full consent lifecycle management.

    Every data access path MUST call verify_consent() FIRST.
    No candidate profile is visible without passing this gate.
    """

    def __init__(self, consent_repo: ConsentRepository, candidate_repo=None):
        self._consent_repo = consent_repo
        self._candidate_repo = candidate_repo

    async def grant(
        self,
        candidate_id: UUID,
        scope: list[str] | None = None,
        duration_days: int = DEFAULT_CONSENT_DURATION_DAYS,
    ) -> dict:
        """Grant consent for a candidate.

        Creates a consent record with:
        - status: granted
        - scope: list of data categories consented to
        - expiry: now + duration_days
        """
        logger.info(f"Granting consent for candidate {candidate_id}, scope={scope}")

        # Revoke any existing consent first (idempotent)
        existing = await self._consent_repo.get_active(candidate_id)
        if existing and existing.status == "granted":
            logger.info(f"Consent already granted for {candidate_id}, updating scope")
            # Update existing record
            await self._consent_repo.grant(candidate_id, scope)
        else:
            await self._consent_repo.grant(candidate_id, scope)

        # Update candidate record in DB
        if self._candidate_repo:
            await self._candidate_repo.update_consent_status(
                candidate_id, GDPRConsentStatus.GRANTED.value
            )

        expires_at = datetime.utcnow() + timedelta(days=duration_days)

        return {
            "candidate_id": str(candidate_id),
            "status": GDPRConsentStatus.GRANTED.value,
            "scope": scope or ["all"],
            "expires_at": expires_at.isoformat(),
            "message": "Consent granted successfully",
        }

    async def revoke(self, candidate_id: UUID) -> dict:
        """Revoke consent for a candidate.

        Triggers:
        - immediate data isolation (candidate flagged as revoked)
        - no further data access permitted
        - existing matches are preserved but marked as historical
        """
        logger.info(f"Revoking consent for candidate {candidate_id}")

        existing = await self._consent_repo.get_active(candidate_id)
        if not existing:
            raise ConsentNotFoundError(f"No consent record for candidate {candidate_id}")
        if existing.status == "revoked":
            raise ConsentAlreadyRevokedError(f"Consent already revoked for {candidate_id}")

        await self._consent_repo.revoke(candidate_id)

        # Update candidate record
        if self._candidate_repo:
            await self._candidate_repo.update_consent_status(
                candidate_id, GDPRConsentStatus.REVOKED.value
            )

        return {
            "candidate_id": str(candidate_id),
            "status": GDPRConsentStatus.REVOKED.value,
            "revoked_at": datetime.utcnow().isoformat(),
            "message": "Consent revoked — data is now isolated",
        }

    async def verify(self, candidate_id: UUID) -> dict:
        """Verify consent is active for a candidate.

        This is the GATE that EVERY data access path must call.
        Returns:
            allowed: bool — true if consent is active
            consent_status: str — current status
            reason: str | None — explanation if denied
        """
        consent = await self._consent_repo.get_active(candidate_id)

        if consent is None:
            return {
                "allowed": False,
                "consent_status": GDPRConsentStatus.PENDING.value,
                "reason": "No consent record found — consent is required before any data access",
            }

        if consent.status == GDPRConsentStatus.REVOKED.value:
            return {
                "allowed": False,
                "consent_status": GDPRConsentStatus.REVOKED.value,
                "reason": "Consent has been revoked by the candidate",
            }

        if consent.expires_at and consent.expires_at < datetime.utcnow():
            # Auto-expire
            await self._auto_expire(consent.consent_id, candidate_id)
            return {
                "allowed": False,
                "consent_status": GDPRConsentStatus.EXPIRED.value,
                "reason": "Consent has expired",
            }

        if consent.status == GDPRConsentStatus.GRANTED.value:
            return {
                "allowed": True,
                "consent_status": GDPRConsentStatus.GRANTED.value,
                "reason": None,
            }

        return {
            "allowed": False,
            "consent_status": consent.status,
            "reason": f"Consent status is '{consent.status}' — access denied",
        }

    async def get_status(self, candidate_id: UUID) -> dict:
        """Get consent status for a candidate (no side effects)."""
        consent = await self._consent_repo.get_active(candidate_id)
        if consent is None:
            return {
                "candidate_id": str(candidate_id),
                "status": GDPRConsentStatus.PENDING.value,
                "granted_at": None,
                "revoked_at": None,
                "expires_at": None,
                "scope": [],
            }

        return {
            "candidate_id": str(candidate_id),
            "status": consent.status,
            "granted_at": consent.granted_at.isoformat() if consent.granted_at else None,
            "revoked_at": consent.revoked_at.isoformat() if consent.revoked_at else None,
            "expires_at": consent.expires_at.isoformat() if consent.expires_at else None,
            "scope": list(consent.data_scope) if consent.data_scope else [],
        }

    async def _auto_expire(self, consent_id: UUID, candidate_id: UUID) -> None:
        """Auto-expire a consent record that has passed its expiry date."""
        logger.info(f"Auto-expiring consent {consent_id} for candidate {candidate_id}")
        if self._candidate_repo:
            await self._candidate_repo.update_consent_status(
                candidate_id, GDPRConsentStatus.EXPIRED.value
            )
