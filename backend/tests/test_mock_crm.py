def test_create_and_get_lead(client):
    payload = {
        "source_event_id": "lead-evt-001",
        "name": "Alice Johnson",
        "email": "   ALICE.JOHNSON@Example.COM   ",
    }

    # 1. Create lead
    create_res = client.post("/api/mock-crm/leads", json=payload)
    assert create_res.status_code == 201
    data = create_res.json()
    assert data["id"] is not None
    assert data["source_event_id"] == "lead-evt-001"
    assert data["name"] == "Alice Johnson"
    # Email must be normalized to lowercase and trimmed
    assert data["normalized_email"] == "alice.johnson@example.com"
    assert data["status"] == "new"
    assert data["duplicate"] is False
    lead_id = data["id"]

    # 2. Retrieve lead by ID
    get_res = client.get(f"/api/mock-crm/leads/{lead_id}")
    assert get_res.status_code == 200
    assert get_res.json()["normalized_email"] == "alice.johnson@example.com"


def test_lead_idempotency_and_conflict(client):
    payload = {
        "source_event_id": "lead-evt-idem-01",
        "name": "Bob Smith",
        "email": "bob.smith@acmecorp.com",
    }

    # First call: 201
    res1 = client.post("/api/mock-crm/leads", json=payload)
    assert res1.status_code == 201
    lead_id = res1.json()["id"]

    # Duplicate call: 200 duplicate=True
    res2 = client.post("/api/mock-crm/leads", json=payload)
    assert res2.status_code == 200
    assert res2.json()["duplicate"] is True
    assert res2.json()["id"] == lead_id

    # Conflicting call: 409 Conflict
    conflict_payload = {
        "source_event_id": "lead-evt-idem-01",
        "name": "Bob Different",
        "email": "bob.different@acmecorp.com",
    }
    res3 = client.post("/api/mock-crm/leads", json=conflict_payload)
    assert res3.status_code == 409


def test_lead_validation_errors(client):
    # Invalid email format
    res = client.post(
        "/api/mock-crm/leads",
        json={"source_event_id": "l-1", "name": "Test", "email": "not-an-email"},
    )
    assert res.status_code == 422

    # Whitespace name
    res2 = client.post(
        "/api/mock-crm/leads",
        json={"source_event_id": "l-2", "name": "   ", "email": "test@example.com"},
    )
    assert res2.status_code == 422


def test_list_leads_pagination(client):
    for i in range(12):
        client.post(
            "/api/mock-crm/leads",
            json={
                "source_event_id": f"lead-page-{i:03d}",
                "name": f"Lead Name {i}",
                "email": f"user{i}@example.com",
            },
        )

    res = client.get("/api/mock-crm/leads?limit=5&offset=0")
    assert res.status_code == 200
    data = res.json()
    assert data["total"] == 12
    assert len(data["items"]) == 5
    assert data["limit"] == 5
    assert data["offset"] == 0
