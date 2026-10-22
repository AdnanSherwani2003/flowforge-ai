"""Lead contracts, durable email aliases and genuine PostgreSQL races."""
import json
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, select, func, text
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from alembic import command
from alembic.config import Config
from app.core.config import settings
from app.models.lead import Lead
from app.models.lead_intake import LeadIdentity, LeadEvent
from app.models.audit_event import AuditEvent
from app.schemas.lead import LeadCreate
from app.services.lead_service import ingest_lead, compute_lead_canonical_hash
from tests.test_postgres_integration import pg_isolated_engine  # noqa: F401

URL = "/api/mock-crm/leads"
BASE = {"source_event_id": "lead-one", "name": "Synthetic Person", "email": "one@example.com"}


def test_email_alias_is_durable_and_never_overwrites(client, db_session):
    a = client.post(URL, json=BASE).json()
    alias = {**BASE, "source_event_id": "lead-two", "name": "Different Synthetic"}
    b = client.post(URL, json=alias)
    assert b.status_code == 200
    assert b.json()["id"] == a["id"] and b.json()["duplicate_reason"] == "email"
    assert b.json()["name"] == BASE["name"]
    assert b.json()["source_event_id"] == BASE["source_event_id"]
    assert b.json()["submitted_source_event_id"] == alias["source_event_id"]
    assert client.post(URL, json=alias).json()["duplicate_reason"] == "event"
    assert client.post(URL, json={**alias, "name": "Changed"}).status_code == 409
    assert client.post(URL, json={**alias, "email": "another@example.com"}).status_code == 409
    assert client.get(URL+"/"+a["id"]).json()["name"] == BASE["name"]
    assert db_session.scalar(select(func.count(Lead.id))) == 1
    assert db_session.scalar(select(func.count(LeadEvent.source_event_id))) == 2


def test_normalization_and_safe_trace_audit(client, db_session):
    p = {"source_event_id":"  event-norm  ", "name":"  Synthetic  ", "email":"  Normal.Case@EXAMPLE.COM "}
    response = client.post(URL, json=p, headers={"X-Correlation-ID":"corr-lead","X-Execution-ID":"exec-lead"})
    assert response.status_code == 201 and response.headers["X-Correlation-ID"] == "corr-lead"
    a = response.json()
    assert a["normalized_email"] == "normal.case@example.com" and a["name"] == "Synthetic"
    assert client.post(URL,json={**p,"email":"normal.case@example.com","source_event_id":"other"}).json()["id"] == a["id"]
    events = db_session.scalars(select(AuditEvent)).all()
    detail = events[0].safe_detail
    assert detail["correlation_id"] == "corr-lead" and detail["execution_id"] == "exec-lead"
    assert events[0].actor == "n8n_workflow"
    assert "email" not in json.dumps([e.safe_detail for e in events if e.event_type=="lead_created"])
    assert "Synthetic" not in json.dumps([e.safe_detail for e in events])


@pytest.mark.parametrize("patch", [
    {"name":123},{"name":None},{"name":[]},{"email":123},{"email":True},{"email":{}},
    {"source_event_id":12},{"source_event_id":[]},{"email":"private-canary"},
    {"name":"  "},{"email":""},{"source_event_id":""},
])
def test_reject_wrong_types_without_raw_input(client, patch):
    response = client.post(URL,json={**BASE,**patch})
    assert response.status_code == 422
    assert "private-canary" not in response.text and '"input"' not in response.text


@pytest.mark.parametrize("body",[{},[],None,"synthetic-private"])
def test_reject_missing_or_wrong_body(client,body):
    response=client.post(URL,json=body)
    assert response.status_code == 422 and "synthetic-private" not in response.text


@pytest.mark.parametrize("header",["bad trace","x"*101])
def test_reject_invalid_lead_trace(client,header):
    assert client.post(URL,json=BASE,headers={"X-Correlation-ID":header}).status_code == 422


@pytest.mark.parametrize("mode",["same_event","same_email","conflicting_event"])
def test_real_pg_lead_concurrency(pg_isolated_engine,mode):
    tag=uuid.uuid4().hex
    barrier=threading.Barrier(6)
    def worker(i):
        payload=LeadCreate(source_event_id=tag+("-"+str(i) if mode=="same_email" else ""),
            name="Synthetic "+str(i%2 if mode=="conflicting_event" else 0),
            email=tag+"@example.com")
        with Session(pg_isolated_engine) as db:
            barrier.wait(timeout=10)
            try:
                result=ingest_lead(db,payload,correlation_id="corr-"+str(i),execution_id="exec-"+str(i))
                return (200 if result.duplicate else 201), result.lead.id
            except HTTPException as exc:
                assert exc.status_code==409
                return 409,None
    with ThreadPoolExecutor(max_workers=6) as pool:results=list(pool.map(worker,range(6)))
    codes=[x[0] for x in results]
    assert codes.count(201)==1
    assert codes.count(200)==(2 if mode=="conflicting_event" else 5)
    assert codes.count(409)==(3 if mode=="conflicting_event" else 0)
    ids={id for _,id in results if id}
    assert len(ids)==1
    with Session(pg_isolated_engine) as db:
        assert db.scalar(select(func.count(Lead.id)).where(Lead.normalized_email==tag+"@example.com"))==1
        lead_id=ids.pop()
        assert db.scalar(select(func.count(LeadEvent.source_event_id)).where(LeadEvent.lead_id==lead_id))==(6 if mode=="same_email" else 1)
        events=db.scalars(select(AuditEvent).where(AuditEvent.entity_id==lead_id)).all()
        assert len(events)==6 and len({e.safe_detail["execution_id"] for e in events})==6


def test_real_pg_lock_wait_is_bounded(pg_isolated_engine):
    from app.services.lead_service import _lock
    from sqlalchemy.exc import OperationalError
    import time
    p=LeadCreate(**{**BASE,"source_event_id":uuid.uuid4().hex})
    with Session(pg_isolated_engine) as holder:
        _lock(holder,"event",p.source_event_id)
        with Session(pg_isolated_engine) as waiter:
            start=time.monotonic()
            with pytest.raises(OperationalError):ingest_lead(waiter,p)
            assert 2.5 <= time.monotonic()-start < 5
            waiter.rollback()


def test_migration_preserves_historical_duplicate_ids(monkeypatch):
    name="test_lead_migration_"+uuid.uuid4().hex
    admin=create_engine(settings.sync_database_url,isolation_level="AUTOCOMMIT")
    with admin.connect() as db:db.execute(text("CREATE SCHEMA "+name))
    engine=create_engine(settings.sync_database_url,connect_args={"options":"-csearch_path="+name})
    monkeypatch.setenv("ALEMBIC_SCHEMA",name)
    config=Config("alembic.ini")
    try:
        command.upgrade(config,"005_reviews")
        originals=[]
        with Session(engine) as db:
            for i in (2,1):
                p=LeadCreate(source_event_id="legacy-"+str(i),name="Historical "+str(i),email="history@example.com")
                lead=Lead(id=str(i)*36,source_event_id=p.source_event_id,name=p.name,normalized_email=str(p.email),
                    payload_hash=compute_lead_canonical_hash(p),status="new",created_at=datetime(2025,1,1,tzinfo=timezone.utc))
                db.add(lead); originals.append((lead.id,p))
            db.commit()
            before=db.execute(text("SELECT id,md5(to_jsonb(t)::text) FROM leads t")).all()
        command.upgrade(config,"006_lead_intake")
        with Session(engine) as db:
            assert db.execute(text("SELECT id,md5(to_jsonb(t)::text) FROM leads t")).all()==before
            assert db.get(LeadIdentity,"history@example.com").lead_id=="1"*36
            for original_id,p in originals:
                result=ingest_lead(db,p)
                assert result.lead.id==original_id and result.duplicate_reason=="event"
            alias=LeadCreate(source_event_id="new-alias",name="No overwrite",email="history@example.com")
            result=ingest_lead(db,alias)
            assert result.lead.id=="1"*36 and result.duplicate_reason=="email"
            assert db.scalar(select(func.count(Lead.id)))==2
            assert db.execute(text("SELECT id,md5(to_jsonb(t)::text) FROM leads t")).all()==before
            db.add(LeadIdentity(normalized_email="history@example.com",lead_id="2"*36))
            with pytest.raises(IntegrityError):db.commit()
            db.rollback()
    finally:
        engine.dispose()
        with admin.connect() as db:db.execute(text("DROP SCHEMA "+name+" CASCADE"))
        admin.dispose()
