"""Core data models for SchemaSurgeon."""

from typing import Any, Dict, List, Optional
import uuid
import time
from pydantic import BaseModel, Field


class ToolContract(BaseModel):
    """Registered contract for an API tool."""

    tool_name: str
    version: int = 1
    method: str = "POST"
    path: str
    request_schema: Dict[str, Any]
    response_schema: Dict[str, Any]
    contract_hash: str = ""
    openapi_hash: Optional[str] = None
    server_url: str = "http://127.0.0.1:8001"
    headers_schema: Optional[Dict[str, Any]] = None
    required_headers: Dict[str, str] = Field(default_factory=dict)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class RecoveryContext(BaseModel):
    """Context for a request recovery run."""

    tool_name: str
    active_version: int
    original_arguments: Dict[str, Any]
    task_id: str = Field(default_factory=lambda: f"task-{uuid.uuid4().hex[:8]}")
    recovery_id: str = Field(default_factory=lambda: f"recovery-{uuid.uuid4().hex[:8]}")
    deadline_seconds: float = 4.0
    started_at: float = Field(default_factory=time.time)
    intent: Optional[Dict[str, Any]] = None

    @property
    def remaining_deadline(self) -> float:
        elapsed = time.time() - self.started_at
        return max(0.0, self.deadline_seconds - elapsed)


class FieldMapping(BaseModel):
    """Proposed mapping between old and new schema fields."""

    source_path: str
    target_path: str
    transformation: str = "identity"  # move, rename, coerce_int, identity
    evidence: List[str] = Field(default_factory=list)
    confidence: float = 0.0


class RepairCandidate(BaseModel):
    """Candidate repair evaluated by the diagnosis and safety engine."""

    target_version: int
    request_adapter: List[Dict[str, Any]] = Field(default_factory=list)
    candidate_request_schema: Dict[str, Any] = Field(default_factory=dict)
    candidate_response_schema: Dict[str, Any] = Field(default_factory=dict)
    candidate_headers: Dict[str, str] = Field(default_factory=dict)
    evidence: List[str] = Field(default_factory=list)
    confidence_score: float = 0.0
    requires_approval: bool = False
    decision: str = "REFUSE"  # AUTO_REPAIR, REQUIRES_APPROVAL, REFUSE
    refusal_reason: Optional[str] = None
    fingerprint: Optional[str] = None


class RecoveryOutcome(BaseModel):
    """Outcome of a tool execution and potential recovery attempt."""

    status: str  # verified_success, refused, quarantined, timeout, error, suppressed
    tool_name: str
    old_version: int
    new_version: Optional[int] = None
    retry_count: int = 0
    task_verified: bool = False
    promoted: bool = False
    refusal_reason: Optional[str] = None
    transformed_arguments: Optional[Dict[str, Any]] = None
    response_data: Optional[Any] = None
    duration_ms: float = 0.0
    error_class: Optional[str] = None
    evidence_summary: List[str] = Field(default_factory=list)


class TaskIntent(BaseModel):
    """Intent Lock constraints and expected postconditions."""

    task_id: str
    intent: str
    constraints: Dict[str, Any] = Field(default_factory=dict)
    postconditions: List[str] = Field(default_factory=list)


class AuditEvent(BaseModel):
    """Structured audit event logged to JSONL."""

    timestamp: float = Field(default_factory=time.time)
    event: str
    tool: str
    task_id: Optional[str] = None
    recovery_id: Optional[str] = None
    old_version: Optional[int] = None
    candidate_version: Optional[int] = None
    decision: Optional[str] = None
    retry_count: int = 0
    task_verified: Optional[bool] = None
    promoted: Optional[bool] = None
    error_class: Optional[str] = None
    refusal_reason: Optional[str] = None
    evidence: List[str] = Field(default_factory=list)
    duration_ms: float = 0.0
    metadata: Dict[str, Any] = Field(default_factory=dict)
