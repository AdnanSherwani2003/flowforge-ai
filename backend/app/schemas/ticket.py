from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field, field_validator, ConfigDict


class TicketCreate(BaseModel):
    source_event_id: str = Field(
        ...,
        description="Unique event identifier from external caller",
        min_length=1,
        max_length=128,
    )
    subject: str = Field(
        ...,
        description="Ticket subject summary",
        min_length=1,
        max_length=200,
    )
    body: str = Field(
        ...,
        description="Detailed ticket issue content",
        min_length=1,
        max_length=5000,
    )

    @field_validator("source_event_id", "subject", "body", mode="before")
    @classmethod
    def validate_and_strip_strings(cls, v: str) -> str:
        if not isinstance(v, str):
            raise ValueError("Value must be a string")
        stripped = v.strip()
        if not stripped:
            raise ValueError("Field cannot be empty or whitespace-only")
        return stripped

    @field_validator("subject")
    @classmethod
    def validate_subject_length(cls, v: str) -> str:
        if len(v) > 200:
            raise ValueError("Subject cannot exceed 200 characters")
        return v

    @field_validator("body")
    @classmethod
    def validate_body_length(cls, v: str) -> str:
        if len(v) > 5000:
            raise ValueError("Body cannot exceed 5000 characters")
        return v


class TicketResponse(BaseModel):
    id: str
    source_event_id: str
    subject: str
    body: str
    status: str
    category: str
    created_at: datetime
    updated_at: Optional[datetime] = None
    duplicate: bool = False

    model_config = ConfigDict(from_attributes=True)


class TicketListResponse(BaseModel):
    items: List[TicketResponse]
    total: int
    limit: int
    offset: int
