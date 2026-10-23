#!/usr/bin/env python3
"""Live disposable restart tests. Ollama is a stub; production is untouched."""
import argparse
import concurrent.futures
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import http.client
import json
import os
from pathlib import Path
import secrets
import subprocess
import tempfile
import time
import urllib.error
import urllib.request
import uuid

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=ROOT / "docs/evaluation/implementation-08-recovery.json")
    args = parser.parse_args()
    tag = "ff-recovery-" + uuid.uuid4().hex[:10]
    names = {s: tag + "-" + s for s in ("postgres", "backend", "n8n", "frontend", "ollama")}
    started, checks = [], []
    began = time.monotonic()
    # Retain isolated synthetic database files outside Git, with private parent.
    # No production or named Docker volume is attached to this harness.
    folder = Path(tempfile.mkdtemp(prefix=tag + "-"))
    folder.chmod(0o700)
    (folder / "pg").mkdir()
    (folder / "n8n").mkdir(mode=0o700)
    assert os.getuid() == 1000, "Run as the local WSL developer"

    def docker(*cmd, check=True, **kw):
        return subprocess.run(["docker", *cmd], cwd=ROOT, check=check, capture_output=True,
                              text=True, timeout=180, **kw)

    def check(ok, label):
        assert ok, label
        checks.append(label)
        print("PASS:", label, flush=True)

    def port(service, number):
        info = json.loads(docker("inspect", names[service]).stdout)[0]
        return int(info["NetworkSettings"]["Ports"][str(number) + "/tcp"][0]["HostPort"])

    def request(url, body=None, headers=None, timeout=15):
        req = urllib.request.Request(url, data=None if body is None else json.dumps(body).encode(),
                                     headers={"Content-Type": "application/json", **(headers or {})})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as response:
                raw = response.read()
                value = json.loads(raw) if "application/json" in response.headers.get("Content-Type", "") else raw.decode()
                return response.status, value, response.headers
        except urllib.error.HTTPError as error:
            return error.code, json.load(error), error.headers

    def wait(url, limit=90):
        deadline = time.monotonic() + limit
        while time.monotonic() < deadline:
            try:
                if request(url, timeout=2)[0] == 200:
                    return
            except (OSError, http.client.HTTPException):
                pass
            time.sleep(.3)
        raise AssertionError("Isolated service failed bounded readiness")

    def service(name, *cmd):
        docker("run", "-d", "--name", names[name], "--label", "flowforge.recovery-test=" + tag,
               "--network", tag, "--network-alias", name, *cmd)
        started.append(name)

    password, db_password = secrets.token_urlsafe(24), secrets.token_urlsafe(24)
    key = secrets.token_urlsafe(32)
    encoded = docker("run", "--rm", "-i", "--network", "none", "flowforge-ai-backend",
                     "python", "-c", "import sys;from pwdlib import PasswordHash;print(PasswordHash.recommended().hash(sys.stdin.read()))",
                     input=password).stdout.strip()
    env = folder / "backend.env"
    env.write_text("\n".join([
        "DATABASE_URL=postgresql+psycopg://fixture:" + db_password + "@postgres:5432/fixture",
        "REVIEWER_USERNAME=fixture", "REVIEWER_PASSWORD_HASH=" + encoded,
        "REVIEWER_SESSION_SECRET=" + secrets.token_urlsafe(48),
        "DIGEST_SERVICE_KEY=" + key, "DIGEST_TIMEZONE=Asia/Kolkata",
        "OLLAMA_BASE_URL=http://ollama:11434", "OLLAMA_TIMEOUT_SECONDS=25",
        "ENABLE_FAILURE_SIMULATION=false"]))
    env.chmod(0o600)
    pg_env = folder / "postgres.env"
    pg_env.write_text("POSTGRES_USER=fixture\nPOSTGRES_DB=fixture\nPOSTGRES_PASSWORD=" + db_password)
    pg_env.chmod(0o600)
    definitions = [json.loads((ROOT / "workflows" / f).read_text()) for f in
                   ("support_ticket_intake.json", "lead_intake.json", "daily_operations_digest.json")]
    (folder / "workflows.json").write_text(json.dumps(definitions))
    credential = folder / "credential.json"
    credential.write_text(json.dumps([{"id": "FlowForgeDigestApi01", "name": "FlowForge Digest Service",
                "type": "httpHeaderAuth", "data": {"name": "X-FlowForge-Digest-Key", "value": key}}]))
    credential.chmod(0o600)
    docker("network", "create", "--label", "flowforge.recovery-test=" + tag, tag)
    try:
        service("postgres", "--env-file", str(pg_env), "--mount",
                f"type=bind,src={folder / 'pg'},dst=/var/lib/postgresql/data", "postgres:17-alpine")
        for _ in range(100):
            if (docker("exec", names["postgres"], "cat", "/proc/1/comm", check=False).stdout.strip() == "postgres"
                    and docker("exec", names["postgres"], "pg_isready", "-U", "fixture", check=False).returncode == 0):
                break
            time.sleep(.3)
        check(docker("exec", names["postgres"], "pg_isready", "-U", "fixture").returncode == 0,
              "Fresh isolated PostgreSQL ready")
        docker("run", "--rm", "--network", tag, "--env-file", str(env), "flowforge-ai-backend", "alembic", "upgrade", "head")
        service("ollama", "-p", "127.0.0.1::11434", "--mount",
                f"type=bind,src={ROOT / 'scripts/recovery_fixture.py'},dst=/fixture.py,readonly",
                "flowforge-ai-backend", "python", "/fixture.py")
        service("backend", "-p", "127.0.0.1::8001", "--env-file", str(env), "flowforge-ai-backend")
        backend = "http://127.0.0.1:" + str(port("backend", 8001))
        wait(backend + "/ready")
        service("frontend", "-p", "127.0.0.1::3000", "-e", "BACKEND_URL=http://backend:8001",
                "-e", "DASHBOARD_ORIGIN=http://localhost:3000", "-e", "COOKIE_SECURE=false",
                "-e", "NEXT_TELEMETRY_DISABLED=1", "flowforge-ai-frontend")
        frontend = "http://127.0.0.1:" + str(port("frontend", 3000))
        wait(frontend + "/login")
        service("n8n", "-p", "127.0.0.1::5678", "--mount",
                f"type=bind,src={folder / 'n8n'},dst=/home/node/.n8n", "--mount",
                f"type=bind,src={folder},dst=/fixture,readonly",
                "-e", "N8N_DIAGNOSTICS_ENABLED=false", "-e", "N8N_SECURE_COOKIE=false",
                "-e", "EXECUTIONS_DATA_PRUNE=false", "-e", "EXECUTIONS_DATA_SAVE_ON_SUCCESS=none",
                "-e", "EXECUTIONS_DATA_SAVE_ON_ERROR=none", "-e", "N8N_USE_WORKFLOW_PUBLICATION_SERVICE=false",
                "--entrypoint", "/bin/sh", "n8nio/n8n:2.43.8", "-c",
                "if [ ! -e /home/node/.n8n/imported ]; then n8n import:workflow --input=/fixture/workflows.json && "
                "n8n import:credentials --input=/fixture/credential.json && "
                "n8n publish:workflow --id=FlowForgeSupportIntake01 && "
                "n8n publish:workflow --id=FlowForgeLeadIntake01 && "
                "n8n publish:workflow --id=FlowForgeDailyDigest01 && "
                "touch /home/node/.n8n/imported; fi; exec n8n start")
        n8n = "http://127.0.0.1:" + str(port("n8n", 5678))
        wait(n8n + "/healthz/readiness", limit=150)

        def sql(query):
            return docker("exec", names["postgres"], "psql", "-U", "fixture", "-d", "fixture", "-Atc", query).stdout.strip()

        def login():
            creds = {"username": "fixture", "password": password}
            token = request(backend + "/api/reviewer/login", creds)[1]["token"]
            result = request(frontend + "/api/auth/login", creds, {"Origin": "http://localhost:3000"})
            cookie = result[2].get("Set-Cookie").split(";")[0]
            return {"Authorization": "Bearer " + token}, {"Cookie": cookie, "Origin": "http://localhost:3000"}

        auth, browser = login()
        check(request(backend + "/api/reviewer/dependencies", headers=auth)[1]["ollama"] == "available",
              "Pinned model metadata diagnostic (stub)")
        check(sql("SELECT version_num FROM alembic_version") == "007_daily_digests", "Clean migration startup")
        bounds = docker("exec", names["backend"], "python", "-c", """
import time
from sqlalchemy import text
from sqlalchemy.exc import OperationalError, TimeoutError
from app.core.database import engine
with engine.connect() as conn:
    assert conn.scalar(text('SHOW statement_timeout')) == '5s'
    assert conn.scalar(text('SHOW lock_timeout')) == '3s'
    conn.commit()
    began = time.monotonic()
    try:
        conn.execute(text('SELECT pg_sleep(15)'))
        raise AssertionError('Statement deadline not enforced')
    except OperationalError:
        assert 4 <= time.monotonic() - began < 8
        conn.rollback()
        assert conn.scalar(text('SELECT 1')) == 1
print('statement_recovered')
held = [engine.connect() for _ in range(15)]
try:
    began = time.monotonic()
    try:
        engine.connect()
        raise AssertionError('Pool deadline not enforced')
    except TimeoutError:
        assert 1.5 <= time.monotonic() - began < 4
finally:
    for connection in held:
        connection.close()
print('pool_bounded')
from unittest.mock import patch
from fastapi.testclient import TestClient
from app.main import app
def interrupt(db, **kwargs):
    pid = db.scalar(text('SELECT pg_backend_pid()'))
    with engine.connect() as other:
        assert other.scalar(text('SELECT pg_terminate_backend(:pid)'), {'pid': pid})
    db.execute(text('SELECT 1'))
body = {'source_event_id': 'isolated-mid-transaction', 'subject': 'Synthetic', 'body': 'Preserve atomicity'}
with TestClient(app) as client:
    with patch('app.services.ticket_service.record_audit_event', interrupt):
        response = client.post('/api/tickets', json=body)
    assert response.status_code == 503
    with engine.connect() as conn:
        assert conn.scalar(text("SELECT count(*) FROM tickets WHERE source_event_id='isolated-mid-transaction'")) == 0
        assert conn.scalar(text('SELECT count(*) FROM audit_events')) == 0
    assert client.post('/api/tickets', json=body).status_code == 201
print('mid_transaction_recovered')
""").stdout
        check("statement_recovered" in bounds, "Server statement timeout and transaction recovery enforced")
        check("pool_bounded" in bounds, "Actual exhausted database pool bounded to two seconds")
        check("mid_transaction_recovered" in bounds, "Terminated PostgreSQL session rolls back flushed ticket and audit; same event recovers")
        support, lead_url = n8n + "/webhook/support-ticket-intake", n8n + "/webhook/lead-intake"
        ticket_body = {"source_event_id": tag + "-ticket", "subject": "Synthetic refund", "body": "Duplicate charge"}
        for _ in range(100):
            code, ticket, _ = request(support, ticket_body)
            if code in (200, 201):
                break
            time.sleep(.3)
        check(code == 201, "Published support webhook accepts original path: " + str(code) + " " + str(ticket.get("outcome")))
        ticket_id = ticket["ticket_id"]
        enrichment_url = backend + "/api/tickets/" + ticket_id + "/enrichment"
        for _ in range(100):
            code, result, _ = request(enrichment_url)
            if code == 200 and result["status"] == "succeeded":
                break
            time.sleep(.2)
        check(code == 200 and result["status"] == "succeeded", "Post-response advisory result durable")
        lead_body = {"source_event_id": tag + "-lead", "name": "Synthetic recovery", "email": tag + "@example.com"}
        code, lead, _ = request(lead_url, lead_body)
        check(code == 201, "Published lead webhook accepts original path")
        review = request(backend + "/api/reviews?ticket_id=" + ticket_id, headers=auth)[1]["items"][0]
        check(review["status"] == "pending", "Pending review persists independently of browser")
        pending_ticket = request(backend + "/api/tickets", {**ticket_body, "source_event_id": tag + "-pending"})[1]
        request(backend + "/api/tickets/" + pending_ticket["id"] + "/enrich", {})
        pending_before = request(backend + "/api/reviews?ticket_id=" + pending_ticket["id"], headers=auth)[1]["items"][0]
        decision = {"enrichment_id": review["enrichment_id"], "expected_revision": review["revision"], "note": None}
        lost_url = "http://127.0.0.1:" + str(port("ollama", 11434)) + "/lose/api/reviews/" + review["id"] + "/approve"
        lost = False
        try:
            request(lost_url, decision, browser)
        except (OSError, http.client.HTTPException):
            lost = True
        saved = request(backend + "/api/reviews/" + review["id"], headers=auth)[1]
        check(lost and saved["status"] == "approved", "Review committed although browser received no response")
        final_time = saved["decided_at"]
        docker("restart", "-t", "3", names["frontend"])
        frontend = "http://127.0.0.1:" + str(port("frontend", 3000))
        wait(frontend + "/login")
        check("Welcome back" in request(frontend + "/reviews")[1], "Frontend restart still requires login")
        auth, browser = login()
        check("Synthetic refund" in request(frontend + "/history", headers=browser)[1], "Relogin and refresh recover decision history")
        pending_after = request(backend + "/api/reviews/" + pending_before["id"], headers=auth)[1]
        check(pending_after["status"] == "pending" and pending_after["revision"] == pending_before["revision"] and pending_before["id"] in request(frontend + "/reviews", headers=browser)[1], "Pending review survives frontend restart refresh and relogin")
        code, replay, _ = request(frontend + "/api/reviews/" + review["id"] + "/approve", decision, browser)
        check(code == 200 and replay["duplicate"] and request(backend + "/api/reviews/" + review["id"], headers=auth)[1]["decided_at"] == final_time, "Review replay preserves final timestamp")
        check(request(backend + "/api/reviews/" + review["id"] + "/approve", decision)[0] == 401, "Backend authentication authoritative")
        check(sql("SELECT count(*) FROM audit_events WHERE event_type='review_approved'") == "1", "One final decision audit after response loss")
        before = sql("SELECT count(*) FROM tickets") + ":" + sql("SELECT count(*) FROM audit_events")
        docker("stop", "-t", "3", names["postgres"])
        start = time.monotonic()
        code, value, _ = request(backend + "/ready", timeout=12)
        check(code == 503 and time.monotonic() - start < 10, "Database outage readiness bounded and unavailable")
        check(request(backend + "/health")[0] == 200, "Liveness survives database outage")
        failed_body = {**ticket_body, "source_event_id": tag + "-db-outage"}
        code, value, headers = request(backend + "/api/tickets", failed_body, timeout=12)
        check(code == 503 and headers.get("Retry-After") == "2" and db_password not in json.dumps(value), "Database outage sanitized retryable error")
        docker("start", names["postgres"])
        wait(backend + "/ready")
        after = sql("SELECT count(*) FROM tickets") + ":" + sql("SELECT count(*) FROM audit_events")
        check(before == after, "Database restart preserves rows and commits no partial intake")
        code, healed, _ = request(backend + "/api/tickets", failed_body)
        check(code == 201, "Existing backend pool recovers after database restart")
        check(request(backend + "/api/tickets", failed_body)[1]["id"] == healed["id"], "Recovered intake replay safe")
        docker("stop", "-t", "2", names["ollama"])
        code, offline, _ = request(support, {**ticket_body, "source_event_id": tag + "-offline"})
        check(code == 201, "Ticket webhook accepted with optional model offline")
        offline_url = backend + "/api/tickets/" + offline["ticket_id"] + "/enrichment"
        for _ in range(120):
            code, unavailable, _ = request(offline_url)
            if code == 200 and unavailable["status"] == "unavailable":
                break
            time.sleep(.2)
        check(code == 200 and unavailable["status"] == "unavailable", "Outage explicitly persisted")
        enrich_url = offline_url.rsplit("/", 1)[0] + "/enrich"
        check(request(enrich_url, {})[1]["attempts"] == 1, "Ordinary replay does not retry inference")
        check(request(backend + "/ready")[0] == 200, "Optional AI outage leaves readiness available")
        check(request(backend + "/api/reviewer/dependencies", headers=auth)[1]["ollama"] == "unavailable", "Optional outage observable")
        docker("start", names["ollama"])
        wait("http://127.0.0.1:" + str(port("ollama", 11434)) + "/health")
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
            results = list(pool.map(lambda _: request(enrich_url + "?retry_unavailable=true", {}), range(4)))
        current = request(offline_url)[1]
        check(current["status"] == "succeeded" and current["attempts"] == 2 and all(x[1]["id"] == unavailable["id"] for x in results), "Concurrent recovery claims one extra inference attempt")
        interrupted = request(backend + "/api/tickets", {**ticket_body, "source_event_id": tag + "-interrupted", "body": "INTERRUPT_FIXTURE"})[1]
        interrupt_url = backend + "/api/tickets/" + interrupted["id"] + "/enrich"
        executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
        future = executor.submit(request, interrupt_url, {}, None, 35)
        lease_started = time.monotonic()
        try:
            for _ in range(100):
                code, claim, _ = request(interrupt_url.rsplit("/", 1)[0] + "/enrichment")
                if code == 200 and claim["status"] == "processing":
                    break
                time.sleep(.1)
            check(code == 200 and claim["status"] == "processing", "In-flight claim committed before inference")
            docker("restart", "-t", "1", names["backend"])
            backend = "http://127.0.0.1:" + str(port("backend", 8001))
            interrupt_url = backend + "/api/tickets/" + interrupted["id"] + "/enrich"
            wait(backend + "/ready")
            try:
                future.result(timeout=35)
            except (OSError, http.client.HTTPException):
                pass
        finally:
            executor.shutdown(wait=True)
        check(request(backend + "/api/tickets/" + interrupted["id"])[0] == 200, "Backend interruption preserves original ticket")
        check(request(interrupt_url, {})[0] == 202, "Unexpired interrupted claim cannot be stolen")
        def export():
            docker("exec", names["n8n"], "n8n", "export:workflow", "--all", "--output=/tmp/proof.json")
            return json.loads(docker("exec", names["n8n"], "cat", "/tmp/proof.json").stdout)
        original_exports = export()
        docker("restart", "-t", "3", names["n8n"])
        n8n = "http://127.0.0.1:" + str(port("n8n", 5678))
        support, lead_url = n8n + "/webhook/support-ticket-intake", n8n + "/webhook/lead-intake"
        wait(n8n + "/healthz/readiness")
        restarted_exports = export()
        check(original_exports == restarted_exports, "Workflow definitions and publication survive n8n restart")
        check(all(any(w["id"] == src["id"] and w["active"] and all(w[k] == v for k, v in src.items()) for w in restarted_exports) for src in definitions), "Restarted published workflows match source exports")
        check(request(support, ticket_body)[1]["ticket_id"] == ticket_id, "Support replay after n8n restart")
        check(request(lead_url, lead_body)[1]["lead_id"] == lead["lead_id"], "Lead replay after n8n restart")
        check(request(backend + "/api/reviews/" + review["id"], headers=auth)[1]["decided_at"] == final_time, "Review decision survives all component restarts")
        check(sql("SELECT count(*) FROM daily_digests") == "0", "Scheduler restart does not automatically backfill history")
        # Simulate the narrow crash window after ticket commit but before n8n's
        # enrichment HTTP node: store directly, then deliver its identical event.
        gap_body = {**ticket_body, "source_event_id": tag + "-dispatch-gap"}
        gap = request(backend + "/api/tickets", gap_body)[1]
        check(request(support, gap_body)[1]["ticket_id"] == gap["id"], "Committed ticket replay resolves post-response dispatch gap")
        gap_url = backend + "/api/tickets/" + gap["id"]
        check(request(gap_url + "/enrichment")[0] == 404, "Duplicate branch does not silently dispatch missing inference")
        check(request(gap_url + "/enrich", {})[0] == 201, "Explicit operator request recovers missing enrichment")
        yesterday = (datetime.now(ZoneInfo("Asia/Kolkata")).date() - timedelta(days=1)).isoformat()
        code, digest, _ = request(backend + "/api/digests/generate", {}, auth)
        check(code == 201 and digest["reporting_date"] == yesterday, "Manual missed-day recovery uses configured timezone")
        saved_digest = {k: v for k, v in digest.items() if k != "duplicate"}
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
            results = list(pool.map(lambda i: request(backend + "/api/digests/generate", {"reporting_date": yesterday}, auth if i % 2 else {"X-FlowForge-Digest-Key": key}), range(4)))
        check(all(x[0] == 200 and x[1]["duplicate"] and {k: v for k, v in x[1].items() if k != "duplicate"} == saved_digest for x in results), "Concurrent scheduled-equivalent and manual calls preserve frozen snapshot")
        check(request(backend + "/api/digests/generate", {"reporting_date": "2000-01-01"}, auth)[0] == 201, "Historical backfill requires an explicit date")
        while time.monotonic() - lease_started < 122:
            time.sleep(min(1, 122 - (time.monotonic() - lease_started)))
        code, expired, _ = request(interrupt_url, {})
        check(code == 503 and expired["diagnostic_code"] == "lease_expired" and expired["attempts"] == 1, "Actual lease expires unavailable without automatic retry")
        attention = request(backend + "/api/reviews?ticket_id=" + interrupted["id"], headers=auth)[1]["items"][0]
        check(attention["status"] == "attention", "Interrupted claim visible in attention queue")
        docker("stop", "-t", "2", names["ollama"])
        for _ in range(4):
            _, exhausted, _ = request(interrupt_url + "?retry_unavailable=true", {})
        check(exhausted["attempts"] == 3 and exhausted["retry_allowed"] is False, "Retries stop at three total attempts")
        check(sql("SELECT count(*) FROM audit_events WHERE event_type='ticket_enrichment_interrupted'") == "1", "Interrupted recovery audit idempotent")
        check(sql("SELECT count(*) FROM tickets WHERE source_event_id='" + tag + "-interrupted'") == "1", "Interrupted inference cannot duplicate ticket")
        report = {"passed": len(checks), "failed": 0, "skipped": 0, "checks": checks,
                  "duration_seconds": round(time.monotonic() - began, 2),
                  "infrastructure": "Live isolated PostgreSQL/FastAPI/n8n/Next.js; Ollama HTTP stub",
                  "production_resources_modified": False, "lease_expiry": "actual 120 seconds; no clock or row manipulation"}
        args.output.write_text(json.dumps(report, indent=2) + "\n")
        print(json.dumps({k: v for k, v in report.items() if k != "checks"}), flush=True)
    finally:
        # Only uniquely named containers with this exact harness ownership label.
        for name in reversed(started):
            info = json.loads(docker("inspect", names[name]).stdout)[0]
            assert info["Config"]["Labels"].get("flowforge.recovery-test") == tag
            docker("rm", "-f", names[name], check=False)
        docker("network", "rm", tag, check=False)
        # Remove only harness plaintext configuration; retain synthetic databases.
        for p in (env, pg_env, credential):
            p.unlink(missing_ok=True)
        print("Private synthetic database artifacts retained:", folder, flush=True)


if __name__ == "__main__":
    main()
