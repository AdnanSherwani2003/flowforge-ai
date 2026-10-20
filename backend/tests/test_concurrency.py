from unittest.mock import patch
import pytest
from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from app.schemas.ticket import TicketCreate
from app.services.ticket_service import create_or_get_ticket


def test_concurrency_race_condition_recovery(db_session):
    """Simulates the database race condition where another concurrent worker inserts
    the same source_event_id between the initial SELECT check and db.flush(), triggering IntegrityError.
    Verifies that the service safely catches IntegrityError, rolls back, re-queries existing record,
    and returns it as duplicate=True.
    """
    payload = TicketCreate(
        source_event_id="evt-race-sim-001",
        subject="High traffic alert",
        body="API gateway reported 5000 req/sec spike.",
    )

    # 1. Normal first insertion succeeds
    ticket1, is_dup1 = create_or_get_ticket(db_session, payload, actor="worker_1")
    assert is_dup1 is False
    assert ticket1.id is not None

    # 2. To simulate race condition:
    # Worker 2 does initial SELECT check -> pretend it returned None (race window)
    # Then db.flush() raises IntegrityError because worker 1 already committed
    # Then after rollback, the re-query finds ticket1
    call_count = {"select": 0, "flush": 0}
    orig_execute = db_session.execute
    orig_flush = db_session.flush

    def mocked_execute(*args, **kwargs):
        call_count["select"] += 1
        if call_count["select"] == 1:
            # First SELECT: pretend record does not exist yet (race window)
            class MockResult:
                def scalar_one_or_none(self):
                    return None
            return MockResult()
        # Second SELECT (inside except IntegrityError): return real query result
        return orig_execute(*args, **kwargs)

    def mocked_flush(*args, **kwargs):
        call_count["flush"] += 1
        if call_count["flush"] == 1:
            # First flush raises IntegrityError due to unique constraint collision
            raise IntegrityError("duplicate key value violates unique constraint", params={}, orig=Exception())
        return orig_flush(*args, **kwargs)

    with patch.object(db_session, "execute", side_effect=mocked_execute):
        with patch.object(db_session, "flush", side_effect=mocked_flush):
            ticket2, is_dup2 = create_or_get_ticket(db_session, payload, actor="worker_2")
            assert is_dup2 is True
            assert ticket2.id == ticket1.id


def test_concurrency_conflict_recovery(db_session):
    """Simulates race condition where a concurrent request with same source_event_id
    but conflicting payload collides on flush, catches IntegrityError, and properly raises 409 Conflict.
    """
    payload = TicketCreate(
        source_event_id="evt-race-sim-002",
        subject="Initial Subject",
        body="Initial Body",
    )
    ticket1, is_dup1 = create_or_get_ticket(db_session, payload, actor="worker_1")
    assert is_dup1 is False

    conflict_payload = TicketCreate(
        source_event_id="evt-race-sim-002",
        subject="Different Subject",
        body="Different Body",
    )

    call_count = {"select": 0, "flush": 0}
    orig_execute = db_session.execute
    orig_flush = db_session.flush

    def mocked_execute(*args, **kwargs):
        call_count["select"] += 1
        if call_count["select"] == 1:
            class MockResult:
                def scalar_one_or_none(self):
                    return None
            return MockResult()
        return orig_execute(*args, **kwargs)

    def mocked_flush(*args, **kwargs):
        call_count["flush"] += 1
        if call_count["flush"] == 1:
            raise IntegrityError("duplicate key", params={}, orig=Exception())
        return orig_flush(*args, **kwargs)

    with patch.object(db_session, "execute", side_effect=mocked_execute):
        with patch.object(db_session, "flush", side_effect=mocked_flush):
            with pytest.raises(HTTPException) as exc_info:
                create_or_get_ticket(db_session, conflict_payload, actor="worker_3")
            assert exc_info.value.status_code == 409
            assert "conflict" in exc_info.value.detail.lower()
