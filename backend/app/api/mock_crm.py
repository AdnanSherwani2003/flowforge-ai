from fastapi import APIRouter, Depends, Query, status, Response, HTTPException
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.schemas.lead import LeadCreate, LeadResponse, LeadListResponse
from app.services import lead_service

router = APIRouter(prefix="/mock-crm", tags=["Mock CRM"])


@router.post(
    "/leads",
    response_model=LeadResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Ingest a new lead with duplicate protection",
)
def create_lead(
    payload: LeadCreate,
    response: Response,
    db: Session = Depends(get_db),
):
    lead, is_duplicate = lead_service.create_or_get_lead(
        db=db,
        lead_in=payload,
        actor="api_client",
    )
    if is_duplicate:
        response.status_code = status.HTTP_200_OK

    return LeadResponse(
        id=lead.id,
        source_event_id=lead.source_event_id,
        normalized_email=lead.normalized_email,
        name=lead.name,
        status=lead.status,
        created_at=lead.created_at,
        duplicate=is_duplicate,
    )


@router.get(
    "/leads/{lead_id}",
    response_model=LeadResponse,
    summary="Retrieve a lead by ID",
)
def get_lead(
    lead_id: str,
    db: Session = Depends(get_db),
):
    lead = lead_service.get_lead_by_id(db, lead_id)
    if not lead:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Lead '{lead_id}' not found",
        )
    return LeadResponse(
        id=lead.id,
        source_event_id=lead.source_event_id,
        normalized_email=lead.normalized_email,
        name=lead.name,
        status=lead.status,
        created_at=lead.created_at,
        duplicate=False,
    )


@router.get(
    "/leads",
    response_model=LeadListResponse,
    summary="List leads with bounded pagination",
)
def list_leads(
    limit: int = Query(default=20, ge=1, le=100, description="Max records to return"),
    offset: int = Query(default=0, ge=0, description="Number of records to skip"),
    db: Session = Depends(get_db),
):
    items, total = lead_service.list_leads(db=db, limit=limit, offset=offset)
    return LeadListResponse(
        items=[
            LeadResponse(
                id=item.id,
                source_event_id=item.source_event_id,
                normalized_email=item.normalized_email,
                name=item.name,
                status=item.status,
                created_at=item.created_at,
                duplicate=False,
            )
            for item in items
        ],
        total=total,
        limit=limit,
        offset=offset,
    )
