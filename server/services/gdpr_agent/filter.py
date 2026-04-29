"""GDPR Compliance Agent — Data Minimization & Access Control Filter.

Enforces:
- Data minimization: only required fields exposed per recruiter role
- No candidate profile is visible without permission rules
- Role-based access control (RBAC) for different recruiter types
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


class DataMinimizationFilter:
    """Filters candidate data based on recruiter role.

    Roles:
    - external_agency: minimal data (skills, seniority, domains — no PII)
    - hiring_manager: basic profile (name, skills, location)
    - internal_recruiter: full profile (all fields including salary, trajectory)
    - system: all fields (for internal processing only)
    """

    # Role → allowed fields mapping
    ROLE_FIELDS = {
        "external_agency": [
            "candidate_id",
            "skills",
            "seniority",
            "domains",
            "years_of_experience",
            "confidence_score",
        ],
        "hiring_manager": [
            "candidate_id",
            "full_name",
            "skills",
            "seniority",
            "domains",
            "years_of_experience",
            "location",
            "confidence_score",
        ],
        "internal_recruiter": [
            "candidate_id",
            "full_name",
            "skills",
            "seniority",
            "domains",
            "years_of_experience",
            "salary_expectation",
            "location",
            "willing_to_relocate",
            "career_trajectory",
            "confidence_score",
        ],
        "system": [
            "candidate_id",
            "full_name",
            "skills",
            "seniority",
            "domains",
            "years_of_experience",
            "salary_expectation",
            "location",
            "willing_to_relocate",
            "career_trajectory",
            "consent_status",
            "confidence_score",
            "raw_cv_s3_key",
            "embedding",
        ],
    }

    # Fields that are NEVER exposed to humans
    NEVER_EXPOSED = ["embedding", "raw_cv_s3_key"]

    def __init__(self):
        self._valid_roles = set(self.ROLE_FIELDS.keys())

    def filter_profile(self, profile: dict, recruiter_role: str) -> dict:
        """Apply data minimization to a candidate profile.

        Args:
            profile: Full candidate profile dict
            recruiter_role: One of external_agency, hiring_manager,
                          internal_recruiter, system

        Returns:
            Filtered dict with only the fields the role is authorized to see.
            Returns error dict if consent is not active.
        """
        role = recruiter_role.lower().strip()

        if role not in self._valid_roles:
            logger.warning(f"Unknown recruiter role '{role}', defaulting to external_agency")
            role = "external_agency"

        # Consent check
        consent_status = profile.get("consent_status", "pending")
        if consent_status != "granted":
            return self._consent_denied_response(profile, consent_status)

        allowed = set(self.ROLE_FIELDS[role])

        # Filter profile to only allowed fields
        filtered = {}
        for key, value in profile.items():
            if key in allowed and key not in self.NEVER_EXPOSED:
                if value is not None:
                    filtered[key] = value

        # Add audit metadata
        filtered["_access_role"] = role
        filtered["_data_minimized"] = True

        return filtered

    def filter_match_result(self, match: dict, recruiter_role: str) -> dict:
        """Apply data minimization to a match result.

        Strips full profile from match results and keeps only
        the scores and minimal candidate info the role should see.
        """
        role = recruiter_role.lower().strip()
        if role not in self._valid_roles:
            role = "external_agency"

        allowed = set(self.ROLE_FIELDS[role])

        safe_match = {
            k: v for k, v in match.items()
            if k in allowed or k.startswith("_") or k in (
                "match_id", "job_id", "candidate_id", "overall_score",
                "confidence", "breakdown", "explanation", "created_at",
            )
        }
        safe_match["_data_minimized"] = True
        return safe_match

    def validate_role_access(self, candidate_profile: dict, recruiter_role: str) -> bool:
        """Quick pre-check: can this role access this candidate at all?"""
        consent = candidate_profile.get("consent_status", "pending")
        if consent != "granted":
            return False
        return recruiter_role.lower().strip() in self._valid_roles

    def _consent_denied_response(self, profile: dict, status: str) -> dict:
        """Return minimal error when consent check fails."""
        return {
            "error": "Candidate data not available",
            "code": "CONSENT_DENIED",
            "consent_status": status,
            "candidate_id": profile.get("candidate_id"),
            "message": (
                "Consent has not been granted. "
                "Only anonymized match scores are available."
            ),
        }
