import secrets
from uuid import uuid4
from datetime import date
from typing import Optional
from fastapi import APIRouter, Depends, Header, Query, Response
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from app.core.config import settings
from app.core.database import get_db
from app.core.reviewer_auth import BEARER, reviewer
from app.schemas.tracing import TraceId
from app.schemas.digest import DigestGenerate, DigestResponse, DigestListResponse
from app.services import digest_service

router = APIRouter(prefix="/digests", tags=["Daily operations digest"])


def generator(credentials: Optional[HTTPAuthorizationCredentials] = Depends(BEARER),
              x_flowforge_digest_key: Optional[str] = Header(default=None)):
    if (x_flowforge_digest_key and len(settings.DIGEST_SERVICE_KEY) >= 32
            and secrets.compare_digest(x_flowforge_digest_key.encode(), settings.DIGEST_SERVICE_KEY.encode())):
        return "n8n_digest_service"
    return reviewer(credentials)


@router.post("/generate", response_model=DigestResponse, status_code=201)
def generate(payload: DigestGenerate, response: Response,
             user: str = Depends(generator), db: Session = Depends(get_db),
             x_correlation_id: Optional[TraceId] = Header(default=None),
             x_execution_id: Optional[TraceId] = Header(default=None)):
    correlation_id = x_correlation_id or "corr-" + uuid4().hex
    row, duplicate = digest_service.generate_digest(db, payload.reporting_date, actor=user,
        correlation_id=correlation_id, execution_id=x_execution_id)
    response.status_code = 200 if duplicate else 201
    response.headers["X-Correlation-ID"] = correlation_id
    return DigestResponse.model_validate(row).model_copy(update={"duplicate": duplicate})


@router.get("", response_model=DigestListResponse)
def list_reports(reporting_date: Optional[date] = None,
                 limit: int = Query(20, ge=1, le=50), offset: int = Query(0, ge=0, le=10000),
                 user: str = Depends(reviewer), db: Session = Depends(get_db)):
    rows, total = digest_service.list_digests(db, reporting_date, limit, offset)
    previous, zone, _, _ = digest_service.reporting_period()
    return DigestListResponse(items=rows, total=total, limit=limit, offset=offset,
                              reporting_timezone=zone, previous_completed_date=previous)


@router.get("/{digest_id}", response_model=DigestResponse)
def detail(digest_id: str, user: str = Depends(reviewer), db: Session = Depends(get_db)):
    return digest_service.get_digest(db, digest_id)
