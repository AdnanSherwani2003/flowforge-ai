from fastapi import APIRouter, Depends, Query, Header, status, Response, HTTPException, Request
from typing import Optional
from sqlalchemy.orm import Session
from app.core.config import settings
from app.core.database import get_db
from app.schemas.ticket import TicketCreate, TicketResponse, TicketListResponse
from app.schemas.audit_event import TicketAuditResponse, AuditEventResponse
from app.services import ticket_service

router = APIRouter(prefix="/tickets", tags=["Support Tickets"])


@router.post(
    "",
    response_model=TicketResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Submit or deduplicate a customer support ticket",
)
def create_ticket(
    payload: TicketCreate,
    response: Response,
    request: Request,
    db: Session = Depends(get_db),
    x_correlation_id: Optional[str] = Header(default=None),
    x_execution_id: Optional[str] = Header(default=None),
    x_flowforge_simulate: Optional[str] = Header(default=None),
):
    # Isolated test-only failure simulation hook:
    # Requires BOTH settings.ENABLE_FAILURE_SIMULATION=True AND explicit X-FlowForge-Simulate header.
    # An ordinary user's source_event_id NEVER triggers any failure.
    if settings.ENABLE_FAILURE_SIMULATION and x_flowforge_simulate:
        if x_flowforge_simulate == "503":
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Database service is temporarily unavailable. Please retry shortly.",
            )
        elif x_flowforge_simulate == "timeout":
            import time
            time.sleep(6)
            raise HTTPException(
                status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                detail="Simulated gateway timeout",
            )
        elif x_flowforge_simulate == "conn-reset":
            transport = getattr(request, "scope", {}).get("transport")
            if transport:
                transport.abort()
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Connection reset simulated",
            )
        elif x_flowforge_simulate == "timeout-after-persist":
            # Case B: Persist record, then sleep 6s to trigger gateway timeout on caller
            actor = "n8n_workflow" if x_execution_id else "api_client"
            ticket, is_duplicate = ticket_service.create_or_get_ticket(
                db=db,
                ticket_in=payload,
                actor=actor,
                correlation_id=x_correlation_id,
                execution_id=x_execution_id,
            )
            import time
            time.sleep(6)
            raise HTTPException(
                status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                detail="Simulated gateway timeout after persistence",
            )

    actor = "n8n_workflow" if x_execution_id else "api_client"
    ticket, is_duplicate = ticket_service.create_or_get_ticket(
        db=db,
        ticket_in=payload,
        actor=actor,
        correlation_id=x_correlation_id,
        execution_id=x_execution_id,
    )
    if is_duplicate:
        response.status_code = status.HTTP_200_OK

    return TicketResponse(
        id=ticket.id,
        source_event_id=ticket.source_event_id,
        subject=ticket.subject,
        body=ticket.body,
        status=ticket.status,
        category=ticket.category,
        created_at=ticket.created_at,
        updated_at=ticket.updated_at,
        duplicate=is_duplicate,
    )


@router.get(
    "/{ticket_id}",
    response_model=TicketResponse,
    summary="Retrieve a ticket by ID",
)
def get_ticket(
    ticket_id: str,
    db: Session = Depends(get_db),
):
    ticket = ticket_service.get_ticket_by_id(db, ticket_id)
    if not ticket:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Ticket '{ticket_id}' not found",
        )
    return TicketResponse(
        id=ticket.id,
        source_event_id=ticket.source_event_id,
        subject=ticket.subject,
        body=ticket.body,
        status=ticket.status,
        category=ticket.category,
        created_at=ticket.created_at,
        updated_at=ticket.updated_at,
        duplicate=False,
    )


@router.get(
    "",
    response_model=TicketListResponse,
    summary="List tickets with bounded pagination",
)
def list_tickets(
    limit: int = Query(default=20, ge=1, le=100, description="Max records to return"),
    offset: int = Query(default=0, ge=0, description="Number of records to skip"),
    db: Session = Depends(get_db),
):
    items, total = ticket_service.list_tickets(db=db, limit=limit, offset=offset)
    return TicketListResponse(
        items=[
            TicketResponse(
                id=item.id,
                source_event_id=item.source_event_id,
                subject=item.subject,
                body=item.body,
                status=item.status,
                category=item.category,
                created_at=item.created_at,
                updated_at=item.updated_at,
                duplicate=False,
            )
            for item in items
        ],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/{ticket_id}/audit",
    response_model=TicketAuditResponse,
    summary="Get safe audit trail for a ticket",
)
def get_ticket_audit(
    ticket_id: str,
    db: Session = Depends(get_db),
):
    audit_events = ticket_service.get_ticket_audit_trail(db, ticket_id)
    return TicketAuditResponse(
        ticket_id=ticket_id,
        audit_events=[
            AuditEventResponse(
                id=e.id,
                entity_id=e.entity_id,
                event_type=e.event_type,
                actor=e.actor,
                timestamp=e.timestamp,
                safe_detail=e.safe_detail,
            )
            for e in audit_events
        ],
    )
