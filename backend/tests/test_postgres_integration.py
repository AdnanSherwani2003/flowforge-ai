import os
import uuid
import threading
import concurrent.futures
import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from app.core.config import settings
from app.models.base import Base
from app.schemas.ticket import TicketCreate
from app.schemas.lead import LeadCreate
from app.services.ticket_service import create_or_get_ticket, get_ticket_by_id
from app.services.lead_service import create_or_get_lead, get_lead_by_id
from app.models.ticket import Ticket
from app.models.audit_event import AuditEvent


@pytest.fixture(scope="module")
def pg_isolated_engine():
    db_url = settings.sync_database_url
    if "sqlite" in db_url:
        pytest.skip("PostgreSQL is not configured in current test environment")

    admin_engine = create_engine(db_url, isolation_level="AUTOCOMMIT")
    schema_name = "test_isolated_" + uuid.uuid4().hex

    try:
        with admin_engine.connect() as conn:
            conn.execute(text(f"CREATE SCHEMA {schema_name}"))
    except Exception:
        admin_engine.dispose()
        pytest.fail("Configured PostgreSQL is unavailable (connection details suppressed)")

    isolated_engine = create_engine(
        db_url,
        connect_args={"options": f"-csearch_path={schema_name}"},
        pool_size=10,
        max_overflow=5,
    )

    Base.metadata.create_all(bind=isolated_engine)

    yield isolated_engine

    Base.metadata.drop_all(bind=isolated_engine)
    with admin_engine.connect() as conn:
        conn.execute(text(f"DROP SCHEMA {schema_name} CASCADE"))
    isolated_engine.dispose()
    admin_engine.dispose()


@pytest.fixture(scope="function")
def pg_session(pg_isolated_engine):
    Session = sessionmaker(autocommit=False, autoflush=False, bind=pg_isolated_engine)
    session = Session()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


def test_real_postgres_ticket_persistence(pg_session):
    ticket_in = TicketCreate(
        source_event_id="pg-int-evt-001",
        subject="PostgreSQL Integration Ticket",
        body="Testing real PostgreSQL persistence in dedicated test schema.",
    )
    ticket, is_dup = create_or_get_ticket(pg_session, ticket_in, actor="pg_test_runner")
    assert is_dup is False
    assert ticket.id is not None

    fetched = get_ticket_by_id(pg_session, ticket.id)
    assert fetched is not None
    assert fetched.source_event_id == "pg-int-evt-001"
    assert fetched.status == "received"


def test_real_postgres_uniqueness_and_idempotency(pg_session):
    ticket_in = TicketCreate(
        source_event_id="pg-int-evt-idem-01",
        subject="PostgreSQL Idempotency Check",
        body="Verifying duplicate event handling on real PostgreSQL database.",
    )
    t1, dup1 = create_or_get_ticket(pg_session, ticket_in, actor="pg_test_runner")
    assert dup1 is False

    t2, dup2 = create_or_get_ticket(pg_session, ticket_in, actor="pg_test_runner")
    assert dup2 is True
    assert t2.id == t1.id

    audit_events = pg_session.query(AuditEvent).filter(AuditEvent.entity_id == t1.id).all()
    assert len(audit_events) >= 2
    types = [a.event_type for a in audit_events]
    assert "ticket_created" in types
    assert "ticket_duplicate_received" in types


def test_real_postgres_multithreaded_concurrency(pg_isolated_engine):
    WorkerSession = sessionmaker(autocommit=False, autoflush=False, bind=pg_isolated_engine)
    payload = TicketCreate(
        source_event_id="pg-concurrent-race-01",
        subject="Concurrent PostgreSQL Test",
        body="High concurrency test across separate database connections.",
    )

    results = []

    def submit():
        session = WorkerSession()
        try:
            ticket, is_dup = create_or_get_ticket(session, payload, actor="pg_thread_test")
            return (ticket.id, is_dup)
        finally:
            session.close()

    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        futures = [executor.submit(submit) for _ in range(5)]
        for f in concurrent.futures.as_completed(futures):
            results.append(f.result())

    assert len(results) == 5
    ticket_ids = {r[0] for r in results}
    assert len(ticket_ids) == 1

    duplicates = [r[1] for r in results]
    assert duplicates.count(False) == 1
    assert duplicates.count(True) == 4


def test_real_postgres_lead_persistence(pg_session):
    lead_in = LeadCreate(
        source_event_id="pg-lead-evt-001",
        name="Real PostgreSQL Lead",
        email="  Real.PG.Lead@Example.COM  ",
    )
    lead, dup = create_or_get_lead(pg_session, lead_in, actor="pg_test_runner")
    assert dup is False
    assert lead.normalized_email == "real.pg.lead@example.com"

    fetched = get_lead_by_id(pg_session, lead.id)
    assert fetched is not None
    assert fetched.normalized_email == "real.pg.lead@example.com"


def test_real_postgres_workflow_run_concurrency(pg_isolated_engine):
    from app.services.workflow_run_service import record_workflow_run
    from app.schemas.workflow_run import WorkflowRunCreate
    WorkerSession = sessionmaker(autocommit=False, autoflush=False, bind=pg_isolated_engine)
    payload = WorkflowRunCreate(
        workflow_name="support_ticket_intake",
        execution_id="pg-concurrent-exec-01",
        correlation_id="pg-concurrent-corr-01",
        source_event_id="pg-concurrent-evt-01",
        outcome="created",
        status_code=201,
        safe_detail={"status": "accepted"},
    )

    results = []

    def submit():
        session = WorkerSession()
        try:
            run = record_workflow_run(session, payload)
            return run.id
        finally:
            session.close()

    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        futures = [executor.submit(submit) for _ in range(5)]
        for f in concurrent.futures.as_completed(futures):
            results.append(f.result())

    assert len(results) == 5
    run_ids = set(results)
    # Exactly one unique row should be created and shared among all 5 concurrent threads
    assert len(run_ids) == 1


@pytest.mark.parametrize("conflicting", [False, True])
def test_real_postgres_forced_race_retains_trace(pg_isolated_engine, conflicting):
    from fastapi import HTTPException
    from sqlalchemy.orm import Session
    from sqlalchemy import select, func

    barrier = threading.Barrier(6)
    event_id = "forced-race-" + uuid.uuid4().hex

    class RacingSession(Session):
        initial_read = True

        def execute(self, statement, *args, **kwargs):
            result = super().execute(statement, *args, **kwargs)
            if self.initial_read and getattr(statement, "is_select", False):
                self.initial_read = False
                # Every transaction observes absence before any INSERT is attempted.
                assert result.scalar_one_or_none() is None
                barrier.wait(timeout=10)

                class EmptyResult:
                    def scalar_one_or_none(self):
                        return None
                return EmptyResult()
            return result

    def submit(index):
        with RacingSession(bind=pg_isolated_engine, autoflush=False) as session:
            payload = TicketCreate(
                source_event_id=event_id,
                subject="Synthetic " + str(index % 2 if conflicting else 0),
                body="Synthetic race only",
            )
            try:
                ticket, duplicate = create_or_get_ticket(
                    session, payload, correlation_id=f"corr-race-{index}",
                    execution_id=f"exec-race-{index}",
                )
                return 200 if duplicate else 201
            except HTTPException as exc:
                assert exc.status_code == 409
                return 409

    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as executor:
        results = list(executor.map(submit, range(6)))
    assert results.count(201) == 1
    assert results.count(200) == (2 if conflicting else 5)
    assert results.count(409) == (3 if conflicting else 0)
    with Session(pg_isolated_engine) as session:
        ticket = session.execute(select(Ticket).where(Ticket.source_event_id == event_id)).scalar_one()
        assert session.scalar(select(func.count(Ticket.id)).where(Ticket.source_event_id == event_id)) == 1
        events = session.scalars(select(AuditEvent).where(AuditEvent.entity_id == ticket.id)).all()
        assert len(events) == 6
        assert {e.safe_detail["correlation_id"] for e in events} == {f"corr-race-{i}" for i in range(6)}
        assert {e.safe_detail["execution_id"] for e in events} == {f"exec-race-{i}" for i in range(6)}
        assert all("subject" not in e.safe_detail and "body" not in e.safe_detail for e in events)
        assert any(e.safe_detail.get("action", "").startswith("concurrent_") for e in events)
