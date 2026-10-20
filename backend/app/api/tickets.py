from fastapi import APIRouter, Depends, Query, status, Response, HTTPException
from sqlalchemy.orm import Session
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
    db: Session = Depends(get_db),
):
    ticket, is_duplicate = ticket_service.create_or_get_ticket(
        db=db,
        ticket_in=payload,
        actor="api_client",
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
