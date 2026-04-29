"""Tests for the Profile Intelligence Agent.

Covers:
- Confidence scoring (LLM blend + quality check)
- Embedding generation (text construction)
- LLM response parsing (JSON extraction, markdown cleanup)
- Fallback extraction
- Edge cases (empty CV, missing fields)
"""

import json
from uuid import uuid4
from datetime import datetime

import pytest

from services.profile_agent.extractor import ConfidenceScorer, EmbeddingGenerator, LLMClient
from src.schemas import CandidateProfile, SeniorityLevel, GDPRConsentStatus


# ─── Confidence Scoring ─────────────────────────────────────────────────

class TestConfidenceScorer:
    def test_compute_full_profile(self):
        """Well-structured LLM output produces high-confidence profile."""
        llm_output = {
            "full_name": "Alice Engineer",
            "skills": ["Python", "Machine Learning", "SQL"],
            "years_of_experience": 6,
            "seniority": "senior",
            "domains": ["FinTech", "SaaS"],
            "career_trajectory": [
                {"role": "ML Engineer", "company": "Acme", "start_date": "2020-01", "end_date": "2023-06"}
            ],
            "salary_expectation": 150000,
            "location": "London",
            "willing_to_relocate": False,
            "confidence_score": 0.90,
            "confidence_breakdown": {
                "name_extracted": True,
                "skills_found": 3,
                "experience_determined": True,
                "seniority_determined": True,
                "domains_found": 2,
                "career_history_complete": True,
            },
        }

        scorer = ConfidenceScorer()
        # Inject ID and date for validation
        llm_output["candidate_id"] = uuid4()
        llm_output["created_at"] = datetime.utcnow()
        profile = scorer.compute(llm_output)

        assert profile.full_name == "Alice Engineer"
        assert len(profile.skills) == 3
        assert profile.years_of_experience == 6
        assert profile.seniority == SeniorityLevel.SENIOR
        assert len(profile.domains) == 2
        assert profile.salary_expectation == 150000
        assert profile.location == "London"
        assert profile.confidence_score >= 0.75  # LLM 0.9 * 0.6 + quality 1.0 * 0.4 = 0.94
        assert profile.consent_status == GDPRConsentStatus.PENDING

    def test_compute_minimal_profile(self):
        """Minimal profile should still produce valid output with low confidence."""
        llm_output = {
            "full_name": None,
            "skills": [],
            "years_of_experience": None,
            "seniority": None,
            "domains": [],
            "career_trajectory": [],
            "confidence_score": 0.30,
            "confidence_breakdown": {},
        }
        llm_output["candidate_id"] = uuid4()
        llm_output["created_at"] = datetime.utcnow()

        scorer = ConfidenceScorer()
        profile = scorer.compute(llm_output)

        assert profile.full_name == "Unknown"
        assert profile.skills == []
        assert profile.years_of_experience == 0
        assert profile.seniority == SeniorityLevel.MID  # default
        assert profile.confidence_score < 0.50

    def test_seniority_mapping(self):
        """All seniority levels should map correctly."""
        scorer = ConfidenceScorer()

        for level_str, level_enum in [
            ("junior", SeniorityLevel.JUNIOR),
            ("mid", SeniorityLevel.MID),
            ("senior", SeniorityLevel.SENIOR),
            ("staff", SeniorityLevel.STAFF),
            ("principal", SeniorityLevel.PRINCIPAL),
            ("executive", SeniorityLevel.EXECUTIVE),
        ]:
            output = {
                "seniority": level_str,
                "skills": [],
                "confidence_score": 0.5,
                "confidence_breakdown": {},
            }
            output["candidate_id"] = uuid4()
            output["created_at"] = datetime.utcnow()
            profile = scorer.compute(output)
            assert profile.seniority == level_enum, f"Failed for {level_str}"

    def test_career_trajectory_parsing(self):
        """Career trajectory entries should be parsed correctly."""
        output = {
            "full_name": "Test User",
            "skills": ["Python"],
            "years_of_experience": 5,
            "domains": ["Tech"],
            "career_trajectory": [
                {"role": "Engineer", "company": "Company A", "start_date": "2019-01", "end_date": "2022-06"},
                {"role": "Senior Engineer", "company": "Company B"},
            ],
            "confidence_score": 0.8,
            "confidence_breakdown": {},
        }
        output["candidate_id"] = uuid4()
        output["created_at"] = datetime.utcnow()

        scorer = ConfidenceScorer()
        profile = scorer.compute(output)

        assert len(profile.career_trajectory) == 2
        assert profile.career_trajectory[0].role == "Engineer"
        assert profile.career_trajectory[0].company == "Company A"
        assert profile.career_trajectory[1].role == "Senior Engineer"


# ─── Embedding Generation ───────────────────────────────────────────────

class TestEmbeddingGenerator:
    @pytest.mark.asyncio
    async def test_embedding_text_construction(self):
        """Should build a meaningful text string for embedding."""
        profile = CandidateProfile(
            candidate_id=uuid4(),
            full_name="Test User",
            skills=["Python", "Machine Learning"],
            years_of_experience=5,
            seniority=SeniorityLevel.SENIOR,
            domains=["FinTech"],
            confidence_score=0.8,
            created_at=datetime.utcnow(),
        )

        gen = EmbeddingGenerator()
        # Without API key, should return zero vector gracefully
        embedding = await gen.generate(profile)
        assert len(embedding) > 0
        # When no key set and openai not installed, returns zeros
        assert isinstance(embedding, list)

    @pytest.mark.asyncio
    async def test_local_embedding_fallback(self):
        """Local embedding should return zero vector without sentence-transformers."""
        gen = EmbeddingGenerator(provider="local")
        embedding = await gen.generate(CandidateProfile(
            candidate_id=uuid4(),
            full_name="Test",
            skills=["Python"],
            years_of_experience=3,
            seniority=SeniorityLevel.MID,
            domains=[],
            confidence_score=0.5,
            created_at=datetime.utcnow(),
        ))
        assert len(embedding) == 384  # default dimension


# ─── LLM Response Parsing ──────────────────────────────────────────────

class TestLLMResponseParsing:
    def test_parse_valid_json(self):
        client = LLMClient(api_key="test")
        result = client._parse_response('{"full_name": "Alice", "skills": ["Python"]}')
        assert result["full_name"] == "Alice"
        assert result["skills"] == ["Python"]

    def test_parse_json_with_markdown_fences(self):
        client = LLMClient(api_key="test")
        result = client._parse_response('```json\n{"full_name": "Bob"}\n```')
        assert result["full_name"] == "Bob"

    def test_parse_json_with_extra_text(self):
        client = LLMClient(api_key="test")
        result = client._parse_response(
            'Here is the extracted data:\n{"name": "Charlie", "age": 30}\nI hope this helps.'
        )
        assert result["name"] == "Charlie"

    def test_parse_invalid_json_raises(self):
        client = LLMClient(api_key="test")
        with pytest.raises(ValueError, match="Failed to parse"):
            client._parse_response("This is not JSON at all")

    def test_parse_empty_string_raises(self):
        client = LLMClient(api_key="test")
        with pytest.raises(ValueError, match="Failed to parse"):
            client._parse_response("")


# ─── Edge Cases ─────────────────────────────────────────────────────────

class TestProfileEdgeCases:
    def test_unknown_seniority_defaults_to_mid(self):
        scorer = ConfidenceScorer()
        output = {
            "seniority": "unknown_level",
            "skills": [],
            "confidence_score": 0.5,
            "confidence_breakdown": {},
        }
        output["candidate_id"] = uuid4()
        output["created_at"] = datetime.utcnow()
        profile = scorer.compute(output)
        assert profile.seniority == SeniorityLevel.MID

    def test_negative_experience_clamped(self):
        scorer = ConfidenceScorer()
        output = {
            "years_of_experience": -5,
            "skills": [],
            "confidence_score": 0.5,
            "confidence_breakdown": {},
        }
        output["candidate_id"] = uuid4()
        output["created_at"] = datetime.utcnow()
        profile = scorer.compute(output)
        assert profile.years_of_experience >= 0

    def test_confidence_bounds(self):
        """Confidence should always be in [0, 1]."""
        scorer = ConfidenceScorer()
        for conf in [2.0, -1.0, 1.5, -0.5]:
            output = {
                "skills": ["Python"],
                "confidence_score": conf,
                "confidence_breakdown": {},
            }
            output["candidate_id"] = uuid4()
            output["created_at"] = datetime.utcnow()
            profile = scorer.compute(output)
            assert 0.0 <= profile.confidence_score <= 1.0
