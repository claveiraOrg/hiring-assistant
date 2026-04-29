"""Feedback Learning Agent — FastAPI service.

Provides:
- POST /v1/actions/recruiter  — Record a recruiter action
- POST /v1/actions/candidate — Record a candidate engagement
- GET  /v1/feedback/match     — Get feedback for a specific match
- GET  /v1/feedback/job       — Get all feedback for a job
- POST /v1/feedback/process   — Process feedback and adjust weights
- GET  /v1/weights            — Get current weight configuration
- POST /v1/weights/reset      — Reset weights to defaults
- GET  /v1/stats              — Get aggregate action statistics
- GET  /health                — Health check
"""

from __future__ import annotations

import logging
from uuid import UUID

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from services.feedback_agent.tracker import RecruiterActionTracker
from services.feedback_agent.weights import WeightAdjustmentEngine

logger = logging.getLogger(__name__)

app = FastAPI(
    title="Feedback Learning Agent",
    version="0.1.0",
    description="Learns from recruiter and candidate interactions to adjust matching weights",
)

tracker = RecruiterActionTracker()
weight_engine = WeightAdjustmentEngine()


# ─── Request models ─────────────────────────────────────────────────────

class RecruiterActionRequest(BaseModel):
    recruiter_id: str
    candidate_id: UUID
    job_id: UUID
    action: str  # view, shortlist, interview, reject, hire


class CandidateEngagementRequest(BaseModel):
    candidate_id: UUID
    job_id: UUID
    action: str  # applied, responded, interviewed, accepted, declined


class MatchFeedbackRequest(BaseModel):
    candidate_id: UUID
    job_id: UUID
    match_scores: dict | None = None


# ─── Endpoints ──────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    return {
        "status": "ok",
        "service": "feedback-agent",
        "version": "0.1.0",
        "total_actions": tracker.total_actions,
        "total_engagements": tracker.total_engagements,
    }


@app.post("/v1/recruiter-action")
async def record_recruiter_action(request: RecruiterActionRequest):
    """Record a recruiter action on a candidate-job match."""
    try:
        action = await tracker.record_action(
            recruiter_id=request.recruiter_id,
            candidate_id=request.candidate_id,
            job_id=request.job_id,
            action=request.action,
        )
        return {
            "action_id": str(action.action_id),
            "status": "recorded",
            "action": action.action,
        }
    except ValueError as e:
        raise HTTPException(400, str(e))


@app.post("/v1/candidate-engagement")
async def record_candidate_engagement(request: CandidateEngagementRequest):
    """Record a candidate engagement action."""
    engagement = await tracker.record_engagement(
        candidate_id=request.candidate_id,
        job_id=request.job_id,
        action=request.action,
    )
    return {
        "engagement_id": str(engagement.engagement_id),
        "status": "recorded",
    }


@app.post("/v1/feedback/process")
async def process_feedback(request: MatchFeedbackRequest):
    """Process feedback for a match and optionally adjust weights."""
    feedback = await tracker.get_feedback_for_match(
        candidate_id=request.candidate_id,
        job_id=request.job_id,
    )
    state = await weight_engine.process_feedback(
        feedback=feedback,
        match_scores=request.match_scores,
    )
    return {
        "outcome": state.to_dict(),
        "feedback_summary": {
            "recruiter_actions": len(feedback.recruiter_actions),
            "candidate_actions": len(feedback.candidate_actions),
            "recruiter_signal": feedback.recruiter_signal,
        },
    }


@app.get("/v1/feedback/match")
async def get_match_feedback(candidate_id: UUID, job_id: UUID):
    """Get aggregated feedback for a specific match."""
    feedback = await tracker.get_feedback_for_match(
        candidate_id=candidate_id, job_id=job_id
    )
    return {
        "candidate_id": str(candidate_id),
        "job_id": str(job_id),
        "recruiter_actions": [
            {
                "action_id": str(a.action_id),
                "recruiter_id": a.recruiter_id,
                "action": a.action,
                "timestamp": a.timestamp.isoformat(),
            }
            for a in feedback.recruiter_actions
        ],
        "candidate_actions": [
            {
                "engagement_id": str(e.engagement_id),
                "action": e.action,
                "timestamp": e.timestamp.isoformat(),
            }
            for e in feedback.candidate_actions
        ],
        "recruiter_signal": feedback.recruiter_signal,
    }


@app.get("/v1/weights")
async def get_weights():
    """Get current matching weights with metadata."""
    return weight_engine.get_current_weights()


@app.post("/v1/weights/reset")
async def reset_weights():
    """Reset weights to initial defaults."""
    weight_engine.reset_to_defaults()
    return {"status": "reset", "weights": weight_engine.get_current_weights()}


@app.get("/v1/stats")
async def get_stats():
    """Get aggregate action and engagement statistics."""
    stats = await tracker.get_action_stats()
    return {
        "total_actions": tracker.total_actions,
        "total_engagements": tracker.total_engagements,
        "breakdown": stats,
        "current_weights": weight_engine.get_current_weights(),
    }
