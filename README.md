# FlowForge AI

A local-first AI workflow automation platform built with n8n, FastAPI, PostgreSQL, Ollama, and Next.js.

## Project Goal

Automate repetitive business operations while retaining human approval, auditability, and failure recovery.

## Official Implementation Roadmap

1. **Implementation 01**: Local infrastructure setup (Verified).
2. **Implementation 02**: Data contracts, idempotent ticket ingestion, safe audit logging, and mock CRM APIs (Verified).
3. **Implementation 03**: Deterministic n8n support-ticket workflow orchestration (Verified).
4. **Implementation 04**: Bounded local AI enrichment using Ollama.
5. **Implementation 05**: Human approval and minimal operational dashboard.
6. **Implementation 06**: Lead intake and deduplication.
7. **Implementation 07**: Daily operations digest.

## Technology Stack

- **n8n Community 2.43.8**: Workflow orchestration (Dedicated host port 5679)
- **FastAPI**: Backend API & business logic (Host port 8001)
- **PostgreSQL 17**: Persistent application data (Internal port 5432)
- **SQLAlchemy 2.x & psycopg 3**: Database ORM and synchronous connection pooling
- **Alembic**: Versioned database migrations
- **Pydantic v2**: Strict data contracts & input validation
- **Docker Compose**: Local infrastructure
- **pytest**: Automated testing suite

## Current Status

**Implementation 03 is complete and verified.**
The support ticket intake workflow (`FlowForge AI - Support Ticket Intake`) is actively orchestrating via n8n on port 5679, delegating schema validation, business logic, and idempotency to FastAPI on port 8001, and recording execution telemetry in PostgreSQL.

## Workflow Location

The reproducible workflow definition is version-controlled at:
- `workflows/support_ticket_intake.json`
- Mapped inside FlowForge n8n container at: `/workflows/support_ticket_intake.json`

## Service Addresses

| Service | Address |
| :--- | :--- |
| **FastAPI Core** | http://localhost:8001 |
| **API Documentation** | http://localhost:8001/docs |
| **FlowForge n8n** | http://localhost:5679 |
| **Health Check** | http://localhost:8001/health |
| **Live Webhook Endpoint** | http://localhost:5679/webhook/support-ticket-intake |

---

## Operational Commands

### 1. Database Migrations
```bash
docker compose run --rm backend alembic upgrade head
```

### 2. Backend Unit and Integration Tests (30 tests)
```bash
docker compose run --rm backend pytest -v
```

### 3. Live Workflow End-to-End Acceptance & Reliability Tests (35 assertions)
Runs real HTTP requests through the FlowForge n8n webhook on port 5679, exercising 10 synthetic fixtures, data minimization verification, idempotency replays, conflict handling, validation errors, and real failure modes (503, timeouts, connection drops, and uncertain replay recovery):
```bash
python3 scripts/test_support_workflow.py
```

### 4. API Smoke Tests
```bash
python3 scripts/smoke_test.py
```

### 5. Local Demonstration & Workflow Import
To inspect or re-import the workflow into FlowForge n8n:
```bash
# Import workflow JSON
docker compose exec n8n n8n import:workflow --input=/workflows/support_ticket_intake.json

# Publish (activate) the workflow
docker compose exec n8n n8n publish:workflow --id=FlowForgeSupportIntake01

# Restart n8n container to register persistent webhook route
docker compose restart n8n

# Trigger test submission
curl -X POST http://localhost:5679/webhook/support-ticket-intake \
  -H "Content-Type: application/json" \
  -H "X-Correlation-ID: demo-corr-001" \
  -d '{"source_event_id": "demo-001", "subject": "Unable to access portal", "body": "Session timeout error"}'
```

This is an engineering portfolio project, not a commercial SaaS platform.
