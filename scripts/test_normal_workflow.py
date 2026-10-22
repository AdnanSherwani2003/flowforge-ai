#!/usr/bin/env python3
"""Normal-operation acceptance; never enables backend fault hooks."""
import json
import time
import uuid
from pathlib import Path
from test_support_workflow import make_request, N8N_WEBHOOK_URL, BACKEND_URL

ROOT = Path(__file__).resolve().parents[1]


def main():
    tag = "normal-" + uuid.uuid4().hex[:12]
    checks = 0

    def check(condition, name):
        nonlocal checks
        assert condition, name
        checks += 1

    def telemetry(response):
        for _ in range(30):
            status, _, run = make_request(BACKEND_URL + "/api/workflow-runs/" + response["execution_id"])
            if status == 200:
                return run
            time.sleep(0.1)
        raise AssertionError("Telemetry missing for " + response["execution_id"])

    check(make_request(BACKEND_URL + "/health")[0] == 200, "backend health")
    fixtures = json.loads((ROOT / "fixtures/support_ticket_fixtures.json").read_text())
    first = None
    for index, fixture in enumerate(fixtures["valid_tickets"]):
        payload = {k: fixture[k] for k in ("subject", "body")}
        payload["source_event_id"] = f"{tag}-{index}"
        status, headers, response = make_request(
            N8N_WEBHOOK_URL, "POST", payload, {"X-Correlation-ID": tag}
        )
        check(status == 201 and response.get("outcome") == "created", "fixture creation")
        lower = {k.lower(): v for k, v in headers.items()}
        check(
            lower.get("x-correlation-id") == tag
            and lower.get("x-flowforge-execution-id") == response["execution_id"]
            and lower.get("x-flowforge-telemetry") == "best-effort"
            and response.get("telemetry") == "best_effort",
            "response tracing and telemetry semantics",
        )
        run = telemetry(response)
        check(run["correlation_id"] == tag and run["ticket_id"] == response["ticket_id"], "telemetry")
        if first is None:
            first = payload, response

    payload, original = first
    status, _, duplicate = make_request(N8N_WEBHOOK_URL, "POST", payload)
    check(status == 200 and duplicate.get("duplicate") is True and duplicate.get("ticket_id") == original["ticket_id"], "replay")
    status, _, conflict = make_request(N8N_WEBHOOK_URL, "POST", {**payload, "body": "Synthetic conflicting body"})
    check(status == 409 and conflict.get("outcome") == "conflict", "conflict")
    status, _, audit = make_request(BACKEND_URL + "/api/tickets/" + original["ticket_id"] + "/audit")
    check(status == 200 and any(e["safe_detail"].get("correlation_id") == tag and e["safe_detail"].get("execution_id") == original["execution_id"] for e in audit["audit_events"]), "audit trace")
    check(all("subject" not in e["safe_detail"] and "body" not in e["safe_detail"] for e in audit["audit_events"]), "audit minimization")

    for case in fixtures["edge_cases"]:
        if case.get("expected_status_code") != 422:
            continue
        data = case["payload"].copy()
        if "source_event_id" in data:
            data["source_event_id"] = tag + data["source_event_id"]
        status, _, response = make_request(N8N_WEBHOOK_URL, "POST", data)
        check(status == 422 and response.get("outcome") == "validation_error" and "input" not in response.get("error", ""), case["scenario"])
        run = telemetry(response)
        check(run["status_code"] == 422 and "error" not in run["safe_detail"], "rejected-event telemetry")
        if len(str(data.get("source_event_id", ""))) > 128:
            check(run["source_event_id"] is None and run["safe_detail"]["source_event_id_rejected"], "oversized event summarized")

    # Pydantic decides validation. Missing/null/types must survive n8n unchanged.
    missing = object()
    values = [123, 1.5, True, False, None, [], ["synthetic"], {}, {"synthetic": "object"}, missing, "   "]
    for field in ("source_event_id", "subject", "body"):
        for index, value in enumerate(values):
            data = {"source_event_id": f"{tag}-type-{field}-{index}", "subject": "Synthetic", "body": "Synthetic"}
            if value is missing:
                data.pop(field)
            else:
                data[field] = value
            before = make_request(BACKEND_URL + "/api/tickets?limit=1")[2]["total"]
            direct, _, _ = make_request(BACKEND_URL + "/api/tickets", "POST", data)
            status, _, response = make_request(N8N_WEBHOOK_URL, "POST", data)
            check(direct == status == 422 and response.get("outcome") == "validation_error", f"type parity {field}/{index}")
            after = make_request(BACKEND_URL + "/api/tickets?limit=1")[2]["total"]
            check(before == after, "invalid types persist no ticket")
            check(telemetry(response)["status_code"] == 422, "invalid type telemetry")

    for root in (None, 123, True, [], ["synthetic"], "synthetic", {}):
        direct, _, _ = make_request(BACKEND_URL + "/api/tickets", "POST", root)
        status, _, response = make_request(N8N_WEBHOOK_URL, "POST", root)
        check(direct == status == 422, "top-level JSON parity " + type(root).__name__)
        check(telemetry(response)["status_code"] == 422, "top-level rejection telemetry")

    data = {"source_event_id": tag + "-trim", "subject": "  Synthetic  ", "body": "  Synthetic body  "}
    status, _, response = make_request(N8N_WEBHOOK_URL, "POST", data)
    ticket = make_request(BACKEND_URL + "/api/tickets/" + response["ticket_id"])[2]
    check(status == 201 and ticket["subject"] == "Synthetic" and ticket["body"] == "Synthetic body", "valid strings retain backend trimming")

    for index, correlation in enumerate(["c", "c" * 100, "c" * 101, "", " ", "bad id", "bad/id"]):
        expected = 201 if index < 2 else 422
        data = {"source_event_id": f"{tag}-corr-{index}", "subject": "Synthetic", "body": "Synthetic"}
        before = make_request(BACKEND_URL + "/api/tickets?limit=1")[2]["total"]
        direct, _, _ = make_request(BACKEND_URL + "/api/tickets", "POST", {**data, "source_event_id": data["source_event_id"] + "-direct"}, {"X-Correlation-ID": correlation})
        status, _, response = make_request(N8N_WEBHOOK_URL, "POST", data, {"X-Correlation-ID": correlation})
        check(status == direct == expected, f"correlation parity {index}")
        after = make_request(BACKEND_URL + "/api/tickets?limit=1")[2]["total"]
        check(after - before == (2 if expected == 201 else 0), "correlation rejected before persistence")
        run = telemetry(response)
        check(run["correlation_id"] == response["correlation_id"] and run["safe_detail"]["correlation_rejected"] == (expected == 422), "correlation telemetry")
        if expected == 201:
            check(response["correlation_id"] == correlation, "valid correlation preserved")

    for mode in ("503", "timeout", "conn-reset", "timeout-after-persist"):
        data = {"source_event_id": f"{tag}-disabled-{mode}", "subject": "test-sim-503 timeout", "body": "Synthetic only", "simulate": mode}
        status, _, response = make_request(N8N_WEBHOOK_URL, "POST", data, {"X-FlowForge-Simulate": mode})
        check(status == 201 and response.get("outcome") == "created", "public fault hook disabled " + mode)
    data = {"source_event_id": tag + "-disabled-direct", "subject": "Synthetic", "body": "Synthetic"}
    check(make_request(BACKEND_URL + "/api/tickets", "POST", data, {"X-FlowForge-Simulate": "503"})[0] == 201, "direct fault hook disabled")
    print(f"Normal-operation acceptance: {checks}/{checks} assertions passed")


if __name__ == "__main__":
    main()
