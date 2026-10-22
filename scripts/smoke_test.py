#!/usr/bin/env python3
"""FlowForge AI Implementation 02 — End-to-End Smoke Test Script
Executes automated health, ticket, idempotency, conflict, audit, and mock-CRM verification.
Designed to be completely safe, isolated, and reproducible when run repeatedly.
"""
import json
import time
import urllib.request
import urllib.error

BASE_URL = "http://127.0.0.1:8001"

def request(method, path, data=None):
    url = f"{BASE_URL}{path}"
    headers = {"Content-Type": "application/json"} if data else {}
    req = urllib.request.Request(
        url,
        data=json.dumps(data).encode("utf-8") if data else None,
        headers=headers,
        method=method
    )
    try:
        with urllib.request.urlopen(req) as resp:
            body = resp.read().decode("utf-8")
            return resp.status, json.loads(body) if body else {}
    except urllib.error.HTTPError as err:
        body = err.read().decode("utf-8")
        return err.code, json.loads(body) if body else {}

def main():
    import uuid
    run_id = f"smoke-{int(time.time())}-{uuid.uuid4().hex[:6]}"
    print(f"=== FlowForge AI Smoke Test (Run: {run_id}) ===")

    # 1. Health
    status, data = request("GET", "/health")
    print(f"[1/8] Health check: HTTP {status} (status={data.get('status')})")
    assert status == 200 and data.get("status") == "ok"

    # 2. Ticket creation (First-time submission -> HTTP 201)
    ticket_payload = {
        "source_event_id": f"evt-{run_id}-ticket",
        "subject": "CLI verification ticket",
        "body": "Automated verification ticket generated during test cycle."
    }
    status, data = request("POST", "/api/tickets", ticket_payload)
    print(f"[2/8] New ticket creation: HTTP {status} (id={data.get('id')}, duplicate={data.get('duplicate')})")
    assert status == 201, f"Expected 201, got {status}"
    assert data["duplicate"] is False
    ticket_id = data["id"]

    # 3. Ticket retrieval
    status, data = request("GET", f"/api/tickets/{ticket_id}")
    print(f"[3/8] Retrieve ticket by ID: HTTP {status} (subject='{data.get('subject')}')")
    assert status == 200 and data["id"] == ticket_id

    # 4. Duplicate identical submission (Replay -> HTTP 200, duplicate=True)
    status, data = request("POST", "/api/tickets", ticket_payload)
    print(f"[4/8] Idempotent duplicate: HTTP {status} (duplicate={data.get('duplicate')})")
    assert status == 200, f"Expected 200, got {status}"
    assert data.get("duplicate") is True
    assert data.get("id") == ticket_id

    # 5. Conflicting submission (Altered body/subject -> HTTP 409 Conflict)
    conflict = dict(ticket_payload, subject="Altered conflicting subject")
    status, data = request("POST", "/api/tickets", conflict)
    print(f"[5/8] Conflicting payload: HTTP {status} (detail='{data.get('detail')}')")
    assert status == 409, f"Expected 409, got {status}"

    # 6. Audit trail verification
    status, data = request("GET", f"/api/tickets/{ticket_id}/audit")
    events = [e["event_type"] for e in data.get("audit_events", [])]
    print(f"[6/8] Audit history: HTTP {status} (events={events})")
    assert status == 200
    assert "ticket_created" in events
    assert "ticket_duplicate_received" in events
    assert "ticket_conflict_received" in events

    # 7. Mock CRM Lead creation
    lead_payload = {
        "source_event_id": f"evt-{run_id}-lead",
        "name": "Dev User",
        "email": f"  Dev.User.{run_id}@Example.COM  "
    }
    status, data = request("POST", "/api/mock-crm/leads", lead_payload)
    print(f"[7/8] Lead creation: HTTP {status} (normalized_email='{data.get('normalized_email')}')")
    assert status == 201, f"Expected 201, got {status}"
    assert data["normalized_email"] == f"dev.user.{run_id}@example.com"
    assert data["duplicate"] is False
    lead_id = data["id"]

    # 8. Mock CRM Duplicate lead
    status, data = request("POST", "/api/mock-crm/leads", lead_payload)
    print(f"[8/8] Lead duplicate: HTTP {status} (duplicate={data.get('duplicate')})")
    assert status == 200, f"Expected 200, got {status}"
    assert data["duplicate"] is True
    assert data["id"] == lead_id

    print("\nSUCCESS: All FlowForge AI API contracts verified successfully!")

if __name__ == "__main__":
    main()
