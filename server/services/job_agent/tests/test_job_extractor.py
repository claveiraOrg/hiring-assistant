"""Tests for the Job Intelligence Agent.

Covers:
- Job intent building from LLM output
- Ambiguity detection (LLM + local)
- Salary range parsing
- Edge cases (missing data, contradictions)
"""

import pytest
from uuid import uuid4
from datetime import datetime

from services.job_agent.extractor import JobIntentBuilder, JobLLMClient
from src.schemas import SeniorityLevel


# ─── Job Intent Building ────────────────────────────────────────────────

class TestJobIntentBuilder:
    def test_build_full_job(self):
        """Well-structured LLM output produces complete job intent."""
        extracted = {
            "title": "Senior ML Engineer",
            "required_skills": ["Python", "Machine Learning", "SQL"],
            "preferred_skills": ["Kubernetes", "AWS"],
            "seniority": "senior",
            "years_experience_required": 5,
            "domains": ["FinTech", "AI/ML"],
            "salary_min": 130000,
            "salary_max": 180000,
            "location": "London",
            "remote_allowed": False,
            "confidence_score": 0.95,
            "ambiguities": [],
        }

        builder = JobIntentBuilder()
        job, ambiguities = builder.build(extracted, uuid4())

        assert job.title == "Senior ML Engineer"
        assert job.required_skills == ["Python", "Machine Learning", "SQL"]
        assert job.preferred_skills == ["Kubernetes", "AWS"]
        assert job.seniority == SeniorityLevel.SENIOR
        assert job.years_experience_required == 5
        assert job.domains == ["FinTech", "AI/ML"]
        assert job.salary_range == (130000, 180000)
        assert job.location == "London"
        assert job.remote_allowed is False
        assert job.confidence_score == 0.95

    def test_build_minimal_job(self):
        """Minimal output should still produce valid job with defaults."""
        extracted = {
            "title": "Engineer",
            "required_skills": [],
            "seniority": None,
            "domains": [],
            "confidence_score": 0.3,
        }
        builder = JobIntentBuilder()
        job, ambiguities = builder.build(extracted, uuid4())

        assert job.title == "Engineer"
        assert job.required_skills == []
        assert job.seniority == SeniorityLevel.MID  # default
        assert job.years_experience_required == 0
        assert job.salary_range is None

    def test_salary_range_single_value(self):
        """Single salary value should create a range with 1.3x multiplier."""
        extracted = {
            "title": "Dev",
            "required_skills": [],
            "salary_min": 100000,
            "seniority": "mid",
            "domains": [],
            "confidence_score": 0.5,
        }
        builder = JobIntentBuilder()
        job, _ = builder.build(extracted, uuid4())
        assert job.salary_range is not None
        assert job.salary_range[0] == 100000  # min
        assert job.salary_range[1] == 130000  # min * 1.3

    def test_ambiguity_parsing(self):
        """LLM-returned ambiguities should be parsed correctly."""
        extracted = {
            "title": "Senior Role",
            "required_skills": ["Python"],
            "seniority": "senior",
            "domains": [],
            "confidence_score": 0.7,
            "ambiguities": [
                {"field": "salary_range", "description": "No salary mentioned", "severity": "info"},
                {"field": "years_experience_required", "description": "1 year exp for senior role", "severity": "warning"},
            ],
        }
        builder = JobIntentBuilder()
        job, ambiguities = builder.build(extracted, uuid4())

        assert len(ambiguities) == 2
        assert ambiguities[0].field == "salary_range"
        assert ambiguities[0].severity == "info"
        assert ambiguities[1].field == "years_experience_required"
        assert ambiguities[1].severity == "warning"

    @pytest.mark.asyncio
    async def test_all_seniority_levels(self):
        """All seniority levels should map correctly."""
        builder = JobIntentBuilder()
        for level_str, level_enum in [
            ("junior", SeniorityLevel.JUNIOR),
            ("mid", SeniorityLevel.MID),
            ("senior", SeniorityLevel.SENIOR),
            ("staff", SeniorityLevel.STAFF),
            ("principal", SeniorityLevel.PRINCIPAL),
            ("executive", SeniorityLevel.EXECUTIVE),
        ]:
            extracted = {
                "title": "Role",
                "required_skills": [],
                "seniority": level_str,
                "domains": [],
                "confidence_score": 0.5,
            }
            job, _ = builder.build(extracted, uuid4())
            assert job.seniority == level_enum, f"Failed for {level_str}"


# ─── Local Ambiguity Detection ──────────────────────────────────────────

class TestLocalAmbiguityDetection:
    def test_seniority_mismatch(self):
        """Both junior and senior keywords should trigger ambiguity."""
        jd = "We need a junior developer with senior-level skills..."
        builder = JobIntentBuilder()
        ambiguities = builder.extract_ambiguities_local(jd)

        seniority_amb = [a for a in ambiguities if a.field == "seniority"]
        assert len(seniority_amb) >= 1
        assert seniority_amb[0].severity == "warning"

    def test_remote_on_site_conflict(self):
        """Both remote and on-site should trigger error."""
        jd = "Remote work available. Must be in office 5 days a week."
        builder = JobIntentBuilder()
        ambiguities = builder.extract_ambiguities_local(jd)

        remote_amb = [a for a in ambiguities if a.field == "remote_allowed"]
        assert len(remote_amb) >= 1
        assert remote_amb[0].severity == "error"

    def test_no_salary_mentioned(self):
        """Missing salary should trigger info-level warning."""
        jd = "Looking for a Python developer. Great team culture."
        builder = JobIntentBuilder()
        ambiguities = builder.extract_ambiguities_local(jd)

        salary_amb = [a for a in ambiguities if a.field == "salary_range"]
        assert len(salary_amb) >= 1
        assert salary_amb[0].severity == "info"

    def test_clear_no_ambiguities(self):
        """Well-specified JD should have minimal local ambiguities."""
        jd = """Senior Software Engineer at FinTech company.
        Salary: £120k-£150k.
        Fully remote position.
        Requirements: 5+ years Python experience.
        """
        builder = JobIntentBuilder()
        ambiguities = builder.extract_ambiguities_local(jd)

        # Should NOT have remote conflict or salary warnings
        remote_amb = [a for a in ambiguities if a.field == "remote_allowed" and a.severity == "error"]
        assert len(remote_amb) == 0


# ─── LLM Response Parsing ──────────────────────────────────────────────

class TestJobLLMResponseParsing:
    def test_parse_valid_json(self):
        client = JobLLMClient(api_key="test")
        result = client._parse_response('{"title": "Engineer", "required_skills": ["Python"]}')
        assert result["title"] == "Engineer"

    def test_parse_with_markdown(self):
        client = JobLLMClient(api_key="test")
        result = client._parse_response('```\n{"title": "Dev"}\n```')
        assert result["title"] == "Dev"

    def test_extract_json_from_text(self):
        client = JobLLMClient(api_key="test")
        result = client._parse_response(
            'Here is the job: {"title": "SWE", "required_skills": ["Go"]}.'
        )
        assert result["title"] == "SWE"

    def test_invalid_raises(self):
        client = JobLLMClient(api_key="test")
        with pytest.raises(ValueError):
            client._parse_response("not json")


# ─── Edge Cases ─────────────────────────────────────────────────────────

class TestJobEdgeCases:
    def test_confidence_bounds(self):
        """Confidence should always be clamped to [0, 1]."""
        builder = JobIntentBuilder()

        for conf, expected_clamped in [(1.5, 1.0), (-0.5, 0.0), (0.8, 0.8)]:
            extracted = {
                "title": "Role",
                "required_skills": [],
                "seniority": "mid",
                "domains": [],
                "confidence_score": conf,
            }
            job, _ = builder.build(extracted, uuid4())
            assert job.confidence_score == expected_clamped

    def test_empty_jd_ambiguities(self):
        """Empty JD should still produce a valid result."""
        jd = ""
        builder = JobIntentBuilder()
        ambiguities = builder.extract_ambiguities_local(jd)
        assert isinstance(ambiguities, list)  # Should not crash

    def test_salary_range_only_max(self):
        """Only max salary specified should create range."""
        builder = JobIntentBuilder()
        extracted = {
            "title": "Dev",
            "required_skills": [],
            "salary_max": 150000,
            "seniority": "mid",
            "domains": [],
            "confidence_score": 0.5,
        }
        job, _ = builder.build(extracted, uuid4())
        assert job.salary_range is not None
        assert job.salary_range[1] == 150000
        assert job.salary_range[0] == 105000  # max * 0.7
