from datetime import date, datetime
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator


class DigestGenerate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reporting_date: date | None = None

    @field_validator("reporting_date", mode="before")
    @classmethod
    def explicit_iso_date(cls, value):
        if value is None:
            return None
        if not isinstance(value, str) or len(value) != 10:
            raise ValueError("Use a calendar date in YYYY-MM-DD format")
        import re
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
            raise ValueError("Use a calendar date in YYYY-MM-DD format")
        return value


class CountModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class LeadRequests(CountModel):
    created_records: int = Field(ge=0)
    event_replays: int = Field(ge=0)
    email_matches: int = Field(ge=0)
    legacy_duplicates: int = Field(ge=0)


class EnrichmentResults(CountModel):
    succeeded: int = Field(ge=0)
    needs_review: int = Field(ge=0)
    unavailable: int = Field(ge=0)


class ReviewDecisions(CountModel):
    approved: int = Field(ge=0)
    rejected: int = Field(ge=0)


class PeriodActivity(CountModel):
    tickets_created: int = Field(ge=0)
    canonical_leads_created: int = Field(ge=0)
    lead_requests_observed: LeadRequests
    enrichment_results_completed: EnrichmentResults
    review_decisions: ReviewDecisions


class CurrentSnapshot(CountModel):
    pending_reviews: int = Field(ge=0)
    attention_reviews: int = Field(ge=0)
    processing_enrichments: int = Field(ge=0)


class DigestMetrics(CountModel):
    activity: PeriodActivity
    snapshot: CurrentSnapshot


class DigestResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    reporting_date: date
    reporting_timezone: str
    period_start: datetime
    period_end: datetime
    generated_at: datetime
    metrics_version: Literal[1]
    metrics: DigestMetrics
    status: Literal["ready"]
    duplicate: bool = False


class DigestListResponse(BaseModel):
    items: list[DigestResponse]
    total: int
    limit: int
    offset: int
    reporting_timezone: str
    previous_completed_date: date
