def test_create_ticket_success(client):
    payload = {
        "source_event_id": "evt-ticket-001",
        "subject": "System login failure on dashboard",
        "body": "User cannot login to the dashboard since 09:00 UTC with error 500."
    }
    response = client.post("/api/tickets", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["id"] is not None
    assert len(data["id"]) > 0
    assert data["source_event_id"] == "evt-ticket-001"
    assert data["subject"] == "System login failure on dashboard"
    assert data["body"] == payload["body"]
    assert data["status"] == "received"
    assert data["category"] == "unknown"
    assert data["duplicate"] is False
    assert "created_at" in data


def test_get_ticket_by_id(client):
    payload = {
        "source_event_id": "evt-ticket-get-01",
        "subject": "Printer network unreachable",
        "body": "Floor 3 printer stopped answering ping requests."
    }
    create_res = client.post("/api/tickets", json=payload)
    assert create_res.status_code == 201
    ticket_id = create_res.json()["id"]

    get_res = client.get(f"/api/tickets/{ticket_id}")
    assert get_res.status_code == 200
    ticket_data = get_res.json()
    assert ticket_data["id"] == ticket_id
    assert ticket_data["subject"] == payload["subject"]
    assert ticket_data["source_event_id"] == payload["source_event_id"]


def test_get_ticket_not_found(client):
    response = client.get("/api/tickets/non-existent-uuid-12345")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


def test_list_tickets_pagination(client):
    for i in range(15):
        client.post(
            "/api/tickets",
            json={
                "source_event_id": f"evt-pagination-{i:03d}",
                "subject": f"Ticket issue #{i}",
                "body": f"Description for issue #{i} with sufficient content.",
            },
        )

    # Page 1 (limit 5, offset 0)
    res_p1 = client.get("/api/tickets?limit=5&offset=0")
    assert res_p1.status_code == 200
    data_p1 = res_p1.json()
    assert data_p1["total"] == 15
    assert data_p1["limit"] == 5
    assert data_p1["offset"] == 0
    assert len(data_p1["items"]) == 5

    # Page 2 (limit 5, offset 5)
    res_p2 = client.get("/api/tickets?limit=5&offset=5")
    assert res_p2.status_code == 200
    data_p2 = res_p2.json()
    assert len(data_p2["items"]) == 5

    # Ensure items on page 1 and page 2 are disjoint
    ids_p1 = {t["id"] for t in data_p1["items"]}
    ids_p2 = {t["id"] for t in data_p2["items"]}
    assert ids_p1.isdisjoint(ids_p2)

    # Test limit validation bounds
    assert client.get("/api/tickets?limit=0").status_code == 422
    assert client.get("/api/tickets?limit=101").status_code == 422
    assert client.get("/api/tickets?offset=-1").status_code == 422
