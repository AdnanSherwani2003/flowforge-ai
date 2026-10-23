import app.models.review  # noqa: F401
import pytest
from typing import Generator
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool

import app.models.ticket  # noqa: F401
import app.models.lead  # noqa: F401
import app.models.audit_event  # noqa: F401
import app.models.workflow_run  # noqa: F401
import app.models.ticket_enrichment  # noqa: F401
from app.models.base import Base
from app.core.database import get_db
from app.main import app as fastapi_app

SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)

TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="function")
def db_session() -> Generator[Session, None, None]:
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def client(db_session: Session) -> Generator[TestClient, None, None]:
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    fastapi_app.dependency_overrides[get_db] = override_get_db
    with TestClient(fastapi_app) as test_client:
        yield test_client
    fastapi_app.dependency_overrides.clear()


def pytest_configure(config):
    """Use a unique owner-only base instead of predictable /tmp/pytest-of-USER."""
    if config.option.basetemp is None:
        import tempfile
        from pathlib import Path
        config.option.basetemp = Path(tempfile.mkdtemp(prefix="flowforge-pytest-"))
