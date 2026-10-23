"""Focused security boundary tests; existing auth/model/race suites are retained."""
import asyncio
import json
import os
import subprocess
import sys
import uuid
import pytest
from sqlalchemy import select, func
from app.core.request_limits import RequestLimits, MAX_BODY_BYTES
from app.models.ticket import Ticket


def payload():
    return {"source_event_id": uuid.uuid4().hex, "subject": "Synthetic", "body": "Test"}


@pytest.mark.parametrize("raw", [b'{"private":"CANARY",', b'{"body":"\\xff"}', ("[" * 1500 + "]" * 1500).encode()])
def test_malformed_json_is_sanitized(client, db_session, raw):
    response = client.post("/api/tickets", content=raw, headers={"Content-Type": "application/json"})
    assert response.status_code == 422
    assert "CANARY" not in response.text and "Traceback" not in response.text
    assert db_session.scalar(select(func.count()).select_from(Ticket)) == 0


@pytest.mark.parametrize("declared", [None, "1", str(MAX_BODY_BYTES + 1)])
def test_actual_body_byte_limit_precedes_persistence(client, db_session, declared):
    value = {**payload(), "ignored": "x" * MAX_BODY_BYTES}
    headers = {"Content-Type": "application/json"}
    if declared is not None:
        headers["Content-Length"] = declared
    response = client.post("/api/tickets", content=json.dumps(value).encode(), headers=headers)
    assert response.status_code == 413 and response.headers["Cache-Control"] == "private, no-store"
    assert db_session.scalar(select(func.count()).select_from(Ticket)) == 0


def test_limit_inclusive_and_legacy_extra_ignore_preserved(client):
    value = payload()
    raw = json.dumps({**value, "ignored": ""}).encode()
    raw = json.dumps({**value, "ignored": "x" * (MAX_BODY_BYTES - len(raw))}).encode()
    assert len(raw) == MAX_BODY_BYTES
    response = client.post("/api/tickets", content=raw, headers={"Content-Type": "application/json"})
    assert response.status_code == 201
    assert response.headers["Cache-Control"] == "private, no-store"
    assert client.get("/api/tickets/" + response.json()["id"]).headers["Cache-Control"] == "private, no-store"


def test_chunked_request_stops_at_limit():
    called, sent = [], []
    async def downstream(*args):
        called.append(True)
    events = iter([{"type": "http.request", "body": b"x" * 32768, "more_body": True},
                   {"type": "http.request", "body": b"x" * 32769, "more_body": True}])
    async def receive():
        return next(events)
    async def send(event):
        sent.append(event)
    asyncio.run(RequestLimits(downstream)({"type": "http", "method": "POST", "path": "/api/tickets",
                                         "headers": []}, receive, send))
    assert not called and sent[0]["status"] == 413


def test_sql_metacharacters_are_values_and_query_types_checked(client):
    assert client.get("/api/tickets?offset=0%20UNION%20SELECT%201").status_code == 422
    assert client.get("/api/tickets/%27%3BDROP%20TABLE%20tickets%3B--").status_code == 404
    value = payload()
    value["source_event_id"] = "'; DROP TABLE tickets;--"
    first = client.post("/api/tickets", json=value)
    assert first.status_code == 201
    assert client.post("/api/tickets", json=value).json()["id"] == first.json()["id"]


def test_memory_sqlite_startup_compatibility():
    env = {**os.environ, "DATABASE_URL": "sqlite:///:memory:"}
    result = subprocess.run([sys.executable, "-c",
        "from app.core.database import engine;from sqlalchemy import text;"
        "c=engine.connect();assert c.scalar(text('SELECT 1'))==1;c.close()"],
        env=env, capture_output=True, text=True, timeout=10)
    assert result.returncode == 0

def test_private_pytest_temporary_root(tmp_path_factory):
    root = tmp_path_factory.getbasetemp()
    assert root.stat().st_mode & 0o777 == 0o700
    assert root.stat().st_uid == os.getuid()
