"""Prometheus metrics for the hiring platform.

Required metrics (from spec):
- match_success_rate: ratio of successful matching workflows
- agent_latency_seconds: per-agent p50/p95/p99 latency
- cv_ingestion_duration_seconds: CV processing time
- candidate_pool_size: gauge of consented candidates
- gdpr_violation_total: counter, CRITICAL if > 0
- workflow_status: count of succeeded/failed/partial workflows
- recruiter_engagement_rate: recruiter actions per session
"""

from __future__ import annotations

import time
from contextlib import contextmanager
from typing import Generator

from prometheus_client import Counter, Gauge, Histogram, REGISTRY


# ─── Metrics Definitions ────────────────────────────────────────────────

# Workflow outcomes
WORKFLOW_STATUS = Counter(
    "hermes_workflow_status_total",
    "Workflow execution outcomes by type and status",
    ["workflow_type", "status"],  # status: succeeded, failed, partial, timed_out
)

# Match success rate (successful matches / total matching attempts)
MATCH_SUCCESS_RATE = Gauge(
    "hermes_match_success_rate",
    "Ratio of successful matching workflows in the current window",
)

# Per-agent latency (seconds)
AGENT_LATENCY = Histogram(
    "hermes_agent_latency_seconds",
    "Agent call latency in seconds",
    ["agent_name", "endpoint"],
    buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.0, 4.0, 8.0, 15.0),
)

# CV ingestion duration
CV_INGESTION_DURATION = Histogram(
    "hermes_cv_ingestion_duration_seconds",
    "CV ingestion processing time in seconds",
    buckets=(0.5, 1.0, 2.0, 3.0, 4.0, 5.0, 10.0),
)

# Candidate pool size
CANDIDATE_POOL_SIZE = Gauge(
    "hermes_candidate_pool_size",
    "Number of consented candidates in the system",
)

# GDPR violations (CRITICAL — alert if > 0)
GDPR_VIOLATION_TOTAL = Counter(
    "hermes_gdpr_violation_total",
    "Count of GDPR violations (unauthorized data access attempts)",
    ["violation_type"],  # consent_denied, data_leak, unauthorized_access
)

# Matching flow duration (critical path)
MATCHING_FLOW_DURATION = Histogram(
    "hermes_matching_flow_duration_seconds",
    "End-to-end matching flow duration",
    buckets=(1.0, 2.0, 3.0, 5.0, 8.0, 10.0, 15.0, 20.0),
)

# Recruiter engagement
RECRUITER_ACTIONS = Counter(
    "hermes_recruiter_actions_total",
    "Recruiter actions by type",
    ["action_type"],  # view, shortlist, interview, reject, hire
)

# LLM fallback rate (low confidence outputs)
LLM_FALLBACK_TOTAL = Counter(
    "hermes_llm_fallback_total",
    "Count of LLM extraction failures that triggered rule-based fallback",
    ["agent_name"],  # profile_agent, job_agent
)

# Query response latency
QUERY_LATENCY = Histogram(
    "hermes_query_latency_seconds",
    "Candidate query response latency",
    buckets=(0.05, 0.1, 0.25, 0.5, 1.0, 2.0, 5.0),
)

# Cache hit rate
CACHE_HIT_TOTAL = Counter(
    "hermes_cache_total",
    "Cache hit/miss count",
    ["result"],  # hit, miss
)


# ─── Context managers for timing ────────────────────────────────────────

@contextmanager
def track_agent_latency(agent_name: str, endpoint: str) -> Generator[None, None, None]:
    """Context manager that records agent call latency.

    Usage:
        with track_agent_latency("matching_agent", "/v1/batch-score"):
            result = await call_agent(...)
    """
    start = time.monotonic()
    try:
        yield
    finally:
        duration = time.monotonic() - start
        AGENT_LATENCY.labels(agent_name=agent_name, endpoint=endpoint).observe(duration)


@contextmanager
def track_matching_flow() -> Generator[None, None, None]:
    """Record matching flow duration."""
    start = time.monotonic()
    try:
        yield
    finally:
        duration = time.monotonic() - start
        MATCHING_FLOW_DURATION.observe(duration)


@contextmanager
def track_cv_ingestion() -> Generator[None, None, None]:
    """Record CV ingestion duration."""
    start = time.monotonic()
    try:
        yield
    finally:
        duration = time.monotonic() - start
        CV_INGESTION_DURATION.observe(duration)


# ─── Recording helpers ──────────────────────────────────────────────────

def record_workflow_outcome(workflow_type: str, status: str) -> None:
    """Record a workflow outcome in the counter."""
    WORKFLOW_STATUS.labels(workflow_type=workflow_type, status=status).inc()


def record_gdpr_violation(violation_type: str) -> None:
    """Record a GDPR violation. Triggers critical alert if > 0."""
    GDPR_VIOLATION_TOTAL.labels(violation_type=violation_type).inc()


def record_recruiter_action(action_type: str) -> None:
    """Record a recruiter action."""
    RECRUITER_ACTIONS.labels(action_type=action_type).inc()


def record_llm_fallback(agent_name: str) -> None:
    """Record an LLM fallback event."""
    LLM_FALLBACK_TOTAL.labels(agent_name=agent_name).inc()


def update_candidate_pool_size(size: int) -> None:
    """Update the consented candidate pool gauge."""
    CANDIDATE_POOL_SIZE.set(size)


def record_cache_result(result: str) -> None:
    """Record a cache hit or miss."""
    CACHE_HIT_TOTAL.labels(result=result).inc()


# ─── Metrics endpoint handler ───────────────────────────────────────────

def metrics_endpoint():
    """FastAPI-compatible metrics endpoint.

    Usage in FastAPI:
        from prometheus_client import generate_latest
        @app.get("/metrics")
        async def metrics():
            return Response(content=generate_latest(), media_type="text/plain")
    """
    from prometheus_client import generate_latest
    from fastapi.responses import Response
    return Response(content=generate_latest(), media_type="text/plain")
