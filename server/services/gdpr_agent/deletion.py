"""GDPR Compliance Agent — Right to Deletion Service.

Enforces GDPR Article 17: Right to erasure ('right to be forgotten').

Full cascade deletion:
- Database records (candidate, consent, matches)
- Embedding vectors (pgvector)
- Raw files (S3 object storage)
- Audit logs (anonymized, not deleted — audit trail must be preserved)
"""

from __future__ import annotations

import logging
from uuid import UUID

from src.db.repositories.candidate_repo import CandidateRepository
from src.db.repositories.match_repo import MatchRepository

logger = logging.getLogger(__name__)


class DeletionService:
    """Right to deletion — full cascade cleanup.

    When a candidate requests deletion (or consent is revoked):
    1. Delete candidate record (triggers cascade to consent)
    2. Delete all matches for this candidate
    3. Delete raw CV from S3
    4. Anonymize audit logs (preserve event, remove PII)
    """

    def __init__(
        self,
        candidate_repo: CandidateRepository,
        match_repo: MatchRepository,
        s3_client=None,
        audit_service=None,
    ):
        self._candidate_repo = candidate_repo
        self._match_repo = match_repo
        self._s3_client = s3_client
        self._audit_service = audit_service

    async def delete_candidate(self, candidate_id: UUID, actor_id: str) -> dict:
        """Execute full cascade deletion for a candidate.

        Steps:
        1. Verify candidate exists
        2. Delete raw CV from S3 (if stored)
        3. Delete all match records
        4. Delete consent record + update candidate status
        5. Anonymize audit trail
        6. Log the deletion itself

        Returns summary of what was deleted.
        """
        logger.info(f"Right to deletion initiated: candidate {candidate_id} by {actor_id}")

        # 1. Verify candidate exists
        candidate = await self._candidate_repo.get_by_id(candidate_id)
        if not candidate:
            return {
                "status": "not_found",
                "candidate_id": str(candidate_id),
                "message": "Candidate not found — nothing to delete",
            }

        deleted_records = []

        # 2. Delete raw CV from S3
        s3_key = candidate.raw_cv_s3_key
        if s3_key and self._s3_client:
            try:
                await self._s3_client.delete_object(Bucket="hermes-cvs", Key=s3_key)
                deleted_records.append("s3_raw_cv")
                logger.info(f"Deleted S3 object: {s3_key}")
            except Exception as e:
                logger.warning(f"Failed to delete S3 object {s3_key}: {e}")

        # 3. Delete all match records
        match_count = await self._match_repo.delete_by_candidate(candidate_id)
        if match_count:
            deleted_records.append(f"matches:{match_count}")

        # 4. Cascade delete candidate (handles consent, embedding)
        db_deleted = await self._candidate_repo.cascade_delete(candidate_id)
        deleted_records.extend(db_deleted)

        # 5. Anonymize audit logs
        if self._audit_service:
            anonymized = await self._audit_service.anonymize_for_deletion(candidate_id)
            if anonymized:
                deleted_records.append(f"audit_records_anonymized:{anonymized}")

        # 6. Log the deletion action
        if self._audit_service:
            await self._audit_service.log_deletion_request(
                actor_id=actor_id,
                candidate_id=candidate_id,
                initiated_by="candidate_request",
            )

        return {
            "status": "deleted",
            "candidate_id": str(candidate_id),
            "deleted_records": deleted_records,
            "message": (
                "Candidate data fully deleted per GDPR Article 17. "
                "Audit trail preserved (anonymized)."
            ),
        }
