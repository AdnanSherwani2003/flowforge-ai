def test_ticket_missing_fields(client):
    # Missing body
    res1 = client.post("/api/tickets", json={"source_event_id": "e1", "subject": "Test"})
    assert res1.status_code == 422

    # Missing subject
    res2 = client.post("/api/tickets", json={"source_event_id": "e1", "body": "Body text"})
    assert res2.status_code == 422

    # Missing source_event_id
    res3 = client.post("/api/tickets", json={"subject": "Test", "body": "Body text"})
    assert res3.status_code == 422


def test_ticket_whitespace_only_rejection(client):
    # Whitespace source_event_id
    res = client.post(
        "/api/tickets",
        json={"source_event_id": "   ", "subject": "Valid Subject", "body": "Valid Body"},
    )
    assert res.status_code == 422

    # Whitespace subject
    res = client.post(
        "/api/tickets",
        json={"source_event_id": "evt-ws", "subject": "   \t  ", "body": "Valid Body"},
    )
    assert res.status_code == 422

    # Whitespace body
    res = client.post(
        "/api/tickets",
        json={"source_event_id": "evt-ws", "subject": "Valid Subject", "body": " \n\t "},
    )
    assert res.status_code == 422


def test_ticket_oversized_inputs(client):
    # Subject exceeding 200 characters
    long_subject = "A" * 201
    res = client.post(
        "/api/tickets",
        json={"source_event_id": "evt-long-sub", "subject": long_subject, "body": "Valid body"},
    )
    assert res.status_code == 422

    # Body exceeding 5000 characters
    long_body = "B" * 5001
    res = client.post(
        "/api/tickets",
        json={"source_event_id": "evt-long-body", "subject": "Valid subject", "body": long_body},
    )
    assert res.status_code == 422


def test_ticket_trims_whitespace(client):
    payload = {
        "source_event_id": "  evt-trimmed-01  ",
        "subject": "   Subject with leading and trailing spaces   ",
        "body": "   Body text with whitespace   ",
    }
    response = client.post("/api/tickets", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["source_event_id"] == "evt-trimmed-01"
    assert data["subject"] == "Subject with leading and trailing spaces"
    assert data["body"] == "Body text with whitespace"
