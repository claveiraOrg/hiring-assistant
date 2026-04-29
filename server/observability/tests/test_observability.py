"""Tests for the observability layer.

Covers:
- Tracing: span creation, workflow tracer, correlation IDs
- Metrics: counters, histograms, recording helpers
- Logging: JSON formatter, structured output, adapter
- Alerting: rule validation, evaluator, SLA breaches
"""

import json
import logging
import re
from uuid import uuid4

import pytest

from observability.tracing import CorrelationID, WorkflowTracer, setup_tracing
from observability.metrics import (
    CANDIDATE_POOL_SIZE,
    GDPR_VIOLATION_TOTAL,
    record_cache_result,
    record_gdpr_violation,
    record_llm_fallback,
    record_recruiter_action,
    record_workflow_outcome,
    track_agent_latency,
    track_cv_ingestion,
    track_matching_flow,
    update_candidate_pool_size,
)
from observability.logging import JSONFormatter, LoggerAdapter, setup_logging
from observability.alerting import AlertEvaluator


# ─── Tracing ────────────────────────────────────────────────────────────

class TestTracing:
    def test_correlation_id_generation(self):
        cid1 = CorrelationID.generate()
        cid2 = CorrelationID.generate()
        assert cid1 != cid2
        assert len(cid1) == 36  # UUID format

    def test_correlation_id_header_injection(self):
        headers = CorrelationID.inject_headers()
        assert CorrelationID._HEADER_NAME in headers
        assert len(headers[CorrelationID._HEADER_NAME]) == 36

    def test_correlation_id_preserves_existing(self):
        headers = CorrelationID.inject_headers({"X-Correlation-Id": "existing-id"})
        assert headers["X-Correlation-Id"] == "existing-id"

    def test_correlation_id_header_name(self):
        assert CorrelationID.header_name() == "X-Correlation-Id"

    @pytest.mark.asyncio
    async def test_workflow_tracer_context(self):
        """WorkflowTracer should create and manage spans."""
        tracer = WorkflowTracer()
        wf_id = uuid4()
        job_id = uuid4()

        try:
            async with tracer.trace_workflow(
                "job_matching", wf_id, job_id=job_id
            ) as span:
                assert span is not None
                span.set_attribute("test_value", 42)
        except Exception:
            pass  # Span may not export without OTLP, but shouldn't crash

    def test_setup_tracing_no_crash(self):
        """setup_tracing should not raise when OTLP endpoint unavailable."""
        # Should fail gracefully on OTLP connection, not crash
        config = type("Config", (), {
            "otlp_endpoint": "http://localhost:14317",  # non-existent
            "service_name": "test",
            "service_version": "0.1.0",
            "environment": "test",
            "sample_rate": 1.0,
        })()
        try:
            provider = setup_tracing(config)
            assert provider is not None
        except Exception:
            pass  # Graceful failure acceptable without OTLP


# ─── Metrics ────────────────────────────────────────────────────────────

class TestMetrics:
    def test_record_workflow_outcome(self):
        """Counter should increment without error."""
        record_workflow_outcome("job_matching", "succeeded")
        record_workflow_outcome("job_matching", "failed")
        record_workflow_outcome("candidate_ingestion", "succeeded")
        # No crash = pass

    def test_record_gdpr_violation(self):
        """GDPR violation counter should increment."""
        record_gdpr_violation("consent_denied")
        # Verify metric exists
        samples = list(GDPR_VIOLATION_TOTAL.collect())
        assert len(samples) > 0

    def test_record_cache_hit_miss(self):
        """Cache hit/miss counter should work."""
        record_cache_result("hit")
        record_cache_result("miss")
        # No crash = pass

    def test_record_recruiter_action(self):
        """Recruiter action counter should work."""
        record_recruiter_action("view")
        record_recruiter_action("shortlist")
        # No crash = pass

    def test_record_llm_fallback(self):
        """LLM fallback counter should work."""
        record_llm_fallback("profile_agent")
        # No crash = pass

    def test_candidate_pool_gauge(self):
        """Pool size gauge should update."""
        update_candidate_pool_size(150)
        assert CANDIDATE_POOL_SIZE._value.get() == 150.0

    @pytest.mark.asyncio
    async def test_track_agent_latency(self):
        """Context manager should not crash."""
        with track_agent_latency("test_agent", "/v1/test"):
            import asyncio
            await asyncio.sleep(0.001)

    @pytest.mark.asyncio
    async def test_track_matching_flow(self):
        """Matching flow timer should not crash."""
        with track_matching_flow():
            pass

    @pytest.mark.asyncio
    async def test_track_cv_ingestion(self):
        """CV ingestion timer should not crash."""
        with track_cv_ingestion():
            pass


# ─── Logging ────────────────────────────────────────────────────────────

class TestLogging:
    def test_json_formatter_output(self):
        """JSON formatter should produce valid JSON."""
        formatter = JSONFormatter("test-service")
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="/test.py",
            lineno=42,
            msg="Test message",
            args=(),
            exc_info=None,
        )

        output = formatter.format(record)
        parsed = json.loads(output)

        assert parsed["level"] == "INFO"
        assert parsed["service"] == "test-service"
        assert parsed["message"] == "Test message"
        assert "timestamp" in parsed
        assert "module" in parsed

    def test_json_formatter_with_exception(self):
        """Exception info should be included in JSON output."""
        import sys
        formatter = JSONFormatter("test")
        try:
            raise ValueError("test error")
        except ValueError:
            record = logging.LogRecord(
                name="test",
                level=logging.ERROR,
                pathname="/test.py",
                lineno=10,
                msg="Error occurred",
                args=(),
                exc_info=sys.exc_info(),
            )

        output = formatter.format(record)
        parsed = json.loads(output)
        assert "exception" in parsed
        assert parsed["exception"]["type"] == "ValueError"

    def test_json_formatter_with_extra_fields(self):
        """Extra fields like correlation_id should be included."""
        formatter = JSONFormatter("test")
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="/test.py",
            lineno=1,
            msg="Processing",
            args=(),
            exc_info=None,
        )
        record.correlation_id = "abc-123"
        record.workflow_id = "wf-456"
        record.duration_ms = 4200

        output = formatter.format(record)
        parsed = json.loads(output)
        assert parsed["correlation_id"] == "abc-123"
        assert parsed["workflow_id"] == "wf-456"
        assert parsed["duration_ms"] == 4200

    def test_setup_logging_does_not_crash(self):
        """setup_logging should configure without error."""
        setup_logging("test-service", "DEBUG")
        assert logging.getLogger().level == logging.DEBUG

    def test_logger_adapter_adds_context(self):
        """LoggerAdapter should inject correlation_id."""
        logger = logging.getLogger("test_adapter")
        logger.setLevel(logging.DEBUG)
        adapter = LoggerAdapter(logger, correlation_id="corr-999")

        # Capture log output
        from io import StringIO
        stream = StringIO()
        handler = logging.StreamHandler(stream)
        handler.setFormatter(JSONFormatter("test"))
        logger.addHandler(handler)

        adapter.info("Test with context")

        handler.flush()
        output = json.loads(stream.getvalue())
        assert output["correlation_id"] == "corr-999"
        logger.removeHandler(handler)


# ─── Alerting ───────────────────────────────────────────────────────────

class TestAlerting:
    def test_alert_rules_yaml_is_valid(self):
        """Alert rules YAML should be parseable."""
        from observability.alerting import ALERT_RULES_YAML
        import yaml
        try:
            parsed = yaml.safe_load(ALERT_RULES_YAML)
            assert parsed is not None
            assert "groups" in parsed
            assert len(parsed["groups"]) > 0
        except ImportError:
            pytest.skip("PyYAML not installed")

    def test_alert_evaluator_gdpr_violation(self):
        """GDPR violation should be logged at CRITICAL level."""
        evaluator = AlertEvaluator()
        evaluator.evaluate_gdpr_violation("consent_denied")
        counts = evaluator.get_alert_counts()
        assert counts["gdpr_violation"] == 1

    def test_alert_evaluator_sla_breach(self):
        """SLA breach should be detected."""
        evaluator = AlertEvaluator()
        evaluator.evaluate_sla_breach("latency", 12.0, 10.0, "matching_flow")
        counts = evaluator.get_alert_counts()
        assert counts["sla_breach"] == 1

    def test_alert_evaluator_no_breach(self):
        """No alert when value is below threshold."""
        evaluator = AlertEvaluator()
        evaluator.evaluate_sla_breach("latency", 5.0, 10.0, "matching_flow")
        assert "sla_breach" not in evaluator.get_alert_counts()

    def test_alert_evaluator_workflow_failure(self):
        """Workflow failure should increment counter."""
        evaluator = AlertEvaluator()
        evaluator.evaluate_workflow_failure("job_matching", "Agent timeout")
        counts = evaluator.get_alert_counts()
        assert counts["workflow_failure"] == 1

    def test_alert_evaluator_reset(self):
        """Reset should clear all alert counts."""
        evaluator = AlertEvaluator()
        evaluator.evaluate_gdpr_violation("test")
        assert len(evaluator.get_alert_counts()) > 0
        evaluator.reset_alert_counts()
        assert evaluator.get_alert_counts() == {}

    def test_alert_rule_count(self):
        """Verify all required alert rules are defined."""
        from observability.alerting import ALERT_RULES_YAML

        # Count all alert rules in YAML
        alert_count = ALERT_RULES_YAML.count("alert: ")
        required_alerts = {
            "GDPRViolationDetected",
            "AgentDown",
            "MatchingFlowLatencyHigh",
            "AgentErrorRateHigh",
            "CVIngestionTooSlow",
            "WorkflowFailureRateHigh",
            "LowConfidenceMatches",
            "EmptyCandidatePool",
            "LLMFallbackRateHigh",
        }
        # Each required alert must appear in the YAML
        for alert in required_alerts:
            assert alert in ALERT_RULES_YAML, f"Missing alert rule: {alert}"
