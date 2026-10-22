import uuid
from typing import Tuple, List, Optional
from sqlalchemy import select, func, desc
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from app.models.workflow_run import WorkflowRun
from app.schemas.workflow_run import WorkflowRunCreate


def record_workflow_run(
    db: Session,
    run_in: WorkflowRunCreate,
) -> WorkflowRun:
    """Records a workflow execution event for end-to-end traceability with idempotency on (workflow_name, execution_id)."""
    if run_in.execution_id and run_in.execution_id != "unknown":
        existing = db.execute(
            select(WorkflowRun).where(
                WorkflowRun.workflow_name == run_in.workflow_name,
                WorkflowRun.execution_id == run_in.execution_id,
            )
        ).scalar_one_or_none()
        if existing:
            return existing

    run = WorkflowRun(
        id=str(uuid.uuid4()),
        workflow_name=run_in.workflow_name,
        execution_id=run_in.execution_id,
        correlation_id=run_in.correlation_id,
        source_event_id=run_in.source_event_id,
        ticket_id=run_in.ticket_id,
        outcome=run_in.outcome,
        status_code=run_in.status_code,
        safe_detail=run_in.safe_detail,
    )
    db.add(run)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        existing = db.execute(
            select(WorkflowRun).where(
                WorkflowRun.workflow_name == run_in.workflow_name,
                WorkflowRun.execution_id == run_in.execution_id,
            )
        ).scalar_one_or_none()
        if existing:
            return existing
        raise
    db.refresh(run)
    return run


def get_workflow_run_by_execution_id(
    db: Session,
    execution_id: str,
) -> Optional[WorkflowRun]:
    stmt = (
        select(WorkflowRun)
        .where(WorkflowRun.execution_id == execution_id)
        .order_by(desc(WorkflowRun.created_at))
        .limit(1)
    )
    return db.execute(stmt).scalar_one_or_none()


def list_workflow_runs(
    db: Session,
    limit: int = 20,
    offset: int = 0,
    correlation_id: Optional[str] = None,
    source_event_id: Optional[str] = None,
    outcome: Optional[str] = None,
) -> Tuple[List[WorkflowRun], int]:
    stmt = select(WorkflowRun)
    count_stmt = select(func.count(WorkflowRun.id))

    if correlation_id:
        stmt = stmt.where(WorkflowRun.correlation_id == correlation_id)
        count_stmt = count_stmt.where(WorkflowRun.correlation_id == correlation_id)
    if source_event_id:
        stmt = stmt.where(WorkflowRun.source_event_id == source_event_id)
        count_stmt = count_stmt.where(WorkflowRun.source_event_id == source_event_id)
    if outcome:
        stmt = stmt.where(WorkflowRun.outcome == outcome)
        count_stmt = count_stmt.where(WorkflowRun.outcome == outcome)

    total = db.scalar(count_stmt) or 0
    stmt = stmt.order_by(desc(WorkflowRun.created_at), desc(WorkflowRun.id)).limit(limit).offset(offset)
    items = list(db.scalars(stmt).all())
    return items, total
