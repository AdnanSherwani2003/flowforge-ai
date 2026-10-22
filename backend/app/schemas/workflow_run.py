from datetime import datetime
from typing import Optional, Dict, Any, List
from app.schemas.tracing import TraceId
from pydantic import BaseModel, Field, field_validator, ConfigDict


class WorkflowRunCreate(BaseModel):
    workflow_name: str = Field(
        default="support_ticket_intake",
        min_length=1,
        max_length=100,
        description="Identifier of the orchestrating workflow",
    )
    execution_id: TraceId = Field(
        ...,
        min_length=1,
        max_length=100,
        description="n8n execution identifier",
    )
    correlation_id: TraceId = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Unique end-to-end request correlation ID",
    )
    source_event_id: Optional[str] = Field(
        default=None,
        max_length=128,
        description="Source event identifier if available",
    )
    ticket_id: Optional[str] = Field(
        default=None,
        max_length=36,
        description="Persisted ticket UUID if created/replayed",
    )
    outcome: str = Field(
        ...,
        min_length=1,
        max_length=50,
        description="Resulting outcome classification (e.g. created, duplicate_replayed, conflict)",
    )
    status_code: int = Field(
        ...,
        ge=100,
        le=599,
        description="HTTP status code returned by the workflow",
    )
    safe_detail: Dict[str, Any] = Field(
        default_factory=dict,
        description="Sanitized non-sensitive operational tracing details",
    )

    @field_validator("workflow_name", "outcome", mode="before")
    @classmethod
    def strip_and_validate_strings(cls, v: str) -> str:
        if not isinstance(v, str):
            raise ValueError("Value must be a string")
        stripped = v.strip()
        if not stripped:
            raise ValueError("Field cannot be empty or whitespace-only")
        return stripped

    @field_validator("safe_detail")
    @classmethod
    def validate_safe_detail(cls, value: Dict[str, Any]) -> Dict[str, Any]:
        allowed = {"status", "duplicate", "error_code", "correlation_rejected", "source_event_id_rejected"}
        if set(value) - allowed:
            raise ValueError("Unsupported telemetry metadata field")
        if "status" in value and (not isinstance(value["status"], str) or value["status"] not in {"accepted", "rejected", "failed"}):
            raise ValueError("Unsupported telemetry status")
        if "error_code" in value and (not isinstance(value["error_code"], str) or value["error_code"] not in {
            "created", "duplicate_replayed", "conflict", "validation_error", "service_unavailable"
        }):
            raise ValueError("Unsupported telemetry error code")
        for key in ("duplicate", "correlation_rejected", "source_event_id_rejected"):
            if key in value and type(value[key]) is not bool:
                raise ValueError("Telemetry flags must be booleans")
        return value

    @field_validator("source_event_id", mode="before")
    @classmethod
    def strip_source_event_id(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and isinstance(v, str):
            stripped = v.strip()
            return stripped if stripped else None
        return v


class WorkflowRunResponse(BaseModel):
    id: str
    workflow_name: str
    execution_id: str
    correlation_id: str
    source_event_id: Optional[str] = None
    ticket_id: Optional[str] = None
    outcome: str
    status_code: int
    safe_detail: Dict[str, Any]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class WorkflowRunListResponse(BaseModel):
    items: List[WorkflowRunResponse]
    total: int
    limit: int
    offset: int
