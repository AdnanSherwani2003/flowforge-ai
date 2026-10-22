from typing import Optional
from fastapi import APIRouter, Depends, Query, status, HTTPException
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.schemas.workflow_run import (
    WorkflowRunCreate,
    WorkflowRunResponse,
    WorkflowRunListResponse,
)
from app.services import workflow_run_service

router = APIRouter(prefix="/workflow-runs", tags=["Workflow Telemetry"])


@router.post(
    "",
    response_model=WorkflowRunResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Record an n8n workflow execution telemetry record",
)
def create_workflow_run(
    payload: WorkflowRunCreate,
    db: Session = Depends(get_db),
):
    run = workflow_run_service.record_workflow_run(db=db, run_in=payload)
    return WorkflowRunResponse.model_validate(run)


@router.get(
    "/{execution_id}",
    response_model=WorkflowRunResponse,
    summary="Retrieve workflow run by execution ID",
)
def get_workflow_run(
    execution_id: str,
    db: Session = Depends(get_db),
):
    run = workflow_run_service.get_workflow_run_by_execution_id(db=db, execution_id=execution_id)
    if not run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Workflow run for execution '{execution_id}' not found",
        )
    return WorkflowRunResponse.model_validate(run)


@router.get(
    "",
    response_model=WorkflowRunListResponse,
    summary="List workflow runs with bounded pagination",
)
def list_workflow_runs(
    limit: int = Query(default=20, ge=1, le=100, description="Max records to return"),
    offset: int = Query(default=0, ge=0, description="Records to skip"),
    correlation_id: Optional[str] = Query(default=None, description="Filter by correlation ID"),
    source_event_id: Optional[str] = Query(default=None, description="Filter by source event ID"),
    outcome: Optional[str] = Query(default=None, description="Filter by outcome"),
    db: Session = Depends(get_db),
):
    items, total = workflow_run_service.list_workflow_runs(
        db=db,
        limit=limit,
        offset=offset,
        correlation_id=correlation_id,
        source_event_id=source_event_id,
        outcome=outcome,
    )
    return WorkflowRunListResponse(
        items=[WorkflowRunResponse.model_validate(i) for i in items],
        total=total,
        limit=limit,
        offset=offset,
    )
