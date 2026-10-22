from typing import Optional
from uuid import uuid4
from fastapi import APIRouter, Depends, Header, HTTPException, Query, Response
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.models.ticket import Ticket
from app.schemas.enrichment import EnrichmentResponse, MAX_ATTEMPTS
from app.schemas.tracing import TraceId
from app.services import enrichment_service

router = APIRouter(prefix="/tickets", tags=["Advisory AI enrichment"])


def as_response(row, duplicate=False):
    value = EnrichmentResponse.model_validate(row)
    return value.model_copy(update={
        "duplicate": duplicate,
        "retry_allowed": row.status == "unavailable" and row.attempts < MAX_ATTEMPTS,
    })


@router.post("/{ticket_id}/enrich", response_model=EnrichmentResponse, status_code=201)
async def enrich(
    ticket_id: str, response: Response, retry_unavailable: bool = Query(False),
    db: Session = Depends(get_db),
    x_correlation_id: Optional[TraceId] = Header(None),
    x_execution_id: Optional[TraceId] = Header(None),
):
    correlation_id = x_correlation_id or "corr-" + uuid4().hex
    row, duplicate = await enrichment_service.enrich_ticket(
        db, ticket_id, retry_unavailable, correlation_id, x_execution_id,
    )
    response.status_code = (
        202 if row.status == "processing" else 503 if row.status == "unavailable"
        else 200 if duplicate else 201
    )
    response.headers["X-Correlation-ID"] = correlation_id
    if row.status == "processing":
        response.headers["Retry-After"] = "2"
    return as_response(row, duplicate)


@router.get("/{ticket_id}/enrichment", response_model=EnrichmentResponse)
def read_enrichment(ticket_id: str, db: Session = Depends(get_db)):
    if db.get(Ticket, ticket_id) is None:
        raise HTTPException(status_code=404, detail="Ticket not found")
    row = enrichment_service.get_enrichment(db, ticket_id)
    if row is None:
        raise HTTPException(status_code=404, detail="No enrichment for the current model and schema version")
    return as_response(row)
