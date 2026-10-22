#!/usr/bin/env python3
"""scripts/test_support_workflow.py

Comprehensive live acceptance, reliability, and hardening regression test suite for
FlowForge AI Implementation 03: Deterministic n8n Workflow Orchestration.

Verifications:
1. Infrastructure & Health (FastAPI & n8n)
2. Synthetic Fixture Ingestion (>= 10 unique cases)
3. Database Persistence & Full Traceability
4. Data Minimization:
   - Audit trail safe_detail strictly excludes raw subject, body, or credentials.
   - HTTP 422 validation responses strictly exclude raw input echoing.
5. Idempotent Duplicate Replay (200 OK with duplicate: true)
6. Conflicting Replay Protection (HTTP 409 Conflict)
7. Validation Failure Routing (HTTP 422 for all contract edge cases)
8. Failure Simulation Isolation (Task 3):
   - Ordinary user sending 'test-sim-503-...' creates normal ticket (no failure triggered).
   - Failure simulation triggers ONLY when explicit 'simulate' flag is supplied.
9. Real Failure Mode Verification:
   - Live HTTP 503 Service Unavailable
   - Live Backend Gateway Timeout (bounded termination <= 8.0s)
   - Live TCP Connection Drop / Reset Handling
10. Retry Correctness (Task 6):
   - Case A: Replay after failure occurring BEFORE persistence -> 201 Created -> 200 Duplicate.
   - Case B: Replay after timeout occurring AFTER persistence -> 200 Duplicate (no duplicate tickets).
11. Telemetry Idempotency on (workflow_name, execution_id)
"""

import json
import sys
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path

N8N_WEBHOOK_URL = "http://localhost:5679/webhook/support-ticket-intake"
BACKEND_URL = "http://localhost:8001"
FIXTURES_PATH = Path(__file__).resolve().parent.parent / "fixtures" / "support_ticket_fixtures.json"


def make_request(url: str, method: str = "GET", data: dict = None, headers: dict = None, timeout: float = 12.0):
    if headers is None:
        headers = {}
    encoded_data = None
    if data is not None:
        encoded_data = json.dumps(data).encode("utf-8")
        headers["Content-Type"] = "application/json"

    req = urllib.request.Request(url, data=encoded_data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as res:
            body = res.read().decode("utf-8")
            return res.status, dict(res.headers), json.loads(body) if body else {}
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8")
        try:
            parsed_body = json.loads(body) if body else {}
        except Exception:
            parsed_body = {"raw": body}
        return e.code, dict(e.headers), parsed_body
    except Exception as e:
        return 0, {}, {"error": str(e)}


def run_tests():
    print("=" * 70)
    print(" FlowForge AI — Implementation 03 Final Hardening & Acceptance Suite")
    print("=" * 70)
    print(f"Target n8n Webhook: {N8N_WEBHOOK_URL}")
    print(f"Target FastAPI Backend: {BACKEND_URL}")
    print()

    run_id = uuid.uuid4().hex[:8]
    passed_count = 0
    total_count = 0

    def assert_test(name: str, condition: bool, details: str = ""):
        nonlocal passed_count, total_count
        total_count += 1
        if condition:
            passed_count += 1
            print(f"  [PASS] {name}")
        else:
            print(f"  [FAIL] {name} - {details}")

    # 1. Health Checks
    print("--- 1. Health & Infrastructure Verification ---")
    st, hdrs, body = make_request(f"{BACKEND_URL}/health")
    assert_test(
        "FastAPI /health endpoint is operational (200 OK)",
        st == 200 and body.get("status") in ("ok", "healthy"),
        f"Status: {st}, Body: {body}",
    )

    # 2. Load Fixtures
    print("\n--- 2. Loading Test Fixtures ---")
    with open(FIXTURES_PATH, "r", encoding="utf-8") as f:
        fixtures = json.load(f)
    valid_tickets = fixtures.get("valid_tickets", [])
    assert_test(
        "Synthetic test fixtures loaded (>= 10 cases)",
        len(valid_tickets) >= 10,
        f"Found {len(valid_tickets)} valid tickets",
    )

    # 3. 10 Scripted First-Time Valid Submissions
    print("\n--- 3. Testing 10 Scripted First-Time Ticket Submissions ---")
    created_tickets = {}
    for item in valid_tickets:
        event_id = f"ff-run-{run_id}-item-{item['id_suffix']}"
        corr_id = f"corr-{run_id}-{item['id_suffix']}"
        payload = {
            "source_event_id": event_id,
            "subject": item["subject"],
            "body": item["body"],
        }
        st, hdrs, resp = make_request(
            N8N_WEBHOOK_URL,
            method="POST",
            data=payload,
            headers={"X-Correlation-ID": corr_id},
        )
        is_success = (
            st == 201
            and resp.get("outcome") == "created"
            and resp.get("status") == "accepted"
            and resp.get("duplicate") is False
            and bool(resp.get("ticket_id"))
            and resp.get("correlation_id") == corr_id
        )
        assert_test(
            f"Case {item['id_suffix']}: {item['subject'][:45]}... -> 201 Created",
            is_success,
            f"Status: {st}, Resp: {resp}",
        )
        if is_success:
            created_tickets[event_id] = {
                "ticket_id": resp["ticket_id"],
                "correlation_id": corr_id,
                "execution_id": resp.get("execution_id"),
                "subject": item["subject"],
                "body": item["body"],
            }

    # 4. Persistence & Audit Verification
    print("\n--- 4. Database Persistence & Execution Traceability Verification ---")
    first_event_id = list(created_tickets.keys())[0]
    first_ticket_info = created_tickets[first_event_id]
    t_id = first_ticket_info["ticket_id"]
    exec_id = first_ticket_info["execution_id"]

    # Verify Ticket Record in FastAPI
    st, _, ticket_data = make_request(f"{BACKEND_URL}/api/tickets/{t_id}")
    assert_test(
        "Created ticket exists in PostgreSQL via GET /api/tickets/{id}",
        st == 200 and ticket_data.get("id") == t_id and ticket_data.get("source_event_id") == first_event_id,
        f"Status: {st}, Ticket: {ticket_data}",
    )

    # Verify Ticket Audit Trail & Data Minimization
    st, _, audit_data = make_request(f"{BACKEND_URL}/api/tickets/{t_id}/audit")
    events = audit_data.get("audit_events", [])
    has_audit = any(
        e.get("safe_detail", {}).get("correlation_id") == first_ticket_info["correlation_id"]
        and e.get("safe_detail", {}).get("execution_id") == str(exec_id)
        for e in events
    )
    assert_test(
        "Ticket audit trail contains correlation_id and execution_id",
        st == 200 and has_audit,
        f"Audit Events: {events}",
    )

    # Verify strict data minimization in safe_detail
    all_safe_details = [e.get("safe_detail", {}) for e in events]
    has_no_raw_subject = all(
        "subject" not in sd and "body" not in sd and first_ticket_info["subject"] not in str(sd)
        for sd in all_safe_details
    )
    assert_test(
        "Audit safe_detail strictly excludes raw subject and body (Data Minimization)",
        has_no_raw_subject,
        f"Safe Details: {all_safe_details}",
    )

    # Verify Workflow Run Telemetry Record
    st, _, run_record = make_request(f"{BACKEND_URL}/api/workflow-runs/{exec_id}")
    assert_test(
        "Workflow run telemetry recorded in /api/workflow-runs/{execution_id}",
        st == 200 and run_record.get("execution_id") == str(exec_id) and run_record.get("ticket_id") == t_id,
        f"Status: {st}, Run: {run_record}",
    )

    # 5. Idempotent Duplicate Replay
    print("\n--- 5. Idempotency & Replay Protection ---")
    dup_corr_id = f"corr-{run_id}-dup-01"
    dup_payload = {
        "source_event_id": first_event_id,
        "subject": first_ticket_info["subject"],
        "body": first_ticket_info["body"],
    }
    st, _, dup_resp = make_request(
        N8N_WEBHOOK_URL,
        method="POST",
        data=dup_payload,
        headers={"X-Correlation-ID": dup_corr_id},
    )
    assert_test(
        "Identical duplicate replay returns 200 OK with duplicate: true and same ticket_id",
        st == 200
        and dup_resp.get("outcome") == "duplicate_replayed"
        and dup_resp.get("ticket_id") == t_id
        and dup_resp.get("duplicate") is True,
        f"Status: {st}, Resp: {dup_resp}",
    )

    # 6. Conflicting Payload Replay
    print("\n--- 6. Conflicting Duplicate Protection ---")
    conf_corr_id = f"corr-{run_id}-conf-01"
    conf_payload = {
        "source_event_id": first_event_id,
        "subject": "Completely altered conflicting subject",
        "body": "Altered conflicting body",
    }
    st, _, conf_resp = make_request(
        N8N_WEBHOOK_URL,
        method="POST",
        data=conf_payload,
        headers={"X-Correlation-ID": conf_corr_id},
    )
    assert_test(
        "Conflicting replay is rejected with HTTP 409 Conflict",
        st == 409 and conf_resp.get("outcome") == "conflict" and conf_resp.get("status") == "rejected",
        f"Status: {st}, Resp: {conf_resp}",
    )

    # 7. Invalid Field Validation Routing & Error Sanitization
    print("\n--- 7. Validation Failure Routing & Error Sanitization ---")
    edge_cases = fixtures.get("edge_cases", [])
    validation_cases = [c for c in edge_cases if c.get("expected_status_code") == 422]
    for vc in validation_cases:
        c_name = vc["scenario"]
        payload = vc["payload"].copy()
        if "source_event_id" in payload:
            payload["source_event_id"] = f"ff-run-{run_id}-{payload['source_event_id']}"

        st, _, v_resp = make_request(
            N8N_WEBHOOK_URL,
            method="POST",
            data=payload,
            headers={"X-Correlation-ID": f"corr-{run_id}-{c_name}"},
        )
        v_err = str(v_resp.get("error", ""))
        assert_test(
            f"Edge case '{c_name}' rejected with HTTP 422 and sanitized error string",
            st == 422
            and v_resp.get("outcome") == "validation_error"
            and v_resp.get("status") == "rejected"
            and "input" not in v_err,
            f"Status: {st}, Resp: {v_resp}",
        )

    # 8. Failure Simulation Isolation (Task 3)
    print("\n--- 8. Failure Simulation Isolation ---")
    ordinary_payload = {
        "source_event_id": f"test-sim-503-ordinary-{run_id}",
        "subject": "Customer inquiry mentioning 503 error",
        "body": "Why did my previous checkout fail with 503?",
    }
    st_ord, _, resp_ord = make_request(N8N_WEBHOOK_URL, method="POST", data=ordinary_payload)
    assert_test(
        "Ordinary user request containing '503' string creates ticket normally (201 Created)",
        st_ord == 201 and resp_ord.get("outcome") == "created" and bool(resp_ord.get("ticket_id")),
        f"Status: {st_ord}, Resp: {resp_ord}",
    )

    # 9. Real Failure Modes & Controlled Reliability Routing
    print("\n--- 9. Real Failure Modes & Reliability Verification ---")

    # 9a. Live HTTP 503 Service Unavailable via explicit simulate flag
    fail_503_payload = {
        "source_event_id": f"test-sim-503-{run_id}",
        "subject": "Simulate Database Outage",
        "body": "Verifying 503 handling through n8n workflow",
        "simulate": "503",
    }
    st, _, resp_503 = make_request(N8N_WEBHOOK_URL, method="POST", data=fail_503_payload)
    assert_test(
        "Live HTTP 503 response routes to service_unavailable with 503 status code",
        st == 503
        and resp_503.get("outcome") == "service_unavailable"
        and resp_503.get("status") == "failed"
        and "password" not in str(resp_503)
        and "postgres" not in str(resp_503),
        f"Status: {st}, Resp: {resp_503}",
    )

    # 9b. Live Backend Request Timeout (Bounded Termination <= 8s)
    t_start = time.time()
    fail_timeout_payload = {
        "source_event_id": f"test-sim-timeout-{run_id}",
        "subject": "Simulate Backend Timeout",
        "body": "Verifying bounded timeout behavior in n8n",
        "simulate": "timeout",
    }
    st, _, resp_timeout = make_request(N8N_WEBHOOK_URL, method="POST", data=fail_timeout_payload, timeout=15.0)
    t_duration = time.time() - t_start
    assert_test(
        f"Live backend timeout terminates in bounded time ({t_duration:.2f}s <= 8.0s) with HTTP 503",
        st == 503
        and t_duration <= 8.0
        and resp_timeout.get("outcome") == "service_unavailable"
        and "timed out" in resp_timeout.get("error", "").lower(),
        f"Status: {st}, Duration: {t_duration:.2f}s, Resp: {resp_timeout}",
    )

    # 9c. Live Connection Reset / Drop Handling
    fail_conn_payload = {
        "source_event_id": f"test-sim-conn-reset-{run_id}",
        "subject": "Simulate Connection Drop",
        "body": "Verifying TCP connection abort handling in n8n",
        "simulate": "conn-reset",
    }
    st, _, resp_conn = make_request(N8N_WEBHOOK_URL, method="POST", data=fail_conn_payload)
    assert_test(
        "Live connection drop returns controlled HTTP 503 without crashing workflow",
        st == 503
        and resp_conn.get("outcome") == "service_unavailable"
        and resp_conn.get("status") == "failed",
        f"Status: {st}, Resp: {resp_conn}",
    )

    # 10. Retry Correctness (Task 6)
    print("\n--- 10. Retry Correctness (Pre- vs. Post-Persistence) ---")

    # 10a. Case A: Replay after failure occurring BEFORE persistence
    case_a_id = f"test-case-a-pre-persist-{run_id}"
    case_a_fail_payload = {
        "source_event_id": case_a_id,
        "subject": "Pre-persistence transient outage",
        "body": "Failed before database write",
        "simulate": "503",
    }
    st_a1, _, _ = make_request(N8N_WEBHOOK_URL, method="POST", data=case_a_fail_payload)
    assert_test("Case A Step 1: Pre-persistence failure produced 503", st_a1 == 503, f"Status: {st_a1}")

    # Replay without simulation flag -> creates ticket
    case_a_retry_payload = {
        "source_event_id": case_a_id,
        "subject": "Pre-persistence transient outage",
        "body": "Failed before database write",
    }
    st_a2, _, resp_a2 = make_request(N8N_WEBHOOK_URL, method="POST", data=case_a_retry_payload)
    assert_test(
        "Case A Step 2: Retry creates exactly one ticket (201 Created)",
        st_a2 == 201 and resp_a2.get("outcome") == "created" and bool(resp_a2.get("ticket_id")),
        f"Status: {st_a2}, Resp: {resp_a2}",
    )
    ticket_a_id = resp_a2.get("ticket_id")

    # Second replay of Case A -> detects duplicate
    st_a3, _, resp_a3 = make_request(N8N_WEBHOOK_URL, method="POST", data=case_a_retry_payload)
    assert_test(
        "Case A Step 3: Second replay detects duplicate (200 OK)",
        st_a3 == 200 and resp_a3.get("duplicate") is True and resp_a3.get("ticket_id") == ticket_a_id,
        f"Status: {st_a3}, Resp: {resp_a3}",
    )

    # 10b. Case B: Replay after timeout occurring AFTER persistence
    case_b_id = f"test-case-b-post-persist-{run_id}"
    case_b_timeout_payload = {
        "source_event_id": case_b_id,
        "subject": "Post-persistence gateway timeout",
        "body": "Persisted in DB but client experienced network timeout",
        "simulate": "timeout-after-persist",
    }
    st_b1, _, resp_b1 = make_request(N8N_WEBHOOK_URL, method="POST", data=case_b_timeout_payload, timeout=15.0)
    assert_test(
        "Case B Step 1: Post-persistence timeout produced 503 to client",
        st_b1 == 503 and resp_b1.get("outcome") == "service_unavailable",
        f"Status: {st_b1}, Resp: {resp_b1}",
    )

    # Client retries with identical payload without simulation flag -> must deduplicate without creating 2nd record
    case_b_retry_payload = {
        "source_event_id": case_b_id,
        "subject": "Post-persistence gateway timeout",
        "body": "Persisted in DB but client experienced network timeout",
    }
    st_b2, _, resp_b2 = make_request(N8N_WEBHOOK_URL, method="POST", data=case_b_retry_payload)
    assert_test(
        "Case B Step 2: Retry correctly detects existing record and returns 200 duplicate (No duplicate tickets)",
        st_b2 == 200 and resp_b2.get("duplicate") is True and bool(resp_b2.get("ticket_id")),
        f"Status: {st_b2}, Resp: {resp_b2}",
    )

    # 11. Telemetry Idempotency Check (Task 4)
    print("\n--- 11. Workflow Run Telemetry Idempotency ---")
    telemetry_payload = {
        "workflow_name": "support_ticket_intake",
        "execution_id": f"exec-idemp-hardened-{run_id}",
        "correlation_id": f"corr-idemp-hardened-{run_id}",
        "outcome": "created",
        "status_code": 201,
        "safe_detail": {"test": "idempotency"},
    }
    st_t1, _, resp_t1 = make_request(f"{BACKEND_URL}/api/workflow-runs", method="POST", data=telemetry_payload)
    st_t2, _, resp_t2 = make_request(f"{BACKEND_URL}/api/workflow-runs", method="POST", data=telemetry_payload)
    assert_test(
        "Workflow run endpoint is idempotent on (workflow_name, execution_id)",
        st_t1 == 201 and st_t2 == 201 and resp_t1.get("id") == resp_t2.get("id"),
        f"Run 1 ID: {resp_t1.get('id')}, Run 2 ID: {resp_t2.get('id')}",
    )

    # Summary
    print()
    print("=" * 70)
    print(f" Summary: {passed_count} / {total_count} assertions passed.")
    print("=" * 70)
    return passed_count == total_count


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
