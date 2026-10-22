"""Strict model output and server-owned advisory response metadata."""
import math
from datetime import datetime
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

Category = Literal["billing", "account_access", "technical_issue", "shipping", "general", "unknown"]
Priority = Literal["low", "medium", "high", "unknown"]
EnrichmentStatus = Literal["processing", "succeeded", "needs_review", "unavailable"]
PROMPT_VERSION = "support-triage-v1"
SCHEMA_VERSION = "1"
MAX_ATTEMPTS = 3


class ModelSuggestion(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    category: Category
    priority: Priority
    reason: str = Field(min_length=1, max_length=200)
    confidence: float | None = Field(default=None, ge=0, le=1)

    @field_validator("reason")
    @classmethod
    def safe_reason(cls, value: str) -> str:
        if not value.strip() or not value.isprintable():
            raise ValueError("Reason must be a short printable explanation")
        return value.strip()

    @field_validator("confidence")
    @classmethod
    def finite_confidence(cls, value):
        if value is not None and not math.isfinite(value):
            raise ValueError("Confidence must be finite")
        return value

    @model_validator(mode="after")
    def consistent_unknowns(self):
        if (self.category == "unknown") != (self.priority == "unknown"):
            raise ValueError("Unknown category and priority must occur together")
        return self


class EnrichmentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    ticket_id: str
    model: str
    model_digest: str
    prompt_version: str
    schema_version: str
    status: EnrichmentStatus
    category: Category
    priority: Priority
    reason: str
    confidence: float | None
    attempts: int
    diagnostic_code: str
    duration_ms: int | None
    prompt_tokens: int | None
    completion_tokens: int | None
    started_at: datetime
    completed_at: datetime | None
    duplicate: bool = False
    retry_allowed: bool = False
    advisory_only: bool = True
