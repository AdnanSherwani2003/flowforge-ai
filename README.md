# FlowForge AI

A local-first AI workflow automation platform built with n8n, FastAPI, PostgreSQL, Ollama, and Next.js.

## Project Goal

Automate repetitive business operations while retaining human approval, auditability, and failure recovery.

## Official Implementation Roadmap

1. **Implementation 01**: Local infrastructure setup (Verified).
2. **Implementation 02**: Data contracts, idempotent ticket ingestion, safe audit logging, and mock CRM APIs (Verified).
3. **Implementation 03**: Deterministic n8n support-ticket workflow orchestration (Complete and verified).
4. **Implementation 04**: Bounded local AI enrichment using Ollama (Implemented and verified locally; awaiting commit approval).
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
- **Ollama 0.40.8**: Existing local Windows runtime; pinned qwen2.5:3b-instruct model
- **pytest**: Automated testing suite

## Current Status

**Implementation 03 is merged and pushed to main at 1489752. Implementation 04 is implemented and verified locally on implementation-04-ollama-enrichment, with no commit or push.**

The 13-node support workflow accepts tickets before requesting bounded local Ollama
advice. FastAPI validates and stores suggestions separately; ticket category/status
and business actions remain unchanged. Only new tickets enter AI enrichment.

After a Windows restart, open Docker Desktop and Ollama, then verify backend
connectivity. See [restart and outage recovery](docs/implementation-04.md#windows-restart-and-unavailable-service-recovery).

See [Implementation 04](docs/implementation-04.md) for setup, API contracts, measured
evaluation, limitations and preservation evidence. The earlier
[Implementation 03 review](docs/implementation-03-review.md) records completed
credential rotation and maintenance.

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

### 2. Backend Unit and Integration Tests (137 tests)
```bash
docker compose run --rm backend pytest -v
```

### 3. Live Normal-Operation Webhook Acceptance (192 assertions)
Runs synthetic HTTP requests through FlowForge n8n with normal backend simulation disabled. Covers fixtures, type/shape parity, tracing, 100/101-character correlation boundaries, validation, persistence, idempotency, audit and best-effort telemetry:
```bash
python3 scripts/test_support_workflow.py
```

Run real transport faults separately using a disposable n8n engine and synthetic proxy (39 assertions):
```bash
python3 scripts/test_workflow_faults.py
python3 scripts/verify_workflow_runtime.py
```

Run suites sequentially with no unrelated ticket writers. Synthetic business records remain; the fault harness uses no production volumes or credentials.

### 4. API Smoke Tests
```bash
python3 scripts/smoke_test.py
```

### 5. Advisory AI Verification

Requires the existing local model; creates only synthetic application records:

```bash
python3 scripts/test_enrichment_workflow.py
docker compose run --rm --no-deps -e PYTHONPATH=/app -v "$PWD:/workspace:ro" backend python /workspace/scripts/evaluate_enrichment.py
```

The endpoint pair is POST /api/tickets/{id}/enrich and GET /api/tickets/{id}/enrichment.
Results are advisory. Unavailable outcomes require explicit bounded retry; no
customer replies or ticket-state changes occur. GPU and CPU measurements are
recorded in docs/evaluation/.

### 6. Workflow Maintenance

Use the authenticated n8n editor or supported API to update and publish exactly `FlowForgeSupportIntake01`. Production CLI import is not a read-only check: it deactivates imported workflows. Do not unpublish or delete other workflows without approval.

Published node data is configured not to be retained after new completed executions. Ticket content is intentionally stored in the business database and may exist in transient/crashed n8n executions and historical records. Application telemetry retains allowlisted metadata and is best effort.

See [Implementation 03](docs/implementation-03.md) for contracts, privacy limits, fault coverage, and safe credential-rotation guidance. See [Implementation 04](docs/implementation-04.md) for current advisory AI behavior. Implementation 05 has not started.

This is an engineering portfolio project, not a commercial SaaS platform.
