"""Workflow state machine — core orchestrator state tracking.

Every workflow execution creates a state record that tracks:
- Current status through the lifecycle
- Per-agent results and errors
- Timing for SLA monitoring
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from uuid import UUID, uuid4


class WorkflowStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    PARTIALLY_SUCCEEDED = "partially_succeeded"
    TIMED_OUT = "timed_out"


class WorkflowType(str, Enum):
    CANDIDATE_INGESTION = "candidate_ingestion"
    JOB_MATCHING = "job_matching"
    BATCH_MATCHING = "batch_matching"
    DATA_DELETION = "data_deletion"
    CONSENT_UPDATE = "consent_update"


@dataclass
class AgentCall:
    """Record of a single agent invocation within a workflow."""

    agent_name: str
    started_at: datetime
    completed_at: datetime | None = None
    success: bool | None = None
    duration_ms: int | None = None
    error: str | None = None


@dataclass
class WorkflowState:
    """Complete state of a workflow execution.

    Immutable after creation — state transitions create new instances.
    """

    workflow_id: UUID
    workflow_type: WorkflowType
    status: WorkflowStatus
    created_at: datetime
    context: dict = field(default_factory=dict)
    results: dict = field(default_factory=dict)
    agent_calls: list[AgentCall] = field(default_factory=list)
    errors: list[dict] = field(default_factory=list)
    retry_count: int = 0
    completed_at: datetime | None = None

    def elapsed_ms(self) -> int:
        end = self.completed_at or datetime.utcnow()
        return int((end - self.created_at).total_seconds() * 1000)

    def to_dict(self) -> dict:
        return {
            "workflow_id": str(self.workflow_id),
            "workflow_type": self.workflow_type.value,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "elapsed_ms": self.elapsed_ms(),
            "context": self.context,
            "results": self.results,
            "agent_calls": [
                {
                    "agent": c.agent_name,
                    "duration_ms": c.duration_ms,
                    "success": c.success,
                    "error": c.error,
                }
                for c in self.agent_calls
            ],
            "errors": self.errors,
            "retry_count": self.retry_count,
        }


class WorkflowFactory:
    """Creates workflow states for different workflow types."""

    @staticmethod
    def new_matching(job_id: UUID, context: dict | None = None) -> WorkflowState:
        return WorkflowState(
            workflow_id=uuid4(),
            workflow_type=WorkflowType.JOB_MATCHING,
            status=WorkflowStatus.PENDING,
            created_at=datetime.utcnow(),
            context={"job_id": str(job_id), **(context or {})},
        )

    @staticmethod
    def new_ingestion(external_id: str | None = None) -> WorkflowState:
        return WorkflowState(
            workflow_id=uuid4(),
            workflow_type=WorkflowType.CANDIDATE_INGESTION,
            status=WorkflowStatus.PENDING,
            created_at=datetime.utcnow(),
            context={"external_id": external_id} if external_id else {},
        )

    @staticmethod
    def new_deletion(candidate_id: UUID, actor_id: str) -> WorkflowState:
        return WorkflowState(
            workflow_id=uuid4(),
            workflow_type=WorkflowType.DATA_DELETION,
            status=WorkflowStatus.PENDING,
            created_at=datetime.utcnow(),
            context={"candidate_id": str(candidate_id), "actor_id": actor_id},
        )
