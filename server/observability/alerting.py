"""Alert rules and alert manager configuration for production monitoring.

Alert severity levels:
- critical: GDPR violation, system down, data loss
- warning: Performance degradation, high error rate
- info: Low confidence outputs, empty candidate pools
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


# ─── Prometheus Alert Rules ─────────────────────────────────────────────

# These are meant to be written to a file and loaded by Prometheus.
# They follow the standard Prometheus recording/alerting rule format.

ALERT_RULES_YAML = """
groups:
  - name: hermes-hiring
    interval: 30s

    rules:
      # ─── CRITICAL: GDPR violation ────────────────────────────────────
      - alert: GDPRViolationDetected
        expr: hermes_gdpr_violation_total > 0
        for: 0s
        labels:
          severity: critical
          team: engineering
        annotations:
          summary: "GDPR violation detected — immediate investigation required"
          description: >
            {{ $value }} GDPR violation(s) detected.
            Violation type: {{ $labels.violation_type }}.
            Action: Investigate immediately, check audit trail, notify DPO.

      # ─── CRITICAL: System down ───────────────────────────────────────
      - alert: AgentDown
        expr: up{job=~"profile-agent|job-agent|matching-agent|gdpr-agent"} == 0
        for: 30s
        labels:
          severity: critical
          team: engineering
        annotations:
          summary: "Agent {{ $labels.job }} is down"
          description: "Agent has been unreachable for 30 seconds."

      # ─── WARNING: Matching flow latency ───────────────────────────────
      - alert: MatchingFlowLatencyHigh
        expr: histogram_quantile(0.95, rate(hermes_matching_flow_duration_seconds_bucket[5m])) > 10
        for: 2m
        labels:
          severity: warning
          team: engineering
        annotations:
          summary: "Matching flow p95 latency above 10s SLA"
          description: "Matching flow p95 latency is {{ $value }}s (SLA: <10s)"

      # ─── WARNING: Agent error rate ────────────────────────────────────
      - alert: AgentErrorRateHigh
        expr: rate(hermes_agent_latency_seconds_count{agent_name=~".+"}[5m]) > 0
        for: 5m
        labels:
          severity: warning
          team: engineering
        annotations:
          summary: "Agent {{ $labels.agent_name }} has errors"
          description: "Agent error rate is elevated for {{ $labels.agent_name }}"

      # ─── WARNING: CV ingestion SLA breach ────────────────────────────
      - alert: CVIngestionTooSlow
        expr: histogram_quantile(0.95, rate(hermes_cv_ingestion_duration_seconds_bucket[5m])) > 5
        for: 5m
        labels:
          severity: warning
          team: engineering
        annotations:
          summary: "CV ingestion p95 latency above 5s SLA"
          description: "CV ingestion p95 is {{ $value }}s (SLA: <5s)"

      # ─── WARNING: Workflow failure rate ───────────────────────────────
      - alert: WorkflowFailureRateHigh
        expr: |
          rate(hermes_workflow_status_total{status="failed"}[10m])
          /
          rate(hermes_workflow_status_total[10m])
          > 0.05
        for: 5m
        labels:
          severity: warning
          team: engineering
        annotations:
          summary: "Workflow failure rate above 5%"
          description: "{{ $value | humanizePercentage }} of workflows are failing"

      # ─── INFO: Low confidence matches ────────────────────────────────
      - alert: LowConfidenceMatches
        expr: hermes_match_success_rate < 0.5
        for: 10m
        labels:
          severity: info
          team: product
        annotations:
          summary: "Match confidence below 50%"
          description: "Match success rate is {{ $value | humanizePercentage }}"

      # ─── INFO: Empty candidate pool ──────────────────────────────────
      - alert: EmptyCandidatePool
        expr: hermes_candidate_pool_size == 0
        for: 1h
        labels:
          severity: info
          team: product
        annotations:
          summary: "Candidate pool is empty"
          description: "No consented candidates in the system for over 1 hour"

      # ─── WARNING: LLM fallback rate high ─────────────────────────────
      - alert: LLMFallbackRateHigh
        expr: rate(hermes_llm_fallback_total[10m]) > 10
        for: 5m
        labels:
          severity: warning
          team: engineering
        annotations:
          summary: "High LLM fallback rate"
          description: >
            {{ $value }} LLM fallbacks per second.
            Agent: {{ $labels.agent_name }}.
            Check LLM provider status and rate limits.
"""


# ─── In-process alert evaluation ────────────────────────────────────────

class AlertEvaluator:
    """Evaluates alert conditions in-process (for systems without Prometheus).

    This is a simplified version that logs alerts. In production,
    these rules should be loaded into Prometheus for proper alerting.
    """

    def __init__(self):
        self._alert_count: dict[str, int] = {}

    def evaluate_gdpr_violation(self, violation_type: str) -> None:
        """CRITICAL: Any GDPR violation triggers immediate alert."""
        logger.critical(
            f"GDPR VIOLATION — {violation_type}. "
            "Immediate investigation required."
        )
        self._alert_count["gdpr_violation"] = self._alert_count.get("gdpr_violation", 0) + 1

    def evaluate_sla_breach(self, metric: str, value: float, threshold: float, sla_name: str) -> None:
        """Evaluate if an SLA has been breached."""
        if value > threshold:
            logger.warning(
                f"SLA BREACH — {sla_name}: {value:.2f}s (threshold: {threshold}s). "
                f"Metric: {metric}"
            )
            self._alert_count["sla_breach"] = self._alert_count.get("sla_breach", 0) + 1

    def evaluate_workflow_failure(self, workflow_type: str, error: str) -> None:
        """Evaluate a workflow failure for alerting."""
        logger.error(
            f"WORKFLOW FAILURE — {workflow_type}: {error}"
        )
        self._alert_count["workflow_failure"] = self._alert_count.get("workflow_failure", 0) + 1

    def get_alert_counts(self) -> dict[str, int]:
        """Get current alert counts for health check."""
        return dict(self._alert_count)

    def reset_alert_counts(self) -> None:
        """Reset alert counters (e.g., after acknowledgement)."""
        self._alert_count = {}
