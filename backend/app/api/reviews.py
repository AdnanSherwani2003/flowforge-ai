from typing import Literal
from fastapi import APIRouter, Depends, Query, Response
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.config import settings
from app.core.reviewer_auth import reviewer, authenticate
from app.services import review_service

router = APIRouter(tags=["Human review"])


class Login(BaseModel):
    model_config = ConfigDict(extra="forbid")
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=200)


class Decision(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    enrichment_id: str = Field(min_length=1, max_length=36)
    expected_revision: int = Field(ge=1)
    note: str | None = Field(default=None, max_length=500)

    @field_validator("note")
    @classmethod
    def bounded_note(cls, v):
        if v is not None and (not v.strip() or not v.isprintable()):
            raise ValueError("Use a nonempty printable note")
        return v.strip() if v is not None else None


class Rejection(Decision):
    note: str = Field(min_length=1, max_length=500)


@router.post("/reviewer/login")
def login(payload: Login, response: Response):
    response.headers["Cache-Control"] = "no-store"
    return {"token": authenticate(payload.username, payload.password), "expires_in": settings.REVIEWER_SESSION_SECONDS}


@router.get("/reviewer/session")
def session(user: str = Depends(reviewer)):
    return {"reviewer": user}


@router.get("/reviews/summary")
def summary(db: Session = Depends(get_db), user: str = Depends(reviewer)):
    return review_service.summary(db)


@router.get("/reviews")
def list_reviews(status: Literal["pending", "approved", "rejected", "attention"] | None = None,
                 limit: int = Query(20, ge=1, le=50), offset: int = Query(0, ge=0, le=10000),
                 ticket_id: str | None = Query(None, max_length=36), final_only: bool = False,
                 db: Session = Depends(get_db), user: str = Depends(reviewer)):
    return review_service.list_reviews(db, status, limit, offset, ticket_id, final_only)


@router.get("/reviews/{review_id}")
def detail(review_id: str, db: Session = Depends(get_db), user: str = Depends(reviewer)):
    return review_service.get_detail(db, review_id)


@router.get("/reviews/{review_id}/history")
def history(review_id: str, db: Session = Depends(get_db), user: str = Depends(reviewer)):
    return review_service.history(db, review_id)


@router.post("/reviews/{review_id}/approve")
def approve(review_id: str, payload: Decision, db: Session = Depends(get_db), user: str = Depends(reviewer)):
    return review_service.decide(db, review_id, payload, "approved", user)


@router.post("/reviews/{review_id}/reject")
def reject(review_id: str, payload: Rejection, db: Session = Depends(get_db), user: str = Depends(reviewer)):
    return review_service.decide(db, review_id, payload, "rejected", user)
