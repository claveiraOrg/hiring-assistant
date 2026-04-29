from uuid import UUID, uuid4
from datetime import datetime

from src.schemas.base import SeniorityLevel, MatchConfidence, GDPRConsentStatus
from src.schemas.profile import CandidateProfile
from src.schemas.job import StructuredJobIntent
from src.schemas.match import MatchResult, RankedShortlist, ScoreBreakdown
from src.schemas.gdpr import ConsentRecord, AccessAuditEvent


def test_candidate_profile_schema():
    """Verify CandidateProfile validates correctly."""
    profile = CandidateProfile(
        full_name="Jane Doe",
        skills=["Python", "Machine Learning", "SQL"],
        years_of_experience=5.0,
        seniority=SeniorityLevel.SENIOR,
        domains=["FinTech", "SaaS"],
        career_trajectory=[{"role": "ML Engineer", "company": "Acme", "start_date": "2020-01"}],
        confidence_score=0.85,
    )
    assert isinstance(profile.candidate_id, UUID)
    assert profile.full_name == "Jane Doe"
    assert profile.consent_status == GDPRConsentStatus.PENDING
    assert profile.confidence_score == 0.85
    assert len(profile.skills) == 3
    assert profile.career_trajectory[0]["role"] == "ML Engineer"


def test_job_intent_schema():
    """Verify StructuredJobIntent validates correctly."""
    job = StructuredJobIntent(
        title="Senior ML Engineer",
        required_skills=["Python", "PyTorch", "AWS"],
        seniority=SeniorityLevel.SENIOR,
        years_experience_required=5,
        domains=["AI/ML"],
        salary_range=(120000, 180000),
        location="Remote",
        remote_allowed=True,
        confidence_score=0.9,
    )
    assert isinstance(job.job_id, UUID)
    assert len(job.required_skills) == 3
    assert job.salary_range == (120000, 180000)
    assert job.remote_allowed is True
    assert job.ambiguities == []


def test_score_breakdown_schema():
    """Verify ScoreBreakdown validates correctly."""
    breakdown = ScoreBreakdown(
        skills_score=0.85,
        experience_score=0.75,
        domain_score=0.60,
        salary_fit_score=1.0,
        location_fit_score=0.8,
    )
    assert breakdown.skills_score == 0.85
    assert breakdown.experience_score == 0.75
    # Verify all values are in range
    for val in [breakdown.skills_score, breakdown.experience_score,
                breakdown.domain_score, breakdown.salary_fit_score,
                breakdown.location_fit_score]:
        assert 0 <= val <= 1


def test_match_result_schema():
    """Verify MatchResult validates correctly."""
    breakdown = ScoreBreakdown(
        skills_score=0.85, experience_score=0.75,
        domain_score=0.60, salary_fit_score=1.0, location_fit_score=0.8,
    )
    match = MatchResult(
        job_id=uuid4(),
        candidate_id=uuid4(),
        overall_score=0.82,
        confidence=MatchConfidence.HIGH,
        breakdown=breakdown,
        explanation="Strong skill match with Python and ML. Seniority aligns well.",
    )
    assert match.confidence == MatchConfidence.HIGH
    assert match.overall_score == 0.82
    assert "Python" in match.explanation


def test_ranked_shortlist_schema():
    """Verify RankedShortlist validates correctly."""
    breakdown = ScoreBreakdown(
        skills_score=0.9, experience_score=0.8,
        domain_score=0.7, salary_fit_score=1.0, location_fit_score=0.9,
    )
    matches = [
        MatchResult(
            job_id=uuid4(), candidate_id=uuid4(),
            overall_score=0.87, confidence=MatchConfidence.HIGH,
            breakdown=breakdown, explanation="Great match",
        )
        for _ in range(3)
    ]
    shortlist = RankedShortlist(
        job_id=uuid4(),
        matches=matches,
        total_candidates_scored=50,
        processing_time_ms=4200,
    )
    assert len(shortlist.matches) == 3
    assert shortlist.total_candidates_scored == 50
    assert shortlist.processing_time_ms == 4200


def test_consent_record_schema():
    """Verify ConsentRecord validates correctly."""
    consent = ConsentRecord(
        candidate_id=uuid4(),
        status=GDPRConsentStatus.GRANTED,
        granted_at=datetime.utcnow(),
        data_scope=["profile", "skills", "location"],
    )
    assert consent.status == GDPRConsentStatus.GRANTED
    assert "skills" in consent.data_scope


def test_audit_event_schema():
    """Verify AccessAuditEvent validates correctly."""
    event = AccessAuditEvent(
        actor_id="recruiter_42",
        action="view_profile",
        resource_type="candidate",
        resource_id=uuid4(),
        granted=True,
        reason="Matched to job JD-123 — recruiter needs to review profile",
    )
    assert event.actor_id == "recruiter_42"
    assert event.granted is True
    assert event.action == "view_profile"


def test_gdpr_consent_enum_values():
    """Verify GDPR consent lifecycle states."""
    assert "granted" in [e.value for e in GDPRConsentStatus]
    assert "revoked" in [e.value for e in GDPRConsentStatus]
    assert "pending" in [e.value for e in GDPRConsentStatus]
    assert "expired" in [e.value for e in GDPRConsentStatus]


def test_seniority_level_ordering():
    """Verify seniority enum values are sensible."""
    levels = list(SeniorityLevel)
    assert levels.index(SeniorityLevel.JUNIOR) < levels.index(SeniorityLevel.SENIOR)
    assert levels.index(SeniorityLevel.SENIOR) < levels.index(SeniorityLevel.EXECUTIVE)
