"""Tests for the Matching Agent scoring engine.

Covers all 5 scoring dimensions + confidence + explainability + edge cases.
"""

import pytest
from uuid import uuid4
from datetime import datetime

from services.matching_agent.matcher import (
    WEIGHTS,
    batch_score,
    compute_confidence,
    compute_domain_score,
    compute_experience_score,
    compute_location_fit,
    compute_salary_fit,
    compute_skills_score,
    score_match,
)
from src.schemas import (
    CandidateProfile,
    MatchConfidence,
    ScoreBreakdown,
    SeniorityLevel,
    StructuredJobIntent,
)

# ─── Fixtures ────────────────────────────────────────────────────────────

@pytest.fixture
def sample_candidate() -> CandidateProfile:
    return CandidateProfile(
        candidate_id=uuid4(),
        full_name="Alice Engineer",
        skills=["Python", "Machine Learning", "SQL", "Kubernetes"],
        years_of_experience=6,
        seniority=SeniorityLevel.SENIOR,
        domains=["FinTech", "SaaS"],
        salary_expectation=150_000,
        location="London",
        willing_to_relocate=False,
        confidence_score=0.90,
        created_at=datetime.utcnow(),
    )


@pytest.fixture
def sample_job() -> StructuredJobIntent:
    return StructuredJobIntent(
        job_id=uuid4(),
        title="Senior ML Engineer",
        required_skills=["Python", "Machine Learning", "SQL"],
        preferred_skills=["Kubernetes", "AWS"],
        seniority=SeniorityLevel.SENIOR,
        years_experience_required=5,
        domains=["FinTech", "AI/ML"],
        salary_range=(130_000, 180_000),
        location="London",
        remote_allowed=False,
        confidence_score=0.95,
        created_at=datetime.utcnow(),
    )


# ─── Skills Score ───────────────────────────────────────────────────────

class TestSkillsScore:
    def test_exact_required_match(self):
        """Candidate has all required skills. Score = 0.8 * 1.0 + 0.2 * 0.0 = 0.80."""
        score = compute_skills_score(
            ["Python", "ML", "SQL"], ["Python", "ML", "SQL"], []
        )
        assert score == 0.80

    def test_partial_required_match(self):
        """Candidate missing some required skills."""
        score = compute_skills_score(
            ["Python"], ["Python", "ML", "SQL"], []
        )
        assert score < 0.5  # 1/3 = 0.33 * 0.8 = 0.26

    def test_preferred_skills_bonus(self):
        """Preferred skills add bonus when candidate has them."""
        # Candidate has both required and preferred skills
        score_with_prefs = compute_skills_score(
            ["Python", "Kubernetes"], ["Python"], ["Kubernetes", "AWS"]
        )
        # Same candidate skills but no preferred list
        score_without_prefs = compute_skills_score(
            ["Python", "Kubernetes"], ["Python"], []
        )
        assert score_with_prefs > score_without_prefs
        # 0.8 * 1.0 + 0.2 * 0.5 = 0.90 vs 0.8 * 1.0 + 0.2 * 0.0 = 0.80
        assert score_with_prefs == 0.90
        assert score_without_prefs == 0.80

    def test_no_skill_requirements(self):
        """No requirements should return neutral score."""
        score = compute_skills_score(["Python"], [], [])
        assert score == 0.5

    def test_empty_candidate_skills(self):
        """Candidate has no listed skills."""
        score = compute_skills_score([], ["Python", "ML"], [])
        assert score == 0.0

    def test_case_insensitive(self):
        """Matching should be case-insensitive. 2/2 required = 1.0 * 0.8 = 0.80."""
        score = compute_skills_score(
            ["python", "ml"], ["Python", "ML"], []
        )
        assert score == 0.80


# ─── Experience Score ───────────────────────────────────────────────────

class TestExperienceScore:
    def test_exact_level_and_years(self):
        """Same seniority + meets years requirement."""
        score = compute_experience_score(5, 5, "senior", "senior")
        assert score >= 0.90

    def test_underqualified_experience(self):
        """Candidate has fewer years than required."""
        score = compute_experience_score(1, 5, "junior", "senior")
        assert score < 0.5

    def test_overqualified_bonus(self):
        """Significantly more years = slight bonus but capped."""
        score = compute_experience_score(15, 5, "senior", "senior")
        assert score <= 1.0
        assert score >= 0.90

    def test_one_off_seniority(self):
        """One level off should still score decently."""
        score = compute_experience_score(5, 5, "mid", "senior")
        # seniority: 0.6 * 0.7 = 0.42, years: 0.4 * 1.0 = 0.4 => 0.82
        assert 0.70 <= score <= 0.95

    def test_no_required_years(self):
        """No years requirement = neutral years component."""
        score = compute_experience_score(3, 0, "senior", "senior")
        # seniority: 0.6 * 1.0 + years: 0.4 * 0.5 = 0.8
        assert score >= 0.70


# ─── Domain Score ───────────────────────────────────────────────────────

class TestDomainScore:
    def test_exact_domain_match(self):
        score = compute_domain_score(["FinTech", "SaaS"], ["FinTech", "SaaS"])
        assert score >= 0.95

    def test_partial_overlap(self):
        score = compute_domain_score(["FinTech"], ["FinTech", "Healthcare"])
        assert 0.4 < score < 0.6  # Jaccard = 1/3

    def test_no_overlap(self):
        score = compute_domain_score(["Gaming"], ["Healthcare"])
        assert score == 0.0

    def test_candidate_no_domains(self):
        score = compute_domain_score([], ["FinTech"])
        assert score == 0.0

    def test_job_no_domains(self):
        score = compute_domain_score(["FinTech"], [])
        assert score == 0.5


# ─── Salary Fit Score ───────────────────────────────────────────────────

class TestSalaryFit:
    def test_within_range(self):
        score = compute_salary_fit(150_000, (130_000, 180_000))
        assert score == 1.0

    def test_below_range(self):
        score = compute_salary_fit(100_000, (130_000, 180_000))
        assert 0.5 < score < 1.0

    def test_above_range(self):
        score = compute_salary_fit(250_000, (130_000, 180_000))
        assert score < 0.5

    def test_no_salary_data(self):
        score = compute_salary_fit(None, (130_000, 180_000))
        assert score == 0.5

        score = compute_salary_fit(150_000, None)
        assert score == 0.5

    def test_exact_boundary(self):
        """Candidate salary at exact range boundary counts as in-range."""
        score = compute_salary_fit(130_000, (130_000, 180_000))
        assert score == 1.0


# ─── Location Fit Score ─────────────────────────────────────────────────

class TestLocationFit:
    def test_exact_match(self):
        score = compute_location_fit("London", "London", False, False)
        assert score == 1.0

    def test_remote_job(self):
        """Remote-friendly = location doesn't matter."""
        score = compute_location_fit("Tokyo", "London", True, False)
        assert score == 1.0

    def test_willing_relocate(self):
        score = compute_location_fit("Tokyo", "London", False, True)
        assert score == 0.8

    def test_no_location_data(self):
        score = compute_location_fit(None, "London", False, False)
        assert score == 0.3

    def test_no_job_location(self):
        score = compute_location_fit("London", None, False, False)
        assert score == 0.5

    def test_no_match(self):
        """Different location, won't relocate, not remote."""
        score = compute_location_fit("Tokyo", "London", False, False)
        assert score == 0.0

    def test_case_insensitive_location(self):
        score = compute_location_fit("london", "London", False, False)
        assert score == 1.0


# ─── Confidence Scoring ─────────────────────────────────────────────────

class TestConfidence:
    def test_high_confidence(self):
        """High average, low variance = high confidence."""
        b = ScoreBreakdown(
            skills_score=0.90,
            experience_score=0.85,
            domain_score=0.80,
            salary_fit_score=0.90,
            location_fit_score=0.85,
        )
        assert compute_confidence(b) == MatchConfidence.HIGH

    def test_medium_confidence(self):
        """Moderate average score."""
        b = ScoreBreakdown(
            skills_score=0.60,
            experience_score=0.55,
            domain_score=0.50,
            salary_fit_score=0.70,
            location_fit_score=0.65,
        )
        assert compute_confidence(b) == MatchConfidence.MEDIUM

    def test_low_confidence(self):
        """Low average score."""
        b = ScoreBreakdown(
            skills_score=0.20,
            experience_score=0.10,
            domain_score=0.30,
            salary_fit_score=0.40,
            location_fit_score=0.50,
        )
        assert compute_confidence(b) == MatchConfidence.LOW


# ─── Weights ────────────────────────────────────────────────────────────

class TestWeights:
    def test_weights_sum_to_one(self):
        total = sum(WEIGHTS.values())
        assert abs(total - 1.0) < 0.001, f"Weights sum to {total}, expected 1.0"

    def test_individual_weights(self):
        assert WEIGHTS["skills_score"] == 0.40
        assert WEIGHTS["experience_score"] == 0.25
        assert WEIGHTS["domain_score"] == 0.15
        assert WEIGHTS["salary_fit_score"] == 0.10
        assert WEIGHTS["location_fit_score"] == 0.10


# ─── Integration: score_match ───────────────────────────────────────────

class TestScoreMatch:
    def test_full_match_pipeline(self, sample_candidate, sample_job):
        """End-to-end: candidate well-matched to job."""
        result = score_match(sample_candidate, sample_job)
        assert result["overall_score"] >= 0.70
        assert result["confidence"] in ("high", "medium")
        assert "skills_score" in result["breakdown"]
        assert result["explanation"]

    def test_poor_match(self, sample_job):
        """Candidate with completely mismatched profile."""
        bad_candidate = CandidateProfile(
            candidate_id=uuid4(),
            full_name="Bad Match",
            skills=["Cooking"],
            years_of_experience=0,
            seniority=SeniorityLevel.JUNIOR,
            domains=["Hospitality"],
            salary_expectation=300_000,
            location="Tokyo",
            willing_to_relocate=False,
            confidence_score=0.50,
            created_at=datetime.utcnow(),
        )
        result = score_match(bad_candidate, sample_job)
        assert result["overall_score"] < 0.30
        assert result["confidence"] == MatchConfidence.LOW.value

    def test_explainability_exists(self, sample_candidate, sample_job):
        """Every match must have an explanation."""
        result = score_match(sample_candidate, sample_job)
        assert result["explanation"]
        assert len(result["explanation"]) > 10

    def test_breakdown_components(self, sample_candidate, sample_job):
        """All 5 breakdown components present and bounded."""
        result = score_match(sample_candidate, sample_job)
        b = result["breakdown"]
        for key in ["skills_score", "experience_score", "domain_score",
                     "salary_fit_score", "location_fit_score"]:
            assert key in b
            assert 0.0 <= b[key] <= 1.0


# ─── Batch Scoring ──────────────────────────────────────────────────────

class TestBatchScore:
    def test_batch_returns_all_results(self, sample_job):
        candidates = [
            CandidateProfile(
                candidate_id=uuid4(),
                full_name=f"Candidate {i}",
                skills=["Python"],
                years_of_experience=i * 2,
                seniority=SeniorityLevel.MID if i < 3 else SeniorityLevel.SENIOR,
                domains=["Tech"],
                confidence_score=0.80,
                created_at=datetime.utcnow(),
            )
            for i in range(5)
        ]
        results = batch_score(candidates, sample_job)
        assert len(results) == 5
        # Verify all candidates got scored
        for r in results:
            assert "overall_score" in r
            assert "confidence" in r
            assert "breakdown" in r

    def test_empty_candidate_pool(self, sample_job):
        results = batch_score([], sample_job)
        assert results == []


# ─── Edge Cases ─────────────────────────────────────────────────────────

class TestEdgeCases:
    def test_missing_data_graceful(self, sample_job):
        """Candidate with minimal data should still produce a valid score."""
        minimal = CandidateProfile(
            candidate_id=uuid4(),
            full_name="Minimal",
            skills=[],
            years_of_experience=0,
            seniority=SeniorityLevel.JUNIOR,
            domains=[],
            confidence_score=0.0,
            created_at=datetime.utcnow(),
        )
        result = score_match(minimal, sample_job)
        assert 0.0 <= result["overall_score"] <= 1.0
        assert result["confidence"] in ("high", "medium", "low")

    def test_very_large_skill_sets(self):
        """Hundreds of skills shouldn't break scoring."""
        skills = [f"skill_{i}" for i in range(200)]
        score = compute_skills_score(skills[:150], skills[:100], skills[100:150])
        assert 0.0 <= score <= 1.0
        assert score >= 0.90  # good overlap

    def test_seniority_ladder_ends(self):
        """Bottom and top of seniority ladder."""
        # Junior vs Executive = 5 level gap
        score = compute_experience_score(0, 10, "junior", "executive")
        assert score < 0.3

    def test_negative_salary_range(self):
        """Edge case: invalid salary range should not crash."""
        score = compute_salary_fit(100_000, (0, 0))
        # Should handle gracefully
        assert 0.0 <= score <= 1.0
