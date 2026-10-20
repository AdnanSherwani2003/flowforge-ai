from unittest.mock import patch
from sqlalchemy.exc import OperationalError
from app.core.database import check_database_health


def test_db_operational_error_returns_503(client):
    with patch("app.services.ticket_service.get_ticket_by_id", side_effect=OperationalError("connection refused", {}, Exception())):
        response = client.get("/api/tickets/some-id")
        assert response.status_code == 503
        data = response.json()
        assert "temporarily unavailable" in data["detail"].lower()
        # Ensure credentials/host internals are not leaked in detail
        assert "password" not in str(data).lower()
        assert "postgresql://" not in str(data).lower()


def test_check_database_health_failure():
    with patch("sqlalchemy.engine.Engine.connect", side_effect=OperationalError("timeout", {}, Exception())):
        assert check_database_health() is False
