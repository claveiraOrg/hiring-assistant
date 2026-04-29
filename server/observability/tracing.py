"""OpenTelemetry distributed tracing setup.

Provides:
- Per-agent call tracing with spans and attributes
- Workflow-level tracing with parent-child span hierarchy
- Correlation ID propagation across agent boundaries
- OTLP export to Jaeger / Tempo / Grafana Cloud
"""

from __future__ import annotations

import os
import logging
from contextlib import asynccontextmanager
from datetime import datetime
from typing import AsyncIterator
from uuid import UUID, uuid4

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource, SERVICE_NAME, SERVICE_VERSION
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, SimpleSpanProcessor
from opentelemetry.trace import Span, SpanKind, Status, StatusCode

logger = logging.getLogger(__name__)


class TracingConfig:
    """Tracing configuration from environment variables."""

    # OTLP endpoint (e.g., http://otel-collector:4317)
    otlp_endpoint: str = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4317")
    service_name: str = os.getenv("OTEL_SERVICE_NAME", "hermes-hiring")
    service_version: str = "0.1.0"
    environment: str = os.getenv("HERMES_ENVIRONMENT", "development")
    sample_rate: float = float(os.getenv("OTEL_TRACE_SAMPLE_RATE", "1.0"))


def setup_tracing(config: TracingConfig | None = None) -> TracerProvider:
    """Initialize OpenTelemetry tracing with OTLP export.

    Call once at application startup. Returns the TracerProvider.
    """
    cfg = config or TracingConfig()

    resource = Resource.create({
        SERVICE_NAME: cfg.service_name,
        SERVICE_VERSION: cfg.service_version,
        "deployment.environment": cfg.environment,
    })

    provider = TracerProvider(resource=resource)

    # OTLP exporter (production)
    if cfg.otlp_endpoint:
        otlp_exporter = OTLPSpanExporter(endpoint=cfg.otlp_endpoint)
        provider.add_span_processor(BatchSpanProcessor(otlp_exporter))

    # Console exporter (development / debugging)
    if cfg.environment == "development":
        from opentelemetry.sdk.trace.export import ConsoleSpanExporter
        provider.add_span_processor(SimpleSpanProcessor(ConsoleSpanExporter()))

    trace.set_tracer_provider(provider)
    logger.info(f"Tracing initialized: service={cfg.service_name}, endpoint={cfg.otlp_endpoint}")
    return provider


def get_tracer(service_name: str | None = None) -> trace.Tracer:
    """Get a tracer for instrumenting agent calls.

    Args:
        service_name: Optional service name override (e.g., "matching-agent")
    """
    return trace.get_tracer(service_name or "hermes-hiring")


# ─── Workflow-level tracing ─────────────────────────────────────────────

class WorkflowTracer:
    """Higher-level tracer for orchestrator workflows.

    Creates a root span for each workflow, then child spans
    for each agent call within the workflow.
    """

    def __init__(self, tracer: trace.Tracer | None = None):
        self._tracer = tracer or get_tracer()

    @asynccontextmanager
    async def trace_workflow(
        self,
        workflow_type: str,
        workflow_id: UUID,
        job_id: UUID | None = None,
        candidate_id: UUID | None = None,
    ) -> AsyncIterator[Span]:
        """Create a root workflow span.

        Usage:
            async with workflow_tracer.trace_workflow("job_matching", wf_id, job_id=jid) as span:
                span.set_attribute("pool_size", 50)
                # ... agent calls will be child spans
        """
        with self._tracer.start_as_current_span(
            name=f"workflow.{workflow_type}",
            kind=SpanKind.SERVER,
            attributes={
                "workflow.id": str(workflow_id),
                "workflow.type": workflow_type,
                "workflow.started_at": datetime.utcnow().isoformat(),
            },
        ) as span:
            if job_id:
                span.set_attribute("job.id", str(job_id))
            if candidate_id:
                span.set_attribute("candidate.id", str(candidate_id))
            try:
                yield span
                span.set_attribute("workflow.success", True)
                span.set_status(Status(StatusCode.OK))
            except Exception as e:
                span.set_attribute("workflow.success", False)
                span.set_attribute("workflow.error", str(e))
                span.set_status(Status(StatusCode.ERROR, str(e)))
                raise

    def trace_agent_call(
        self,
        agent_name: str,
        endpoint: str,
        duration_ms: float,
        success: bool,
        parent_span: Span | None = None,
        attributes: dict | None = None,
    ):
        """Record an agent call as a span.

        Called after the agent call completes (not as a context manager,
        since we want to attribute timing after the fact).
        """
        span_attrs = {
            "agent.name": agent_name,
            "agent.endpoint": endpoint,
            "agent.duration_ms": duration_ms,
            "agent.success": success,
        }
        if attributes:
            span_attrs.update(attributes)

        # Create and end the span
        span = self._tracer.start_span(
            name=f"agent.{agent_name}",
            kind=SpanKind.CLIENT,
            attributes=span_attrs,
        )
        if success:
            span.set_status(Status(StatusCode.OK))
        else:
            span.set_status(Status(StatusCode.ERROR))
        span.end()


# ─── Correlation ID propagation ─────────────────────────────────────────

class CorrelationID:
    """Correlation ID for tracing requests across agent boundaries.

    Each incoming request gets a correlation_id that is propagated
    to all downstream agent calls in headers.
    """

    _HEADER_NAME = "X-Correlation-Id"

    @staticmethod
    def generate() -> str:
        return str(uuid4())

    @staticmethod
    def header_name() -> str:
        return CorrelationID._HEADER_NAME

    @staticmethod
    def inject_headers(headers: dict | None = None) -> dict:
        """Add correlation ID to outgoing request headers."""
        headers = headers or {}
        if CorrelationID._HEADER_NAME not in headers:
            headers[CorrelationID._HEADER_NAME] = CorrelationID.generate()
        return headers
