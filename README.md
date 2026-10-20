# FlowForge AI

A local-first AI workflow automation platform built
with n8n, FastAPI, PostgreSQL, Ollama, and Next.js.

## Project Goal

Automate repetitive business operations while retaining
human approval, auditability, and failure recovery.

## Official Implementation Roadmap

1. **Implementation 01**: Local infrastructure setup (Verified).
2. **Implementation 02**: Data contracts, idempotent ticket ingestion, safe audit logging, and mock CRM APIs (Verified).
3. **Implementation 03**: Deterministic n8n support-ticket workflow.
4. **Implementation 04**: Bounded Ollama AI enrichment.
5. **Implementation 05**: Human approval and minimal dashboard.

## Technology Stack

- **n8n Community**: Workflow orchestration (Host port 5679)
- **FastAPI**: Backend API & business logic (Host port 8001)
- **PostgreSQL 17**: Persistent application data (Internal port 5432)
- **SQLAlchemy 2.x & psycopg 3**: Database ORM and synchronous connection pooling
- **Alembic**: Versioned database migrations
- **Pydantic v2**: Strict data contracts & input validation
- **Docker Compose**: Local infrastructure
- **pytest**: Automated testing suite

## Current Status

Implementation 02 is complete and verified.

## Service Addresses

- **FastAPI Core**: http://localhost:8001
- **API Documentation**: http://localhost:8001/docs
- **FlowForge n8n**: http://localhost:5679
- **Health Check**: http://localhost:8001/health

## Operational Commands

```bash
# Apply database migrations (explicit command required)
docker compose run --rm backend alembic upgrade head

# Run automated test suite (includes isolated PostgreSQL integration tests)
docker compose run --rm backend pytest -v

# Run live end-to-end API smoke test (safe to run repeatedly)
python3 scripts/smoke_test.py
```

This is an engineering portfolio project, not a commercial SaaS platform.
