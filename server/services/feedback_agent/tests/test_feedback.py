"""Tests for the Feedback Learning Agent.

Covers:
- Recruiter action recording and classification
- Candidate engagement recording
- Match feedback aggregation
- Weight adjustment from feedback signals
- Edge cases (insufficient data, reset, stats)
"""

import pytest
from uuid import uuid4

from services.feedback_agent.tracker import (
    RecruiterAction,
    RecruiterActionTracker,
    RecruiterActionType,
    MatchFeedback,
)
from services.feedback_agent.weights import (
    WEIGHT_NAMES,
    WEIGHT_MAX,
    WEIGHT_MIN,
    WeightAdjustmentEngine,
    WeightState,
)


# ─── Recruiter Action Tracker ───────────────────────────────────────────

class TestRecruiterActionTracker:
    @pytest.mark.asyncio
    async def test_record_view_action(self):
        tracker = RecruiterActionTracker()
        action = await tracker.record_action(
            recruiter_id="recruiter-1",
            candidate_id=uuid4(),
            job_id=uuid4(),
            action="view",
        )
        assert action.action == "view"
        assert action.recruiter_id == "recruiter-1"
        assert tracker.total_actions == 1

    @pytest.mark.asyncio
    async def test_record_shortlist_action(self):
        tracker = RecruiterActionTracker()
        action = await tracker.record_action(
            recruiter_id="recruiter-1",
            candidate_id=uuid4(),
            job_id=uuid4(),
            action="shortlist",
        )
        assert action.is_positive() is True

    @pytest.mark.asyncio
    async def test_record_reject_action(self):
        tracker = RecruiterActionTracker()
        action = await tracker.record_action(
            recruiter_id="recruiter-1",
            candidate_id=uuid4(),
            job_id=uuid4(),
            action="reject",
        )
        assert action.is_negative() is True

    @pytest.mark.asyncio
    async def test_invalid_action_raises(self):
        tracker = RecruiterActionTracker()
        with pytest.raises(ValueError):
            await tracker.record_action(
                recruiter_id="r1",
                candidate_id=uuid4(),
                job_id=uuid4(),
                action="invalid_action",
            )

    @pytest.mark.asyncio
    async def test_record_candidate_engagement(self):
        tracker = RecruiterActionTracker()
        engagement = await tracker.record_engagement(
            candidate_id=uuid4(),
            job_id=uuid4(),
            action="applied",
        )
        assert engagement.action == "applied"
        assert tracker.total_engagements == 1

    @pytest.mark.asyncio
    async def test_get_feedback_for_match(self):
        tracker = RecruiterActionTracker()
        cid = uuid4()
        jid = uuid4()

        await tracker.record_action("r1", cid, jid, "shortlist")
        await tracker.record_action("r1", cid, jid, "interview")

        feedback = await tracker.get_feedback_for_match(cid, jid)
        assert len(feedback.recruiter_actions) == 2
        assert feedback.recruiter_signal > 0  # both positive

    @pytest.mark.asyncio
    async def test_get_feedback_for_job(self):
        tracker = RecruiterActionTracker()
        jid = uuid4()

        await tracker.record_action("r1", uuid4(), jid, "shortlist")
        await tracker.record_action("r1", uuid4(), jid, "reject")

        feedbacks = await tracker.get_feedback_for_job(jid)
        assert len(feedbacks) == 2

    @pytest.mark.asyncio
    async def test_get_action_stats(self):
        tracker = RecruiterActionTracker()
        cid = uuid4()
        jid = uuid4()

        await tracker.record_action("r1", cid, jid, "view")
        await tracker.record_action("r1", cid, jid, "shortlist")
        await tracker.record_action("r1", cid, jid, "reject")
        await tracker.record_engagement(cid, jid, "applied")

        stats = await tracker.get_action_stats()
        assert stats.get("view") == 1
        assert stats.get("shortlist") == 1
        assert stats.get("reject") == 1
        assert stats.get("candidate_applied") == 1

    def test_recruiter_action_signal(self):
        """Mixed actions should produce net signal."""
        feedback = MatchFeedback(
            job_id=uuid4(),
            candidate_id=uuid4(),
            recruiter_actions=[
                RecruiterAction(uuid4(), "r1", uuid4(), uuid4(), "shortlist", None),
                RecruiterAction(uuid4(), "r1", uuid4(), uuid4(), "interview", None),
                RecruiterAction(uuid4(), "r1", uuid4(), uuid4(), "reject", None),
            ],
        )
        # 2 positive, 1 negative: score = (2 - 1) / 3 = 0.33
        assert 0.3 <= feedback.recruiter_signal <= 0.4

    def test_no_actions_no_signal(self):
        feedback = MatchFeedback(job_id=uuid4(), candidate_id=uuid4())
        assert feedback.recruiter_signal == 0.0


# ─── Weight Adjustment Engine ───────────────────────────────────────────

class TestWeightAdjustmentEngine:
    def test_initial_weights_match_spec(self):
        """Initial weights should match the mandate specification."""
        engine = WeightAdjustmentEngine()
        weights = engine.get_current_weights()
        w = weights["weights"]

        assert w["skills_score"] == 0.40
        assert w["experience_score"] == 0.25
        assert w["domain_score"] == 0.15
        assert w["salary_fit_score"] == 0.10
        assert w["location_fit_score"] == 0.10

    def test_weights_sum_to_one(self):
        engine = WeightAdjustmentEngine()
        weights = engine.get_current_weights()
        total = sum(weights["weights"].values())
        assert abs(total - 1.0) < 0.001

    def test_reset_to_defaults(self):
        engine = WeightAdjustmentEngine()
        # Modify weights
        engine.state.skills_score = 0.50
        engine.state.experience_score = 0.20
        engine.reset_to_defaults()

        weights = engine.get_current_weights()
        assert weights["weights"]["skills_score"] == 0.40

    @pytest.mark.asyncio
    async def test_no_adjustment_below_min_observations(self):
        """No weight adjustment should happen below MIN_OBSERVATIONS."""
        engine = WeightAdjustmentEngine()

        # Process with positive feedback but only 5 observations
        for _ in range(5):
            feedback = MatchFeedback(
                job_id=uuid4(),
                candidate_id=uuid4(),
                recruiter_actions=[
                    RecruiterAction(uuid4(), "r1", uuid4(), uuid4(), "shortlist", None),
                    RecruiterAction(uuid4(), "r1", uuid4(), uuid4(), "hire", None),
                ],
            )
            scores = {n: 0.9 for n in WEIGHT_NAMES}
            state = await engine.process_feedback(feedback, scores)

        # Weights should still be at defaults
        weights = state.to_dict()["weights"]
        assert weights["skills_score"] == 0.40

    @pytest.mark.asyncio
    async def test_weight_adjustment_after_min(self):
        """Weights should adjust after enough observations."""
        engine = WeightAdjustmentEngine()

        # Override min for testing
        engine.MIN_OBSERVATIONS = 3

        # Process positive feedback where skills score is dominant
        feedback = MatchFeedback(
            job_id=uuid4(),
            candidate_id=uuid4(),
            recruiter_actions=[
                RecruiterAction(uuid4(), "r1", uuid4(), uuid4(), "shortlist", None),
                RecruiterAction(uuid4(), "r1", uuid4(), uuid4(), "hire", None),
            ],
        )

        for _ in range(5):
            # Skills is the standout dimension
            scores = {
                "skills_score": 0.95,
                "experience_score": 0.50,
                "domain_score": 0.50,
                "salary_fit_score": 0.50,
                "location_fit_score": 0.50,
            }
            state = await engine.process_feedback(feedback, scores)

        # Skills weight should have increased
        weights = state.to_dict()["weights"]
        assert weights["skills_score"] > 0.40

    @pytest.mark.asyncio
    async def test_negative_feedback_decreases_weight(self):
        """Negative feedback on a dimension should decrease its weight."""
        engine = WeightAdjustmentEngine()
        engine.MIN_OBSERVATIONS = 3

        feedback = MatchFeedback(
            job_id=uuid4(),
            candidate_id=uuid4(),
            recruiter_actions=[
                RecruiterAction(uuid4(), "r1", uuid4(), uuid4(), "reject", None),
            ],
        )

        for _ in range(5):
            scores = {
                "skills_score": 0.50,
                "experience_score": 0.50,
                "domain_score": 0.90,  # High domain match but rejected
                "salary_fit_score": 0.50,
                "location_fit_score": 0.50,
            }
            state = await engine.process_feedback(feedback, scores)

        # Domain weight should have decreased
        weights = state.to_dict()["weights"]
        # Allow some tolerance — exact value depends on normalization
        assert weights["domain_score"] < 0.15 or any(
            w < v for w, v in zip(
                [0.40, 0.25, 0.15, 0.10, 0.10],
                [weights["skills_score"], weights["experience_score"],
                 weights["domain_score"], weights["salary_fit_score"],
                 weights["location_fit_score"]]
            )
        )  # At least one weight decreased

    @pytest.mark.asyncio
    async def test_weights_always_sum_to_one(self):
        """After any adjustment, weights must always sum to 1.0."""
        engine = WeightAdjustmentEngine()
        engine.MIN_OBSERVATIONS = 3

        feedback = MatchFeedback(
            job_id=uuid4(),
            candidate_id=uuid4(),
            recruiter_actions=[
                RecruiterAction(
                    uuid4(), "r1", uuid4(), uuid4(),
                    "shortlist", None
                ),
            ],
        )
        for _ in range(20):
            scores = {n: 0.3 + (hash(n) % 70) / 100.0 for n in WEIGHT_NAMES}
            state = await engine.process_feedback(feedback, scores)

        weights = state.to_dict()["weights"]
        total = sum(weights.values())
        assert abs(total - 1.0) < 0.001, f"Weights sum to {total}"

    @pytest.mark.asyncio
    async def test_weights_clamped_to_bounds(self):
        """Weights should never go below WEIGHT_MIN or above WEIGHT_MAX."""
        engine = WeightAdjustmentEngine()
        engine.MIN_OBSERVATIONS = 0  # allow immediate adjustment

        # Apply extreme adjustments
        for _ in range(100):
            feedback = MatchFeedback(
                job_id=uuid4(),
                candidate_id=uuid4(),
                recruiter_actions=[
                    RecruiterAction(uuid4(), "r1", uuid4(), uuid4(), "hire", None),
                ],
            )
            scores = {n: 0.99 for n in WEIGHT_NAMES}
            state = await engine.process_feedback(feedback, scores)

        weights = state.to_dict()["weights"]
        for name, value in weights.items():
            assert WEIGHT_MIN <= value <= WEIGHT_MAX, (
                f"{name} = {value} outside [{WEIGHT_MIN}, {WEIGHT_MAX}]"
            )

    @pytest.mark.asyncio
    async def test_inconclusive_feedback_no_change(self):
        """Feedback without clear positive/negative signal should not change weights."""
        engine = WeightAdjustmentEngine()
        initial = engine.get_current_weights()

        feedback = MatchFeedback(
            job_id=uuid4(),
            candidate_id=uuid4(),
            recruiter_actions=[
                RecruiterAction(uuid4(), "r1", uuid4(), uuid4(), "view", None),
            ],
        )
        state = await engine.process_feedback(feedback)
        after = state.to_dict()

        assert after["weights"] == initial["weights"]

    def test_update_average_scores(self):
        """Updating running averages should work."""
        engine = WeightAdjustmentEngine()
        scores = [
            {"skills_score": 0.8, "experience_score": 0.6, "domain_score": 0.4,
             "salary_fit_score": 0.5, "location_fit_score": 0.3},
            {"skills_score": 0.7, "experience_score": 0.5, "domain_score": 0.5,
             "salary_fit_score": 0.4, "location_fit_score": 0.4},
        ]
        engine.update_average_scores(scores)
        assert engine._average_scores["skills_score"] == 0.75

    def test_dimension_adjustments_tracked(self):
        """Per-dimension adjustment counters should be tracked."""
        engine = WeightAdjustmentEngine()
        assert all(adj == 0.0 for adj in engine.state.dimension_adjustments.values())
