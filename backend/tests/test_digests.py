"""Deterministic reporting, real PostgreSQL races and additive migration proof."""
import json
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta, timezone
import pytest
from alembic import command
from alembic.config import Config
from pydantic import ValidationError
from sqlalchemy import create_engine, select, func, text
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import Session
from app.core.config import settings, Settings
from app.models.ticket import Ticket
from app.models.lead import Lead
from app.models.lead_intake import LeadIdentity
from app.models.audit_event import AuditEvent
from app.models.review import Review
from app.models.ticket_enrichment import TicketEnrichment as E
from app.models.digest import DailyDigest
from app.schemas.digest import DigestMetrics
from app.services import digest_service as service
from tests.test_reviews import reviewer  # noqa: F401
from tests.test_postgres_integration import pg_isolated_engine  # noqa: F401

UTC=timezone.utc
DAY=date(2025,12,31)
NOW=datetime(2026,1,2,0,0,tzinfo=UTC)


@pytest.mark.parametrize("day,zone,start,end",[
 ("2025-12-31","Asia/Kolkata","2025-12-30T18:30:00+00:00","2025-12-31T18:30:00+00:00"),
 ("2026-01-01","Asia/Kolkata","2025-12-31T18:30:00+00:00","2026-01-01T18:30:00+00:00"),
 ("2024-02-29","UTC","2024-02-29T00:00:00+00:00","2024-03-01T00:00:00+00:00"),
 ("2025-03-09","America/New_York","2025-03-09T05:00:00+00:00","2025-03-10T04:00:00+00:00"),
 ("2025-11-02","America/New_York","2025-11-02T04:00:00+00:00","2025-11-03T05:00:00+00:00"),
])
def test_aware_calendar_boundaries(day,zone,start,end):
    _,_,a,b=service.reporting_period(date.fromisoformat(day),zone,now=NOW)
    assert a.isoformat()==start and b.isoformat()==end


def test_previous_completed_day_across_local_midnight():
    for instant,expected in [("2026-01-01T18:29:59+00:00",date(2025,12,31)),("2026-01-01T18:30:00+00:00",date(2026,1,1))]:
        assert service.reporting_period(zone="Asia/Kolkata",now=datetime.fromisoformat(instant))[0]==expected
    with pytest.raises(ValueError):service.reporting_period(now=datetime(2026,1,2))
    with pytest.raises(ValidationError):Settings(_env_file=None,DIGEST_TIMEZONE="../unsafe")


@pytest.mark.parametrize("day",[date(1999,12,31),date(2026,1,2),date(2026,1,3)])
def test_reject_incomplete_or_unsupported_day(day):
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as exc:service.reporting_period(day,zone="UTC",now=NOW)
    assert exc.value.status_code==422


@pytest.mark.parametrize("method,path,body",[
 ("get","/api/digests",None),("get","/api/digests/unknown",None),
 ("post","/api/digests/generate",{"reporting_date":"2025-12-31"}),
])
def test_authentication_required(client,method,path,body):
    response=getattr(client,method)(path,**({"json":body} if body else {}))
    assert response.status_code==401 and response.headers["Cache-Control"]=="private, no-store"


@pytest.mark.parametrize("value",[123,True,[],{},"2025-13-01","2025-02-30","20251231","2025-12-31T00:00:00Z","PRIVATE_DATE_CANARY"])
def test_invalid_generation_date(client,reviewer,value):
    response=client.post("/api/digests/generate",json={"reporting_date":value},headers=reviewer)
    assert response.status_code==422
    assert "PRIVATE_DATE_CANARY" not in response.text and '"input"' not in response.text


def test_service_credential_is_generation_only(client,monkeypatch):
    monkeypatch.setattr(settings,"DIGEST_SERVICE_KEY","synthetic-digest-service-key-"*3)
    key={"X-FlowForge-Digest-Key":settings.DIGEST_SERVICE_KEY}
    assert client.post("/api/digests/generate",json={"reporting_date":"2025-12-31"},headers={"X-FlowForge-Digest-Key":"wrong"}).status_code==401
    response=client.post("/api/digests/generate",json={"reporting_date":"2025-12-31"},headers=key)
    assert response.status_code==201
    assert client.get("/api/digests",headers=key).status_code==401
    assert client.get("/api/reviews",headers=key).status_code==401
    assert client.post("/api/reviewer/login",json={"username":"x","password":settings.DIGEST_SERVICE_KEY}).status_code==401


def seed(db):
    _,_,start,end=service.reporting_period(DAY)
    tickets=[]
    for i,at in enumerate([start-timedelta(microseconds=1),start,start+timedelta(hours=1),end,start-timedelta(days=10)]):
        t=Ticket(id=str(uuid.uuid4()),source_event_id="metric-"+str(i),subject="CUSTOMER_SUBJECT_CANARY",body="CUSTOMER_BODY_CANARY",payload_hash="a"*64,created_at=at,status="received",category="unknown")
        db.add(t);tickets.append(t)
    db.flush()
    old=Lead(id=str(uuid.uuid4()),source_event_id="legacy-old",name="CUSTOMER_NAME_CANARY",normalized_email="legacy@example.com",payload_hash="a"*64,status="new",created_at=start-timedelta(days=1))
    duplicate=Lead(id=str(uuid.uuid4()),source_event_id="legacy-dup",name="CUSTOMER_NAME_CANARY",normalized_email="legacy@example.com",payload_hash="b"*64,status="new",created_at=start)
    fresh=Lead(id=str(uuid.uuid4()),source_event_id="fresh",name="CUSTOMER_NAME_CANARY",normalized_email="fresh@example.com",payload_hash="c"*64,status="new",created_at=start)
    db.add_all([old,duplicate,fresh]);db.flush()
    db.add_all([LeadIdentity(normalized_email=old.normalized_email,lead_id=old.id),LeadIdentity(normalized_email=fresh.normalized_email,lead_id=fresh.id)])
    for kind,detail in [
      ("lead_created",{}),("lead_created",{}),
      ("lead_duplicate_received",{"duplicate_reason":"event"}),
      ("lead_duplicate_received",{"action":"concurrent_duplicate_resolved"}),
      ("lead_duplicate_received",{"duplicate_reason":"email"}),
      ("lead_duplicate_received",{"action":"unknown-legacy"}),
      ("lead_conflict_received",{}),
    ]:
        db.add(AuditEvent(entity_id=fresh.id,event_type=kind,actor="test",safe_detail=detail,timestamp=start))
    db.add(AuditEvent(entity_id=fresh.id,event_type="lead_created",actor="test",safe_detail={},timestamp=end))
    def enrichment(ticket,status,order,completed,review=None,decided=None):
        e=E(id=str(uuid.uuid4()),ticket_id=ticket.id,model="synthetic:"+str(order),model_digest="a"*64,prompt_version="v1",schema_version="1",status=status,
            category="billing" if status=="succeeded" else "unknown",priority="medium" if status=="succeeded" else "unknown",
            reason="MODEL_RESPONSE_CANARY",diagnostic_code="test",attempts=1,lease_token=str(uuid.uuid4()) if status=="processing" else None,
            started_at=start+timedelta(seconds=order),completed_at=completed)
        db.add(e);db.flush()
        if review:
            db.add(Review(enrichment_id=e.id,status=review,revision=1,
                reviewer="test-reviewer" if decided else None,note="Synthetic rejection" if review=="rejected" else None,
                decided_at=decided,created_at=start,updated_at=start))
    enrichment(tickets[1],"succeeded",1,start,"pending")
    enrichment(tickets[1],"needs_review",2,start+timedelta(hours=1),"attention")
    enrichment(tickets[2],"succeeded",3,start+timedelta(hours=1),"approved",start)
    enrichment(tickets[0],"unavailable",4,end-timedelta(microseconds=1),"attention")
    enrichment(tickets[3],"succeeded",5,end,"pending")
    enrichment(tickets[4],"succeeded",6,start-timedelta(seconds=1),"rejected",end-timedelta(microseconds=1))
    enrichment(tickets[4],"processing",7,None)
    db.commit()
    return start,end


def test_exact_aggregates_and_immutable_snapshots(client,db_session,reviewer):
    seed(db_session)
    response=client.post("/api/digests/generate",json={"reporting_date":DAY.isoformat()},headers=reviewer)
    assert response.status_code==201
    value=response.json();a=value["metrics"]["activity"]
    assert a=={"tickets_created":2,"canonical_leads_created":1,
        "lead_requests_observed":{"created_records":2,"event_replays":2,"email_matches":1,"legacy_duplicates":1},
        "enrichment_results_completed":{"succeeded":2,"needs_review":1,"unavailable":1},
        "review_decisions":{"approved":1,"rejected":1}}
    assert value["metrics"]["snapshot"]=={"pending_reviews":1,"attention_reviews":2,"processing_enrichments":1}
    assert all(canary not in json.dumps(value) for canary in ("CUSTOMER_","MODEL_RESPONSE_","@example.com"))
    start,end=service.reporting_period(DAY)[2:]
    db_session.add(Ticket(source_event_id="late-arrival",subject="Synthetic",body="Synthetic",payload_hash="d"*64,created_at=start))
    db_session.commit()
    repeat=client.post("/api/digests/generate",json={"reporting_date":DAY.isoformat()},headers=reviewer)
    assert repeat.status_code==200 and repeat.json()["duplicate"] is True
    for field in ("id","generated_at","metrics","period_start","period_end"):
        assert repeat.json()[field]==value[field]
    assert client.get("/api/digests/"+value["id"],headers=reviewer).json()["metrics"]==value["metrics"]
    events=db_session.scalars(select(AuditEvent).where(AuditEvent.entity_id==value["id"])).all()
    assert {e.event_type for e in events}=={"digest_generated","digest_replayed"}


def test_empty_day_and_manual_backfill(client,db_session,reviewer):
    response=client.post("/api/digests/generate",json={"reporting_date":"2020-01-01"},headers=reviewer)
    assert response.status_code==201
    assert all(value==0 for group in response.json()["metrics"]["activity"].values() for value in (group.values() if isinstance(group,dict) else [group]))
    assert client.post("/api/digests/generate",json={},headers=reviewer).status_code==201
    page=client.get("/api/digests?limit=1",headers=reviewer).json()
    assert page["total"]==2 and len(page["items"])==1
    assert client.get("/api/digests?reporting_date=2020-01-01",headers=reviewer).json()["total"]==1
    assert client.get("/api/digests/missing",headers=reviewer).status_code==404
    assert client.get("/api/digests?limit=51",headers=reviewer).status_code==422
    assert client.post("/api/digests/generate",json={"reporting_date":"2020-01-01","refresh":True},headers=reviewer).status_code==422


def test_database_failure_does_not_persist_fake_zeros(client,db_session,reviewer,monkeypatch):
    def unavailable(*a):raise OperationalError("PRIVATE_DATABASE_CANARY",{},Exception("PRIVATE_DATABASE_CANARY"))
    monkeypatch.setattr(service,"calculate_metrics",unavailable)
    response=client.post("/api/digests/generate",json={"reporting_date":"2020-01-01"},headers=reviewer)
    assert response.status_code==503 and "PRIVATE_DATABASE_CANARY" not in response.text
    assert db_session.scalar(select(func.count(DailyDigest.id)))==0


def test_strict_metric_validation():
    with pytest.raises(ValidationError):DigestMetrics.model_validate({"activity":{},"snapshot":{}})


def test_real_postgres_digest_concurrency(pg_isolated_engine):
    barrier=threading.Barrier(6);day=date(2019,6,15)
    def worker(i):
        with Session(pg_isolated_engine) as db:
            barrier.wait(timeout=10)
            report,duplicate=service.generate_digest(db,day,correlation_id="digest-race-"+str(i),execution_id="exec-race-"+str(i))
            assert report.period_start.tzinfo is not None and report.generated_at.tzinfo is not None
            return report.id,duplicate
    with ThreadPoolExecutor(max_workers=6) as pool:results=list(pool.map(worker,range(6)))
    assert len({r[0] for r in results})==1 and sum(not r[1] for r in results)==1
    with Session(pg_isolated_engine) as db:
        report=db.get(DailyDigest,results[0][0])
        assert db.scalar(select(func.count(AuditEvent.id)).where(AuditEvent.entity_id==report.id))==6
        db.add(DailyDigest(reporting_date=report.reporting_date,reporting_timezone=report.reporting_timezone,
            period_start=report.period_start,period_end=report.period_end,generated_at=report.generated_at,metrics=report.metrics,
            metrics_version=1,status="ready",correlation_id="duplicate"))
        with pytest.raises(IntegrityError):db.commit()
        db.rollback()


def test_real_postgres_metric_parity(pg_isolated_engine):
    with Session(pg_isolated_engine) as db:
        start,end=seed(db)
        result,at=service.calculate_metrics(db,start,end)
        assert result.activity.tickets_created==2 and result.activity.canonical_leads_created==1
        assert result.activity.lead_requests_observed.event_replays==2
        assert result.activity.lead_requests_observed.email_matches==1
        assert result.snapshot.pending_reviews==1 and at.tzinfo is not None


def test_additive_digest_migration(monkeypatch):
    name="test_digest_migration_"+uuid.uuid4().hex
    admin=create_engine(settings.sync_database_url,isolation_level="AUTOCOMMIT")
    with admin.connect() as c:c.execute(text("CREATE SCHEMA "+name))
    engine=create_engine(settings.sync_database_url,connect_args={"options":"-csearch_path="+name})
    monkeypatch.setenv("ALEMBIC_SCHEMA",name);config=Config("alembic.ini")
    try:
        command.upgrade(config,"006_lead_intake")
        with Session(engine) as db:
            db.add(Ticket(source_event_id="preserve-digest-migration",subject="Preserve",body="Preserve",payload_hash="a"*64))
            db.commit()
            before=db.execute(text("SELECT id,md5(to_jsonb(t)::text) FROM tickets t")).all()
        command.upgrade(config,"007_daily_digests")
        with Session(engine) as db:
            assert db.execute(text("SELECT id,md5(to_jsonb(t)::text) FROM tickets t")).all()==before
            assert db.scalar(select(func.count(DailyDigest.id)))==0
            row,_=service.generate_digest(db,date(2019,1,1))
            assert row.reporting_timezone=="Asia/Kolkata"
    finally:
        engine.dispose()
        with admin.connect() as c:c.execute(text("DROP SCHEMA "+name+" CASCADE"))
        admin.dispose()


def test_schedule_export_is_scoped_and_private():
    # The export is mounted read-only in this specific test invocation.
    from pathlib import Path
    path=Path("/workspace/workflows/daily_operations_digest.json")
    if not path.exists():
        # Normal backend images include a synthetic copy in test fixtures.
        path=Path("tests/fixtures/daily_operations_digest.json")
    w=json.loads(path.read_text())
    assert w["id"]=="FlowForgeDailyDigest01" and len(w["nodes"])==5
    assert w["settings"]["timezone"]=="Asia/Kolkata"
    assert w["settings"]["saveDataSuccessExecution"]==w["settings"]["saveDataErrorExecution"]=="none"
    schedule=w["nodes"][0]
    assert schedule["parameters"]["rule"]["interval"][0]["expression"]=="0 9 * * *"
    assert schedule["parameters"].get("misfirePolicy","skip")=="skip"
    assert "minus({days: 1})" in w["nodes"][1]["parameters"]["jsonOutput"]
    assert w["nodes"][2]["credentials"]["httpHeaderAuth"]["id"]=="FlowForgeDigestApi01"
    assert all(n["type"]!="n8n-nodes-base.code" for n in w["nodes"])
    assert settings.DIGEST_SERVICE_KEY not in json.dumps(w) if settings.DIGEST_SERVICE_KEY else True
