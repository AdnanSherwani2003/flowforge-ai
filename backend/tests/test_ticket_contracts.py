from app.core.config import settings


def test_ticket_missing_fields(client):
    res = client.post("/api/tickets", json={})
    assert res.status_code == 422
    data = res.json()
    assert "detail" in data
    fields = [err["field"] for err in data["detail"]]
    assert "source_event_id" in fields
    assert "subject" in fields
    assert "body" in fields
    # Ensure raw input is NOT echoed in validation response
    assert "input" not in str(data)


def test_ticket_whitespace_only_rejection(client):
    res = client.post(
        "/api/tickets",
        json={
            "source_event_id": "evt-ws-01",
            "subject": "   ",
            "body": "   ",
        },
    )
    assert res.status_code == 422
    data = res.json()
    assert "detail" in data
    # Ensure sensitive raw whitespace or values are not echoed in 'input'
    assert "input" not in str(data)


def test_ticket_oversized_inputs(client):
    sensitive_long_subject = "A" * 256 + "secret_token_12345"
    res = client.post(
        "/api/tickets",
        json={
            "source_event_id": "evt-oversized-01",
            "subject": sensitive_long_subject,
            "body": "Valid body",
        },
    )
    assert res.status_code == 422
    data = res.json()
    assert "detail" in data
    # Verify strict sanitization: the raw 256-char subject and secret_token MUST NOT be in response!
    assert "secret_token_12345" not in str(data)
    assert "input" not in str(data)


def test_ticket_trims_whitespace(client):
    res = client.post(
        "/api/tickets",
        json={
            "source_event_id": "  evt-trim-01  ",
            "subject": "  Needs whitespace trimming  ",
            "body": "  Body with padded whitespace  ",
        },
    )
    assert res.status_code == 201
    ticket = res.json()
    assert ticket["source_event_id"] == "evt-trim-01"
    assert ticket["subject"] == "Needs whitespace trimming"
    assert ticket["body"] == "Body with padded whitespace"


def test_ordinary_user_cannot_trigger_failure_simulation(client):
    """Verify that an ordinary user submitting source_event_id 'test-sim-503-user'
    is processed normally because ENABLE_FAILURE_SIMULATION is False (Task 3)."""
    res = client.post(
        "/api/tickets",
        json={
            "source_event_id": "test-sim-503-user-safe",
            "subject": "User inquiry about 503 error",
            "body": "I saw a 503 error on your site yesterday.",
        },
    )
    # Must succeed with 201 Created because failure simulation is disabled by default!
    assert res.status_code == 201
    assert res.json()["source_event_id"] == "test-sim-503-user-safe"


def test_isolated_failure_simulation_when_explicitly_enabled(client, monkeypatch):
    """Verify that failure simulation ONLY triggers when ENABLE_FAILURE_SIMULATION=True
    AND the explicit internal header X-FlowForge-Simulate is present."""
    monkeypatch.setattr(settings, "ENABLE_FAILURE_SIMULATION", True)

    # 1. Without header -> Still succeeds (no failure)
    res_no_hdr = client.post(
        "/api/tickets",
        json={
            "source_event_id": "test-sim-headerless",
            "subject": "Inquiry",
            "body": "Body content",
        },
    )
    assert res_no_hdr.status_code == 201

    # 2. With header X-FlowForge-Simulate: 503 -> Triggers 503
    res_503 = client.post(
        "/api/tickets",
        json={
            "source_event_id": "test-sim-503-hdr",
            "subject": "Inquiry",
            "body": "Body content",
        },
        headers={"X-FlowForge-Simulate": "503"},
    )
    assert res_503.status_code == 503
    assert res_503.json()["detail"] == "Database service is temporarily unavailable. Please retry shortly."
