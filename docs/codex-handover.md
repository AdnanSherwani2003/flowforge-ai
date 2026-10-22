# FlowForge AI — Codex Handover Documentation

Welcome to **FlowForge AI**! This document provides the engineering context, runtime architecture, verification commands, and safety boundaries required for OpenAI Codex to seamlessly continue development.

---

## 1. Project Purpose & Philosophy

FlowForge AI is a **local-first AI workflow automation platform** designed to automate repetitive business operations while strictly maintaining **human approval, auditability, data minimization, and deterministic failure recovery**.

Core Architectural Principles:
1. **Local-First & Zero Paid Cloud Dependencies**: Runs entirely on Docker Desktop using open-source, local technologies.
2. **FastAPI & PostgreSQL as the Source of Truth**: n8n serves exclusively as an orchestrator and integration router. All schema validation, idempotency checks, conflict resolution, and data persistence reside firmly in FastAPI and PostgreSQL.
3. **Data Minimization & Privacy**: Customer bodies, subjects, and PII are never echoed back in validation errors, never stored in raw audit detail, and never printed to container logs.
4. **Resilient Failure Recovery**: Webhook routes cleanly handle upstream outages (503), bounded timeouts (5s), connection drops, and retries distinguishing pre-persistence failures from post-persistence client timeouts.

---

## 2. Technology Stack & Service Architecture

| Layer | Technology | Service Name | Container Name | Host Port | Internal Port |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Workflow Engine** | n8n Community 2.43.8 | `n8n` | `flowforge-ai-n8n-1` | `5679` | `5678` |
| **Core Backend & APIs** | FastAPI (Python 3.12) | `backend` | `flowforge-ai-backend-1` | `8001` | `8001` |
| **Persistent Storage** | PostgreSQL 17-alpine | `postgres` | `flowforge-ai-postgres-1` | *Internal only* | `5432` |
| **Database ORM** | SQLAlchemy 2.x + psycopg 3 | N/A | N/A | N/A | N/A |
| **Schema Migrations** | Alembic | N/A | N/A | N/A | N/A |
| **Contract Validation** | Pydantic v2 | N/A | N/A | N/A | N/A |

### Environment & Host Details
- **Repository Location**: `/home/adnan/projects/flowforge-ai`
- **Operating Environment**: Ubuntu WSL2 on Windows 11 with Docker Desktop
- **GitHub Remote**: `https://github.com/AdnanSherwani2003/flowforge-ai.git`
- **Active Branch**: `implementation-03-deterministic-workflow`

---

## 3. Strict Safety & Boundary Requirements

> [!CAUTION]
> **CRITICAL: Protect User's Personal n8n Instance**
> - The host machine has an existing personal n8n instance:
>   - Container: `n8n` (host port `5678`, volume `n8n_data`, contains 37 personal workflows).
> - **FlowForge n8n is strictly bound to port `5679`** (service `n8n`, volume `flowforge-ai_n8n_data`).
> - **NEVER** run commands targeting container `n8n`, port `5678`, or volume `n8n_data`.
> - **NEVER** run `docker compose down -v` or prune global volumes.
> - SentinelPOMDP and Neo4j containers on the host must remain untouched.

---

## 4. Current Implementation Status & Roadmap

### Official Implementation Roadmap
1. [x] **Implementation 01**: Local infrastructure setup (Docker Compose, networking, multi-role PostgreSQL).
2. [x] **Implementation 02**: Data contracts, idempotent ticket ingestion, safe audit logging, and mock CRM APIs.
3. [x] **Implementation 03**: Deterministic n8n support-ticket workflow orchestration (WIP finalized with security hardening).
4. [ ] **Implementation 04**: **Bounded local AI enrichment using Ollama** *(NEXT STEP)*.
5. [ ] **Implementation 05**: Human approval and minimal operational dashboard.
6. [ ] **Implementation 06**: Lead intake and deduplication.
7. [ ] **Implementation 07**: Daily operations digest.

---

## 5. Operations & Development Commands

### Start / Restart FlowForge Services
```bash
cd /home/adnan/projects/flowforge-ai

# Start FlowForge stack
docker compose up -d

# Verify services are healthy
docker compose ps
```

### Run Database Migrations
```bash
docker compose exec -T backend alembic upgrade head
```

### Run Backend Unit and Integration Test Suite (30 Tests)
```bash
docker compose exec -T backend pytest -v
```

### Run Live End-to-End n8n Webhook Acceptance Suite (35 Assertions)
Exercises 10 synthetic fixtures, data minimization, duplicate detection, conflicting payloads, sanitized 422 errors, bounded 503 timeouts, and retry recovery:
```bash
python3 scripts/test_support_workflow.py
```

### Run API Smoke Test
```bash
python3 scripts/smoke_test.py
```

---

## 6. Workflow Architecture (Implementation 03)

The version-controlled workflow definition is stored at:
[`workflows/support_ticket_intake.json`](file:///home/adnan/projects/flowforge-ai/workflows/support_ticket_intake.json) and mounted into the n8n container at `/workflows/support_ticket_intake.json`.

### Reconciled 11-Node Canvas
1. `Webhook Trigger` (`node-webhook-01`): `POST /webhook/support-ticket-intake`
2. `Extract & Prepare` (`node-extract-02`): Sanitizes fields, extracts correlation ID and execution ID.
3. `Call FastAPI Backend` (`node-backend-03`): Synchronous HTTP call with 5s bounded timeout and `neverError: true`.
4. `Route Outcome` (`node-switch-04`): Evaluates HTTP status code (`201`, `200`, `409`, `422`, fallback/503).
5. `Format Created Outcome` (`node-fmt-created-05`): Normalized 201 JSON payload.
6. `Format Duplicate Outcome` (`node-fmt-dup-06`): Normalized 200 JSON payload with `duplicate: true`.
7. `Format Conflict Outcome` (`node-fmt-conf-07`): Normalized 409 JSON payload.
8. `Format Validation Outcome` (`node-fmt-val-08`): Clean field error messages without user text reflection.
9. `Format Unavailable Outcome` (`node-fmt-err-09`): Safe generic 503 fallback suppressing internal network topology.
10. `Respond to Webhook` (`node-respond-10`): Returns HTTP response and correlation headers immediately to client.
11. `Record Workflow Run` (`node-telemetry-11`): Asynchronous, non-blocking telemetry logging to `POST /api/workflow-runs`.

---

## 7. Remaining Tasks & Handover Notes for Codex

### A. Pending Safe Credential Rotation (Awaiting User Supervision)
During earlier development, a database password for role `n8n_app` was logged. All project files have been audited and verified secret-free. A safe rotation procedure has been formulated:
1. `ALTER ROLE n8n_app WITH PASSWORD '<new_password>';`
2. Update `N8N_DB_PASSWORD=<new_password>` in `.env`.
3. `docker compose restart n8n`
*(Do not execute without user confirmation).*

### B. Inactive Draft Workflows in n8n
Four empty/draft workflows exist in n8n from initial experiments:
- `wWjX3Bi5uRDyLzGu`, `4i5roR0oitA1bfbc`, `DKrWyiNmb2ph8c6w`, `MWeQoRSWGXVBxbBP`
To clean them up when approved:
```bash
docker compose exec n8n n8n delete:workflow --id=<workflow_id>
```

### C. Recommended Next Engineering Step: Implementation 04
Proceed with **Implementation 04: Bounded Local AI Enrichment using Ollama**.
- Container: Add local Ollama container or connect to host Ollama (`qwen2.5:7b-instruct` / `llama3.2`).
- Goal: Categorize incoming tickets, score sentiment/priority, and output structured JSON strictly matching Pydantic schemas.
- Ingress Guardrail: Fallback to `unknown` category if Ollama is unreachable or response schema violates bounds.\n