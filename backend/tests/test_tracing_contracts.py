import pytest
from sqlalchemy import select, func
from app.models.ticket import Ticket


@pytest.mark.parametrize("field", ["source_event_id", "subject", "body"])
@pytest.mark.parametrize("value", [17, 1.5, True, False, None, [], ["value"], {}, {"value": "x"}, "   "])
def test_ticket_rejects_invalid_field_types(client, field, value):
    payload = {"source_event_id": "type-contract", "subject": "Synthetic", "body": "Synthetic"}
    payload[field] = value
    response = client.post("/api/tickets", json=payload)
    assert response.status_code == 422
    assert "input" not in response.text


@pytest.mark.parametrize("header", ["X-Correlation-ID", "X-Execution-ID"])
@pytest.mark.parametrize("value", ["", " ", "a" * 101, "bad id", "bad/id"])
def test_invalid_trace_headers_reject_before_persistence(client, db_session, header, value):
    response = client.post(
        "/api/tickets",
        json={"source_event_id": "invalid-trace", "subject": "Synthetic", "body": "Synthetic"},
        headers={header: value},
    )
    assert response.status_code == 422
    assert db_session.scalar(select(func.count(Ticket.id))) == 0
    assert "input" not in response.text


@pytest.mark.parametrize("length", [1, 100])
def test_valid_trace_header_boundaries(client, length):
    correlation = "c" * length
    execution = "e" * length
    response = client.post(
        "/api/tickets",
        json={"source_event_id": "valid-trace", "subject": "Synthetic", "body": "Synthetic"},
        headers={"X-Correlation-ID": correlation, "X-Execution-ID": execution},
    )
    assert response.status_code == 201
    assert response.headers["X-Correlation-ID"] == correlation
    audit = client.get(f"/api/tickets/{response.json()['id']}/audit").json()["audit_events"][0]
    assert audit["safe_detail"]["correlation_id"] == correlation
    assert audit["safe_detail"]["execution_id"] == execution
    telemetry = {
        "execution_id": execution, "correlation_id": correlation,
        "outcome": "created", "status_code": 201, "safe_detail": {"status": "accepted"},
    }
    assert client.post("/api/workflow-runs", json=telemetry).status_code == 201


def test_missing_correlation_is_generated(client):
    response = client.post(
        "/api/tickets",
        json={"source_event_id": "generated-trace", "subject": "Synthetic", "body": "Synthetic"},
    )
    assert response.status_code == 201
    correlation = response.headers["X-Correlation-ID"]
    audit = client.get(f"/api/tickets/{response.json()['id']}/audit").json()["audit_events"][0]
    assert audit["safe_detail"]["correlation_id"] == correlation


@pytest.mark.parametrize("field", ["correlation_id", "execution_id"])
def test_telemetry_rejects_long_trace_id(client, field):
    payload = {"execution_id": "exec", "correlation_id": "corr", "outcome": "created", "status_code": 201}
    payload[field] = "x" * 101
    assert client.post("/api/workflow-runs", json=payload).status_code == 422


@pytest.mark.parametrize("detail", [{"body": "private"}, {"error": "raw error"}, {"duplicate": "yes"}, {"status": "private"}, {"error_code": "private"}])
def test_telemetry_metadata_is_allowlisted(client, detail):
    payload = {"execution_id": "exec", "correlation_id": "corr", "outcome": "created", "status_code": 201, "safe_detail": detail}
    response = client.post("/api/workflow-runs", json=payload)
    assert response.status_code == 422
    assert "private" not in response.text
