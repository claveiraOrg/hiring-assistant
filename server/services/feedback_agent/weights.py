"""Feedback Learning Agent — Weight Adjustment Engine.

Adjusts the 5 matching weights over time based on:
- Recruiter actions (shortlist, interview, hire = positive signal)
- Candidate engagement (response, acceptance = positive signal)
- Bayesian updating of dimension importance

Initial weights (from mandate):
  Skills:      0.40
  Experience:  0.25
  Domain:      0.15
  Salary fit:  0.10
  Location fit: 0.10

The engine adjusts weights based on which dimensions were strong
for candidates that received positive recruiter actions.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from services.feedback_agent.tracker import MatchFeedback, RecruiterActionTracker
from services.matching_agent.matcher import WEIGHTS as INITIAL_WEIGHTS

logger = logging.getLogger(__name__)

# Weight names matching ScoreBreakdown fields
WEIGHT_NAMES = [
    "skills_score",
    "experience_score",
    "domain_score",
    "salary_fit_score",
    "location_fit_score",
]

# Min/max bounds for each weight
WEIGHT_MIN = 0.05
WEIGHT_MAX = 0.70


@dataclass
class WeightState:
    """Current state of the matching weights with learning metadata."""

    skills_score: float = INITIAL_WEIGHTS["skills_score"]
    experience_score: float = INITIAL_WEIGHTS["experience_score"]
    domain_score: float = INITIAL_WEIGHTS["domain_score"]
    salary_fit_score: float = INITIAL_WEIGHTS["salary_fit_score"]
    location_fit_score: float = INITIAL_WEIGHTS["location_fit_score"]

    total_observations: int = 0
    positive_outcomes: int = 0
    negative_outcomes: int = 0

    # Per-dimension adjustment counters
    dimension_adjustments: dict[str, float] = field(default_factory=lambda: {
        n: 0.0 for n in WEIGHT_NAMES
    })

    def to_dict(self) -> dict:
        return {
            "weights": {
                "skills_score": self.skills_score,
                "experience_score": self.experience_score,
                "domain_score": self.domain_score,
                "salary_fit_score": self.salary_fit_score,
                "location_fit_score": self.location_fit_score,
            },
            "metadata": {
                "total_observations": self.total_observations,
                "positive_outcomes": self.positive_outcomes,
                "negative_outcomes": self.negative_outcomes,
                "dimension_adjustments": self.dimension_adjustments,
            },
        }


class WeightAdjustmentEngine:
    """Bayesian-inspired weight adjustment based on feedback signals.

    Algorithm:
    - For each match with a clear outcome (hired/rejected):
      1. Compare the candidate's per-dimension scores against the job's average.
      2. If a dimension was significantly above average and the outcome was positive,
         that dimension's weight increases slightly.
      3. If a dimension was significantly above average and the outcome was negative,
         that dimension's weight decreases slightly.
      4. Re-normalize weights to sum to 1.0.
    """

    # Learning rate: how much each observation moves the weights
    LEARNING_RATE = 0.02

    # Min observations before any adjustment happens
    MIN_OBSERVATIONS = 10

    # How much above average a dimension must be to count as "significant"
    SIGNIFICANCE_THRESHOLD = 0.15

    def __init__(self):
        self.state = WeightState()
        self._average_scores: dict[str, float] = {n: 0.5 for n in WEIGHT_NAMES}

    def _get_weight_list(self) -> list[float]:
        return [
            self.state.skills_score,
            self.state.experience_score,
            self.state.domain_score,
            self.state.salary_fit_score,
            self.state.location_fit_score,
        ]

    def _set_weight_list(self, weights: list[float]) -> None:
        (self.state.skills_score,
         self.state.experience_score,
         self.state.domain_score,
         self.state.salary_fit_score,
         self.state.location_fit_score) = weights

    async def process_feedback(self, feedback: MatchFeedback, match_scores: dict | None = None) -> WeightState:
        """Process a single match feedback event and optionally adjust weights.

        Args:
            feedback: Aggregated recruiter + candidate feedback for a match.
            match_scores: Optional full ScoreBreakdown dict for this match.

        Returns:
            Updated WeightState (may be identical if no adjustment triggered).
        """
        self.state.total_observations += 1

        # Determine outcome
        outcome = self._determine_outcome(feedback)
        if outcome is None:
            return self.state  # no clear signal yet

        if outcome == "positive":
            self.state.positive_outcomes += 1
        else:
            self.state.negative_outcomes += 1

        # Skip adjustment if we don't have enough data yet
        if self.state.total_observations < self.MIN_OBSERVATIONS:
            return self.state

        # Skip if no score breakdown provided
        if not match_scores:
            return self.state

        # Adjust weights
        self._adjust_weights(match_scores, outcome == "positive")
        return self.state

    def _determine_outcome(self, feedback: MatchFeedback) -> str | None:
        """Determine match outcome from feedback signals."""
        recruiter_signal = feedback.recruiter_signal

        # Strong positive signal
        if recruiter_signal >= 0.5:
            return "positive"

        # Strong negative signal
        if recruiter_signal <= -0.5:
            return "negative"

        # Check for explicit hire action
        for action in feedback.recruiter_actions:
            if action.action == "hire":
                return "positive"

        # Check for explicit reject
        for action in feedback.recruiter_actions:
            if action.action == "reject":
                return "negative"

        return None  # inconclusive

    def _adjust_weights(self, match_scores: dict, positive_outcome: bool) -> None:
        """Apply Bayesian-inspired weight adjustment."""
        weights = self._get_weight_list()

        for i, dim in enumerate(WEIGHT_NAMES):
            dim_score = match_scores.get(dim, 0.5)
            avg_score = self._average_scores.get(dim, 0.5)
            deviation = dim_score - avg_score

            # Only adjust if this dimension was a significant factor
            if abs(deviation) < self.SIGNIFICANCE_THRESHOLD:
                continue

            # Direction: if positive outcome and dimension was strong → increase weight
            # If negative outcome and dimension was strong → decrease weight
            direction = 1.0 if positive_outcome else -1.0
            adjustment = self.LEARNING_RATE * deviation * direction

            weights[i] += adjustment
            self.state.dimension_adjustments[dim] += adjustment

        # Clamp to bounds
        weights = [max(WEIGHT_MIN, min(WEIGHT_MAX, w)) for w in weights]

        # Re-normalize to sum to 1.0
        total = sum(weights)
        if total > 0:
            weights = [w / total for w in weights]

        self._set_weight_list(weights)
        logger.info(
            f"Weights adjusted: positive={positive_outcome}, "
            f"new_weights={self._get_weight_list()}"
        )

    def update_average_scores(self, recent_scores: list[dict]) -> None:
        """Update the running average of per-dimension scores.

        Called periodically with a batch of recent match scores.
        """
        if not recent_scores:
            return

        for dim in WEIGHT_NAMES:
            values = [s.get(dim, 0.5) for s in recent_scores if dim in s]
            if values:
                self._average_scores[dim] = sum(values) / len(values)

    def get_current_weights(self) -> dict:
        """Get the current weight configuration for the matching agent."""
        return self.state.to_dict()

    def reset_to_defaults(self) -> None:
        """Reset weights to initial defaults."""
        self.state = WeightState()
        logger.info("Weights reset to defaults")
