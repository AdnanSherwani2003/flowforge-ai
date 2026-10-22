from datetime import datetime
from typing import List, Literal, Optional
from pydantic import BaseModel, Field, EmailStr, field_validator, ConfigDict


class LeadCreate(BaseModel):
    source_event_id: str = Field(
        ...,
        description="Unique event identifier for lead",
        min_length=1,
        max_length=128,
    )
    name: str = Field(
        ...,
        description="Lead contact name",
        min_length=1,
        max_length=100,
    )
    email: EmailStr = Field(
        ...,
        description="Lead contact email",
        max_length=255,
    )

    @field_validator("source_event_id", "name", mode="before")
    @classmethod
    def validate_and_strip_strings(cls, v: str) -> str:
        if not isinstance(v, str):
            raise ValueError("Value must be a string")
        stripped = v.strip()
        if not stripped:
            raise ValueError("Field cannot be empty or whitespace-only")
        return stripped

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email(cls, v: str) -> str:
        if not isinstance(v, str):
            raise ValueError("Email must be a string")
        stripped = v.strip().lower()
        if not stripped:
            raise ValueError("Email cannot be empty or whitespace-only")
        return stripped


class LeadResponse(BaseModel):
    id: str
    source_event_id: str
    normalized_email: str
    name: str
    status: str
    created_at: datetime
    duplicate: bool = False
    duplicate_reason: Optional[Literal["event", "email"]] = None
    submitted_source_event_id: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class LeadListResponse(BaseModel):
    items: List[LeadResponse]
    total: int
    limit: int
    offset: int
