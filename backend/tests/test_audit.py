def test_audit_event_generation_and_safe_detail(client):
    payload = {
        "source_event_id": "evt-audit-demo-01",
        "subject": "Sensitive customer inquiry with token secret123",
        "body": "My api key is abc-xyz-secret and my credit card is 4111222233334444.",
    }

    create_res = client.post("/api/tickets", json=payload)
    assert create_res.status_code == 201
    ticket_id = create_res.json()["id"]

    # Trigger duplicate submission
    dup_res = client.post("/api/tickets", json=payload)
    assert dup_res.status_code == 200

    # Trigger conflicting submission
    conflict_payload = {
        "source_event_id": "evt-audit-demo-01",
        "subject": "Changed subject",
        "body": "Changed body",
    }
    conflict_res = client.post("/api/tickets", json=conflict_payload)
    assert conflict_res.status_code == 409

    # Retrieve audit trail
    audit_res = client.get(f"/api/tickets/{ticket_id}/audit")
    assert audit_res.status_code == 200
    audit_data = audit_res.json()
    assert audit_data["ticket_id"] == ticket_id

    events = audit_data["audit_events"]
    assert len(events) >= 3

    event_types = [e["event_type"] for e in events]
    assert "ticket_created" in event_types
    assert "ticket_duplicate_received" in event_types
    assert "ticket_conflict_received" in event_types

    # Inspect safe_detail of ticket_created: ensure full body and credentials are NOT logged
    created_event = next(e for e in events if e["event_type"] == "ticket_created")
    detail = created_event["safe_detail"]

    # Verify that safe_detail only stores operational metrics, not full sensitive content
    assert "source_event_id" in detail
    assert "subject_length" in detail
    assert "body_length" in detail
    assert "secret123" not in str(detail)
    assert "4111222233334444" not in str(detail)
    assert "abc-xyz-secret" not in str(detail)


def test_audit_nonexistent_ticket_returns_404(client):
    res = client.get("/api/tickets/missing-id-999/audit")
    assert res.status_code == 404
