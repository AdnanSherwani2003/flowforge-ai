import concurrent.futures
import threading
import uuid
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text, select, func
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from app.core.config import settings
from app.models.ticket_enrichment import TicketEnrichment
from app.schemas.ticket import TicketCreate
from app.services.ticket_service import create_or_get_ticket
from app.services import enrichment_service as service
from app.services.ollama_client import InferenceOutcome
from tests.test_postgres_integration import pg_isolated_engine


def test_postgres_forced_enrichment_race(pg_isolated_engine):
    with Session(pg_isolated_engine) as db:
        ticket, _ = create_or_get_ticket(db, TicketCreate(
            source_event_id="ai-race-" + uuid.uuid4().hex, subject="Synthetic refund", body="Duplicate charge."))
        ticket_id = ticket.id
    barrier = threading.Barrier(5)
    class RacingSession(Session):
        initial_read = True
        def execute(self, statement, *args, **kwargs):
            result = super().execute(statement, *args, **kwargs)
            if self.initial_read and getattr(statement, "is_select", False) and "ticket_enrichments" in str(statement):
                self.initial_read = False
                assert result.scalar_one_or_none() is None
                barrier.wait(timeout=10)
                class Empty:
                    def scalar_one_or_none(self):
                        return None
                return Empty()
            return result
    def claim(_):
        with RacingSession(pg_isolated_engine) as db:
            row, token, *_ = service.claim_enrichment(db, ticket_id)
            return row.id, token
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as pool:
        results = list(pool.map(claim, range(5)))
    assert len({row_id for row_id, _ in results}) == 1
    assert sum(token is not None for _, token in results) == 1
    with Session(pg_isolated_engine) as db:
        row_id, token = next(pair for pair in results if pair[1])
        service.finish_enrichment(db, row_id, token, InferenceOutcome("unavailable", "timeout"))
        row = db.get(TicketEnrichment, row_id)
        row.attempts = 4
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()
        assert db.scalar(select(func.count(TicketEnrichment.id)).where(TicketEnrichment.ticket_id == ticket_id)) == 1


def test_actual_migration_preserves_existing_ticket(monkeypatch):
    # All migration operations are confined to a fresh disposable test schema.
    name = "test_ai_migration_" + uuid.uuid4().hex
    admin = create_engine(settings.sync_database_url, isolation_level="AUTOCOMMIT")
    with admin.connect() as db:
        db.execute(text("CREATE SCHEMA " + name))
    engine = create_engine(settings.sync_database_url, connect_args={"options": "-csearch_path=" + name})
    monkeypatch.setenv("ALEMBIC_SCHEMA", name)
    config = Config(str(Path("alembic.ini").resolve()))
    try:
        with engine.connect() as connection:
            command.upgrade(config, "003_workflow_runs_unique")
            connection.execute(text(
                "INSERT INTO tickets (id,source_event_id,subject,body,status,category,payload_hash) "
                "VALUES ('migration-ticket','migration-event','Synthetic','Preserve me','received','general','0000000000000000000000000000000000000000000000000000000000000000')"))
            connection.commit()
            command.upgrade(config, "004_ticket_enrichments")
            assert connection.scalar(text("SELECT body FROM tickets WHERE id='migration-ticket'")) == "Preserve me"
            assert connection.scalar(text("SELECT version_num FROM alembic_version")) == "004_ticket_enrichments"
            assert connection.scalar(text("SELECT count(*) FROM ticket_enrichments")) == 0
            connection.commit()
            command.downgrade(config, "003_workflow_runs_unique")
            assert connection.scalar(text("SELECT count(*) FROM tickets")) == 1
    finally:
        engine.dispose()
        with admin.connect() as db:
            db.execute(text("DROP SCHEMA " + name + " CASCADE"))
        admin.dispose()
