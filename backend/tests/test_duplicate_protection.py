def test_idempotent_ticket_submission(client):
    payload = {
        "source_event_id": "evt-idem-001",
        "subject": "Payment webhook timeout",
        "body": "Stripe webhook failed with timeout after 30s.",
    }

    # Case 1: First submission -> 201 Created
    res1 = client.post("/api/tickets", json=payload)
    assert res1.status_code == 201
    data1 = res1.json()
    assert data1["duplicate"] is False
    original_id = data1["id"]

    # Case 2: Same event ID + identical payload -> 200 OK, duplicate=True
    res2 = client.post("/api/tickets", json=payload)
    assert res2.status_code == 200
    data2 = res2.json()
    assert data2["duplicate"] is True
    assert data2["id"] == original_id
    assert data2["subject"] == payload["subject"]

    # Case 2 with leading/trailing whitespace variations in payload: should still match canonical hash!
    payload_whitespace_variation = {
        "source_event_id": "  evt-idem-001  ",
        "subject": "  Payment webhook timeout  ",
        "body": "  Stripe webhook failed with timeout after 30s.  ",
    }
    res2_ws = client.post("/api/tickets", json=payload_whitespace_variation)
    assert res2_ws.status_code == 200
    assert res2_ws.json()["duplicate"] is True
    assert res2_ws.json()["id"] == original_id

    # Case 3: Same event ID + conflicting payload -> 409 Conflict
    conflicting_payload = {
        "source_event_id": "evt-idem-001",
        "subject": "Different Subject: Database deadlock",
        "body": "Different body describing a completely different error.",
    }
    res3 = client.post("/api/tickets", json=conflicting_payload)
    assert res3.status_code == 409
    assert "conflict" in res3.json()["detail"].lower()

    # Verify that original ticket in database was NOT overwritten
    fetch_res = client.get(f"/api/tickets/{original_id}")
    assert fetch_res.status_code == 200
    assert fetch_res.json()["subject"] == "Payment webhook timeout"

    # Verify ticket count is still 1
    list_res = client.get("/api/tickets")
    assert list_res.json()["total"] == 1
