"""Structured JSON logging with correlation IDs.

Provides:
- JSON-formatted log entries (not plain text)
- Correlation ID injection for tracing across agents
- Log level configuration via environment variable
- Structured fields: timestamp, level, service, correlation_id, workflow_id
"""

from __future__ import annotations

import json
import logging
import os
import sys
from datetime import datetime
from typing import Any
from uuid import UUID


class JSONFormatter(logging.Formatter):
    """Custom formatter that outputs structured JSON log entries.

    Example output:
    {"timestamp": "2026-04-27T10:00:00.000Z", "level": "INFO",
     "service": "hermes-hiring", "message": "Matching flow completed",
     "correlation_id": "abc-123", "duration_ms": 4500}
    """

    def __init__(self, service_name: str | None = None):
        super().__init__()
        self.service_name = service_name or os.getenv("OTEL_SERVICE_NAME", "hermes-hiring")

    def format(self, record: logging.LogRecord) -> str:
        log_entry: dict[str, Any] = {
            "timestamp": datetime.utcfromtimestamp(record.created).isoformat() + "Z",
            "level": record.levelname,
            "service": self.service_name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        # Include exception info if present
        if record.exc_info and record.exc_info[0] if isinstance(record.exc_info, tuple) else False:
            log_entry["exception"] = {
                "type": record.exc_info[0].__name__,
                "message": str(record.exc_info[1]),
            }

        # Include extra fields from the log record
        for key in ("correlation_id", "workflow_id", "workflow_type",
                     "agent_name", "duration_ms", "job_id", "candidate_id",
                     "pool_size", "match_count", "gdpr_blocked", "confidence"):
            value = getattr(record, key, None)
            if value is not None:
                log_entry[key] = str(value) if isinstance(value, UUID) else value

        return json.dumps(log_entry, default=str)


def setup_logging(service_name: str | None = None, level: str | None = None) -> None:
    """Configure structured JSON logging.

    Call once at application startup.

    Args:
        service_name: Override the service name in log entries
        level: Log level (default: from LOG_LEVEL env var, or INFO)
    """
    log_level = (level or os.getenv("LOG_LEVEL", "INFO")).upper()

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JSONFormatter(service_name))

    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    root_logger.handlers.clear()
    root_logger.addHandler(handler)

    # Quiet noisy libraries
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy").setLevel(logging.WARNING)

    logging.info(f"Structured logging initialized: level={log_level}, format=json")


class LoggerAdapter(logging.LoggerAdapter):
    """Logger adapter that automatically injects correlation_id and workflow_id."""

    def __init__(self, logger: logging.Logger, correlation_id: str | None = None):
        super().__init__(logger, {})
        self._correlation_id = correlation_id
        self._workflow_id: str | None = None

    def set_workflow(self, workflow_id: str) -> None:
        self._workflow_id = workflow_id

    def process(self, msg: str, kwargs: dict) -> tuple[str, dict]:
        extra = kwargs.get("extra", {})
        if self._correlation_id:
            extra["correlation_id"] = self._correlation_id
        if self._workflow_id:
            extra["workflow_id"] = self._workflow_id
        kwargs["extra"] = extra
        return msg, kwargs

    def info(self, msg, *args, **kwargs):
        self.log(logging.INFO, msg, *args, **kwargs)

    def warning(self, msg, *args, **kwargs):
        self.log(logging.WARNING, msg, *args, **kwargs)

    def error(self, msg, *args, **kwargs):
        self.log(logging.ERROR, msg, *args, **kwargs)
