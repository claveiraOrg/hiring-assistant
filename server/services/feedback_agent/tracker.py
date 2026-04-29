"""Feedback Learning Agent — Recruiter Action Tracker.

Learns from recruiter interactions:
- Which candidates are viewed, shortlisted, interviewed, rejected, hired
- Which candidate attributes correlate with positive outcomes
- Aggregates signals to inform weight adjustment
"""

from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

logger = logging.getLogger(__name__)


# ─── Action types ───────────────────────────────────────────────────────

class RecruiterActionType:
    VIEW = "view"
    SHORTLIST = "shortlist"
    INTERVIEW = "interview"
    REJECT = "reject"
    HIRE = "hire"

    # Positive actions (signal a good match)
    POSITIVE = {SHORTLIST, INTERVIEW, HIRE}

    # Negative actions (signal a poor match)
    NEGATIVE = {REJECT}

    # Neutral actions (for analytics only)
    NEUTRAL = {VIEW}


# ─── Domain models ──────────────────────────────────────────────────────

@dataclass
class RecruiterAction:
    action_id: UUID
    recruiter_id: str
    candidate_id: UUID
    job_id: UUID
    action: str
    timestamp: datetime
    context: dict = field(default_factory=dict)

    def is_positive(self) -> bool:
        return self.action in RecruiterActionType.POSITIVE

    def is_negative(self) -> bool:
        return self.action in RecruiterActionType.NEGATIVE


@dataclass
class CandidateEngagement:
    engagement_id: UUID
    candidate_id: UUID
    job_id: UUID
    action: str  # applied, responded, interviewed, accepted, declined
    timestamp: datetime


@dataclass
class MatchFeedback:
    """Aggregated feedback for a single match (candidate-job pair)."""
    job_id: UUID
    candidate_id: UUID
    recruiter_actions: list[RecruiterAction] = field(default_factory=list)
    candidate_actions: list[CandidateEngagement] = field(default_factory=list)
    outcome: str | None = None  # hired, rejected, pending

    @property
    def recruiter_signal(self) -> float:
        """Net positive signal from recruiter actions. Range: -1.0 to 1.0."""
        if not self.recruiter_actions:
            return 0.0

        score = 0.0
        for action in self.recruiter_actions:
            if action.is_positive():
                score += 1.0
            elif action.is_negative():
                score -= 1.0
        return max(-1.0, min(1.0, score / max(len(self.recruiter_actions), 1)))


# ─── Tracker ────────────────────────────────────────────────────────────

class RecruiterActionTracker:
    """Records and analyzes recruiter actions for feedback learning."""

    def __init__(self):
        self._actions: list[RecruiterAction] = []
        self._engagements: list[CandidateEngagement] = []

    async def record_action(
        self,
        recruiter_id: str,
        candidate_id: UUID,
        job_id: UUID,
        action: str,
        context: dict | None = None,
    ) -> RecruiterAction:
        """Record a recruiter action on a candidate-job pair."""
        if action not in (RecruiterActionType.VIEW, RecruiterActionType.SHORTLIST,
                          RecruiterActionType.INTERVIEW, RecruiterActionType.REJECT,
                          RecruiterActionType.HIRE):
            raise ValueError(f"Unknown recruiter action: {action}")

        record = RecruiterAction(
            action_id=uuid4(),
            recruiter_id=recruiter_id,
            candidate_id=candidate_id,
            job_id=job_id,
            action=action,
            timestamp=datetime.utcnow(),
            context=context or {},
        )
        self._actions.append(record)
        logger.info(f"Recruiter action: {recruiter_id} -> {action} on {candidate_id} for {job_id}")
        return record

    async def record_engagement(
        self,
        candidate_id: UUID,
        job_id: UUID,
        action: str,
    ) -> CandidateEngagement:
        """Record a candidate engagement action."""
        record = CandidateEngagement(
            engagement_id=uuid4(),
            candidate_id=candidate_id,
            job_id=job_id,
            action=action,
            timestamp=datetime.utcnow(),
        )
        self._engagements.append(record)
        logger.info(f"Candidate engagement: {candidate_id} -> {action} for {job_id}")
        return record

    async def get_feedback_for_match(self, candidate_id: UUID, job_id: UUID) -> MatchFeedback:
        """Get aggregated feedback for a specific match."""
        return MatchFeedback(
            job_id=job_id,
            candidate_id=candidate_id,
            recruiter_actions=[a for a in self._actions
                               if a.candidate_id == candidate_id and a.job_id == job_id],
            candidate_actions=[e for e in self._engagements
                               if e.candidate_id == candidate_id and e.job_id == job_id],
        )

    async def get_feedback_for_job(self, job_id: UUID) -> list[MatchFeedback]:
        """Get all feedback for a specific job."""
        matches = defaultdict(list)
        for a in self._actions:
            if a.job_id == job_id:
                matches[a.candidate_id].append(a)
        return [
            MatchFeedback(job_id=job_id, candidate_id=cid, recruiter_actions=actions)
            for cid, actions in matches.items()
        ]

    async def get_action_stats(self) -> dict:
        """Get aggregate action statistics."""
        stats: dict[str, int] = defaultdict(int)
        for a in self._actions:
            stats[a.action] += 1
        for e in self._engagements:
            stats[f"candidate_{e.action}"] += 1
        return dict(stats)

    @property
    def total_actions(self) -> int:
        return len(self._actions)

    @property
    def total_engagements(self) -> int:
        return len(self._engagements)
