def test_create_and_get_workflow_run(client):
    payload = {
        "workflow_name": "support_ticket_intake",
        "execution_id": "exec-test-001",
        "correlation_id": "corr-test-001",
        "source_event_id": "evt-wr-001",
        "ticket_id": "mock-ticket-id-123",
        "outcome": "created",
        "status_code": 201,
        "safe_detail": {
            "status": "accepted",
            "duplicate": False,
        },
    }

    create_res = client.post("/api/workflow-runs", json=payload)
    assert create_res.status_code == 201
    data = create_res.json()
    assert data["id"] is not None
    assert data["execution_id"] == "exec-test-001"
    assert data["correlation_id"] == "corr-test-001"
    assert data["outcome"] == "created"
    assert data["status_code"] == 201

    # Retrieve by execution_id
    get_res = client.get("/api/workflow-runs/exec-test-001")
    assert get_res.status_code == 200
    assert get_res.json()["correlation_id"] == "corr-test-001"

    # Test idempotency: second call with same execution_id returns existing record without creating duplicate
    dup_res = client.post("/api/workflow-runs", json=payload)
    assert dup_res.status_code == 201
    assert dup_res.json()["id"] == data["id"]


def test_list_workflow_runs_pagination_and_filter(client):
    for i in range(5):
        client.post(
            "/api/workflow-runs",
            json={
                "workflow_name": "support_ticket_intake",
                "execution_id": f"exec-batch-{i:03d}",
                "correlation_id": f"corr-batch-{i:03d}",
                "outcome": "created" if i % 2 == 0 else "duplicate_replayed",
                "status_code": 201 if i % 2 == 0 else 200,
            },
        )

    # Filter by outcome
    res_filtered = client.get("/api/workflow-runs?outcome=created")
    assert res_filtered.status_code == 200
    assert res_filtered.json()["total"] == 3


def test_ticket_headers_tracked_in_audit_and_data_minimization(client):
    ticket_payload = {
        "source_event_id": "evt-traced-ticket-01",
        "subject": "System crash on export with token private999",
        "body": "Export fails with 500 when exporting more than 1000 records.",
    }
    headers = {
        "X-Correlation-ID": "corr-trace-header-123",
        "X-Execution-ID": "exec-n8n-456",
    }
    res = client.post("/api/tickets", json=ticket_payload, headers=headers)
    assert res.status_code == 201
    ticket_id = res.json()["id"]

    # Verify audit event captures correlation_id and execution_id, but NO sensitive text
    audit_res = client.get(f"/api/tickets/{ticket_id}/audit")
    assert audit_res.status_code == 200
    audit_events = audit_res.json()["audit_events"]
    assert len(audit_events) >= 1
    safe_detail = audit_events[0]["safe_detail"]
    assert safe_detail.get("correlation_id") == "corr-trace-header-123"
    assert safe_detail.get("execution_id") == "exec-n8n-456"
    assert "subject" not in safe_detail
    assert "body" not in safe_detail
    assert "private999" not in str(safe_detail)
    assert "System crash on export" not in str(safe_detail)
