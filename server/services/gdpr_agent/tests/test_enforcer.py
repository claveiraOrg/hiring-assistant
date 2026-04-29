"""Tests for the GDPR Compliance Agent — consent, minimization, audit, deletion."""

import pytest
from uuid import uuid4
from datetime import datetime

from services.gdpr_agent.enforcer import (
    ROLE_FIELD_MAP,
    SENSITIVE_FIELDS,
    ConsentManager,
    DataMinimizationFilter,
    DeletionHandler,
)
from src.schemas import (
    AccessAuditEvent,
    CandidateProfile,
    GDPRConsentStatus,
    SeniorityLevel,
)


class TestRolePermissionMap:
    def test_external_agency_limited_fields(self):
        fields = ROLE_FIELD_MAP["external_agency"]
        assert "candidate_id" in fields
        assert "full_name" not in fields  # PII not exposed
        assert "salary_expectation" not in fields
        assert "career_trajectory" not in fields

    def test_hiring_manager_gets_name(self):
        fields = ROLE_FIELD_MAP["hiring_manager"]
        assert "full_name" in fields
        assert "salary_expectation" not in fields  # sensitive

    def test_internal_recruiter_full_access(self):
        fields = ROLE_FIELD_MAP["internal_recruiter"]
        assert "salary_expectation" in fields
        assert "career_trajectory" in fields
        assert "willing_to_relocate" in fields


class TestSensitiveFields:
    def test_salary_is_sensitive(self):
        assert "salary_expectation" in SENSITIVE_FIELDS

    def test_full_name_is_sensitive(self):
        assert "full_name" in SENSITIVE_FIELDS


class TestDataMinimizationFilter:
    @pytest.mark.asyncio
    async def test_allowed_role_gets_correct_fields(self):
        """Test that different roles get different field sets."""
        profile = {
            "candidate_id": str(uuid4()),
            "full_name": "Jane Doe",
            "skills": ["Python"],
            "seniority": "senior",
            "domains": ["FinTech"],
            "years_of_experience": 5,
            "salary_expectation": 150000,
            "location": "London",
            "consent_status": "granted",
            "data_scope": ["all"],
        }

        class MockAuditRepo:
            async def write(self, event):
                pass

        filter_agent = DataMinimizationFilter(MockAuditRepo())

        # Agency should NOT get full_name
        agency_result = await filter_agent.filter_profile(
            profile, "external_agency", uuid4(), "recruiter-1"
        )
        assert "full_name" not in agency_result.filtered_profile

        # Hiring manager SHOULD get name
        hm_result = await filter_agent.filter_profile(
            profile, "hiring_manager", uuid4(), "recruiter-2"
        )
        assert hm_result.filtered_profile.get("full_name") == "Jane Doe"

        # Internal recruiter SHOULD get salary
        ir_result = await filter_agent.filter_profile(
            profile, "internal_recruiter", uuid4(), "recruiter-3"
        )
        assert "salary_expectation" in ir_result.filtered_profile

    @pytest.mark.asyncio
    async def test_no_consent_blocks_profile(self):
        """Profile without consent returns error."""
        profile = {
            "candidate_id": str(uuid4()),
            "full_name": "Jane Doe",
            "skills": ["Python"],
            "consent_status": "pending",
        }

        class MockAuditRepo:
            async def write(self, event):
                pass

        filter_agent = DataMinimizationFilter(MockAuditRepo())
        result = await filter_agent.filter_profile(
            profile, "internal_recruiter", uuid4(), "recruiter-1"
        )
        assert "error" in result.filtered_profile

    @pytest.mark.asyncio
    async def test_filter_logs_audit_event(self):
        """Every access must produce an audit event."""
        profile = {
            "candidate_id": str(uuid4()),
            "full_name": "Jane Doe",
            "skills": ["Python"],
            "consent_status": "granted",
            "data_scope": ["all"],
        }

        events = []

        class RecordingAuditRepo:
            async def write(self, event):
                events.append(event)

        filter_agent = DataMinimizationFilter(RecordingAuditRepo())
        cid = uuid4()
        await filter_agent.filter_profile(profile, "hiring_manager", cid, "recruiter-1")

        assert len(events) == 1
        assert events[0].resource_id == cid
        assert events[0].granted is True
        assert events[0].action == "view_profile"


class TestConsentManager:
    @pytest.mark.asyncio
    async def test_no_consent_returns_pending(self):
        class MockConsentRepo:
            async def get_active(self, cid):
                return None

        class MockAuditRepo:
            pass

        cm = ConsentManager(MockConsentRepo(), MockAuditRepo())
        result = await cm.verify_consent(uuid4())
        assert result.allowed is False
        assert result.consent_status == GDPRConsentStatus.PENDING

    @pytest.mark.asyncio
    async def test_revoked_consent_blocks_access(self):
        class MockConsent:
            status = "revoked"
            expires_at = None

        class MockConsentRepo:
            async def get_active(self, cid):
                return MockConsent()

        cm = ConsentManager(MockConsentRepo(), None)
        result = await cm.verify_consent(uuid4())
        assert result.allowed is False
        assert result.consent_status == GDPRConsentStatus.REVOKED


class TestDeletionHandler:
    @pytest.mark.asyncio
    async def test_cascade_delete_returns_records(self):
        class MockCandidateRepo:
            async def cascade_delete(self, cid):
                return ["candidate", "consent", "matches"]

        handler = DeletionHandler(MockCandidateRepo())
        result = await handler.cascade_delete(uuid4(), "recruiter-1")
        assert result.status == "deleted"
        assert "candidate" in result.deleted_records
        assert "audit_logs_anonymized" in result.deleted_records
