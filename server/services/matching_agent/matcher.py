"""Matching Agent — weighted scoring engine.

Computes candidate-job relevance scores across 5 dimensions:
- Skills (40%): Jaccard similarity on required + preferred skills
- Experience (25%): Seniority level alignment + years match
- Domain (15%): Industry/domain overlap
- Salary fit (10%): Compensation band compatibility
- Location fit (10%): Geographic + remote + relocation

Supports: batch inference, confidence scoring, explainability.
"""

from __future__ import annotations

from src.schemas import (
    CandidateProfile,
    MatchConfidence,
    MatchResult,
    ScoreBreakdown,
    StructuredJobIntent,
)

# ─── Weights (initial config — adjustable via Feedback Learning Agent in Phase 2) ──

SKILLS_WEIGHT = 0.40
EXPERIENCE_WEIGHT = 0.25
DOMAIN_WEIGHT = 0.15
SALARY_FIT_WEIGHT = 0.10
LOCATION_FIT_WEIGHT = 0.10

WEIGHTS = {
    "skills_score": SKILLS_WEIGHT,
    "experience_score": EXPERIENCE_WEIGHT,
    "domain_score": DOMAIN_WEIGHT,
    "salary_fit_score": SALARY_FIT_WEIGHT,
    "location_fit_score": LOCATION_FIT_WEIGHT,
}

# Seniority level ladder for comparison
_SENIORITY_LADDER = [
    "junior",
    "mid",
    "senior",
    "staff",
    "principal",
    "executive",
]


# ─── Dimension scorers ───────────────────────────────────────────────────

def compute_skills_score(
    candidate_skills: list[str],
    required_skills: list[str],
    preferred_skills: list[str] | None = None,
) -> float:
    """Skills match using weighted Jaccard similarity.

    Required skills are mandatory — missing a required skill is heavily penalized.
    Preferred skills are bonus — having them adds but not having them isn't fatal.
    """
    c_set = set(s.lower().strip() for s in candidate_skills)
    req_set = set(s.lower().strip() for s in required_skills)
    pref_set = set(s.lower().strip() for s in (preferred_skills or []))

    if not req_set and not pref_set:
        return 0.5  # no skill requirements = neutral score

    # Required skills: Jaccard-like (intersection/required_count)
    req_score = 0.0
    if req_set:
        req_overlap = len(req_set & c_set)
        req_score = req_overlap / len(req_set)

    # Preferred skills: bonus on top of required
    pref_score = 0.0
    if pref_set:
        pref_overlap = len(pref_set & c_set)
        pref_score = min(1.0, pref_overlap / max(1, len(pref_set)))

    # Blend: required is mandatory (80%), preferred is bonus (20%)
    return round(0.80 * req_score + 0.20 * pref_score, 4)


def compute_experience_score(
    candidate_years: float,
    required_years: int,
    candidate_seniority: str,
    required_seniority: str,
) -> float:
    """Experience score: 60% seniority alignment + 40% years match."""
    # Seniority level match
    c_level = candidate_seniority.lower().strip()
    r_level = required_seniority.lower().strip()

    seniority_score = 0.5  # default if levels unrecognized
    if c_level in _SENIORITY_LADDER and r_level in _SENIORITY_LADDER:
        level_diff = abs(_SENIORITY_LADDER.index(c_level) - _SENIORITY_LADDER.index(r_level))
        seniority_score = max(0.0, 1.0 - (level_diff * 0.3))
    elif c_level == r_level:
        seniority_score = 1.0
    elif r_level == "":
        seniority_score = 0.5

    # Years experience fit
    if required_years <= 0:
        years_score = 0.5
    elif candidate_years >= required_years:
        # Slight bonus for over-qualified (caps at +20%)
        over_qualify = min(0.20, (candidate_years - required_years) * 0.05)
        years_score = min(1.0, 1.0 + over_qualify)
    else:
        # Under-qualified: linear penalty
        years_score = candidate_years / required_years

    return round(0.60 * seniority_score + 0.40 * years_score, 4)


def compute_domain_score(
    candidate_domains: list[str],
    job_domains: list[str],
) -> float:
    """Domain overlap using true Jaccard similarity."""
    c_set = set(d.lower().strip() for d in candidate_domains)
    j_set = set(d.lower().strip() for d in job_domains)

    if not j_set:
        return 0.5  # no domain requirements = neutral
    if not c_set:
        return 0.0  # candidate has no domains = zero

    intersection = len(c_set & j_set)
    union = len(c_set | j_set)
    return round(intersection / union, 4)


def compute_salary_fit(
    candidate_salary: float | None,
    salary_range: tuple[float, float] | None,
) -> float:
    """Salary compatibility — candidate's expectation vs job's range."""
    if candidate_salary is None or salary_range is None:
        return 0.5  # no data = neutral

    min_sal, max_sal = salary_range
    if min_sal <= candidate_salary <= max_sal:
        return 1.0  # perfect fit

    midpoint = (min_sal + max_sal) / 2.0
    if candidate_salary < min_sal:
        # Candidate expects less than minimum — ratio-based
        ratio = candidate_salary / midpoint if midpoint > 0 else 0.5
        return round(min(1.0, 0.7 + 0.3 * (ratio / 0.8)), 4)
    else:
        # Candidate expects more than max — distance penalty
        overshoot = (candidate_salary - max_sal) / max_sal if max_sal > 0 else 1.0
        return round(max(0.0, 1.0 - overshoot * 2), 4)


def compute_location_fit(
    candidate_location: str | None,
    job_location: str | None,
    remote_allowed: bool,
    willing_to_relocate: bool,
) -> float:
    """Location compatibility — geography, remote policy, and relocation."""
    if job_location is None:
        return 0.5  # no location specified = neutral

    if remote_allowed:
        return 1.0  # remote-friendly = location irrelevant

    if candidate_location is None:
        return 0.3  # unknown candidate location = low compatibility

    if candidate_location.lower().strip() == job_location.lower().strip():
        return 1.0  # exact location match

    if willing_to_relocate:
        return 0.8  # willing to move = high but not perfect

    return 0.0  # no match, won't relocate


# ─── Confidence & explainability ─────────────────────────────────────────

def compute_confidence(breakdown: ScoreBreakdown) -> MatchConfidence:
    """Determine confidence based on score variance and completeness."""
    scores = [
        breakdown.skills_score,
        breakdown.experience_score,
        breakdown.domain_score,
        breakdown.salary_fit_score,
        breakdown.location_fit_score,
    ]
    avg = sum(scores) / len(scores)
    # Variance as a measure of consistency across dimensions
    variance = sum((s - avg) ** 2 for s in scores) / len(scores)
    # High avg + low variance = high confidence
    if avg >= 0.80 and variance < 0.05:
        return MatchConfidence.HIGH
    elif avg >= 0.50:
        return MatchConfidence.MEDIUM
    return MatchConfidence.LOW


def generate_explanation(
    breakdown: ScoreBreakdown,
    candidate: CandidateProfile | dict,
    job: StructuredJobIntent | dict,
) -> str:
    """Generate human-readable explanation for a match score."""
    parts = []

    if breakdown.skills_score >= 0.8:
        parts.append("strong skill match")
    elif breakdown.skills_score >= 0.5:
        parts.append("moderate skill overlap")
    elif breakdown.skills_score > 0:
        parts.append("limited skill alignment")

    if breakdown.experience_score >= 0.8:
        parts.append("experience level aligns well")
    elif breakdown.experience_score < 0.4:
        parts.append("experience gap")

    if breakdown.domain_score < 0.3 and breakdown.domain_score >= 0:
        parts.append("different domain background")

    if breakdown.location_fit_score < 0.3:
        c_loc = candidate.get("location") if isinstance(candidate, dict) else candidate.location
        parts.append(f"location constraint ({c_loc or 'unknown'} vs job location)")

    if breakdown.salary_fit_score < 0.5:
        parts.append("potential salary mismatch")

    if not parts:
        parts.append("balanced match across all dimensions")

    return "; ".join(parts[:3])  # max 3 explanation points for readability


# ─── Main scorer ─────────────────────────────────────────────────────────

def score_match(
    candidate: CandidateProfile | dict,
    job: StructuredJobIntent | dict,
) -> dict:
    """Compute full match score for one candidate-job pair.

    Returns dict with overall_score, confidence, breakdown, and explanation.
    This is the single-entry scoring function used by both online and batch paths.
    """
    # Convert Pydantic models to dict-like access if needed
    if hasattr(candidate, "model_dump"):
        c = candidate.model_dump()
    else:
        c = candidate
    if hasattr(job, "model_dump"):
        j = job.model_dump()
    else:
        j = job

    skills_score = compute_skills_score(
        c.get("skills", []),
        j.get("required_skills", []),
        j.get("preferred_skills"),
    )
    experience_score = compute_experience_score(
        c.get("years_of_experience", 0),
        j.get("years_experience_required", 0),
        c.get("seniority", "mid"),
        j.get("seniority", "mid"),
    )
    domain_score = compute_domain_score(
        c.get("domains", []),
        j.get("domains", []),
    )
    salary_fit = compute_salary_fit(
        c.get("salary_expectation"),
        j.get("salary_range"),
    )
    location_fit = compute_location_fit(
        c.get("location"),
        j.get("location"),
        j.get("remote_allowed", False),
        c.get("willing_to_relocate", False),
    )

    breakdown = ScoreBreakdown(
        skills_score=skills_score,
        experience_score=experience_score,
        domain_score=domain_score,
        salary_fit_score=salary_fit,
        location_fit_score=location_fit,
    )

    overall = sum(
        WEIGHTS[k] * getattr(breakdown, k)
        for k in WEIGHTS
    )
    overall = round(min(1.0, max(0.0, overall)), 4)

    confidence = compute_confidence(breakdown)
    explanation = generate_explanation(breakdown, c, j)

    return {
        "overall_score": overall,
        "confidence": confidence.value,
        "breakdown": breakdown.model_dump(),
        "explanation": explanation,
    }


def batch_score(
    candidates: list[CandidateProfile | dict],
    job: StructuredJobIntent | dict,
) -> list[dict]:
    """Score all candidates against a single job. Supports batch inference."""
    return [score_match(c, job) for c in candidates]
