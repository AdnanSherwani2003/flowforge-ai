# FlowForge AI — Codex Handover Documentation

Welcome to **FlowForge AI**! This document provides the engineering context, runtime architecture, verification commands, and safety boundaries required for OpenAI Codex to seamlessly continue development.

---

## 1. Project Purpose & Philosophy

FlowForge AI is a **local-first AI workflow automation platform** designed to automate repetitive business operations while strictly maintaining **human approval, auditability, data minimization, and deterministic failure recovery**.

Core Architectural Principles:
1. **Local-First & Zero Paid Cloud Dependencies**: Uses Docker Desktop for application services and an existing native Windows Ollama for local inference; no paid inference dependency.
2. **FastAPI & PostgreSQL as the Source of Truth**: n8n serves exclusively as an orchestrator and integration router. All schema validation, idempotency checks, conflict resolution, and data persistence reside firmly in FastAPI and PostgreSQL.
3. **Data Minimization & Privacy**: Ticket content is intentionally stored in business tables and passes through n8n memory. Validation errors omit raw inputs; audit/telemetry use bounded identifiers and allowlisted metadata. New completed workflow payloads are not retained under the configured no-save policy, but historical/crashed executions and backups can contain raw content. Periodic pruning is disabled to preserve historical records.
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
- **Active Branch**: `implementation-05-human-approval-dashboard` (uncommitted; do not commit/push without approval)

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

**2026-10-23 current status:** Implementation 03 was fast-forward merged and pushed to main at 1489752 after regression verification. Implementation 04 is committed locally as 491b719. Implementation 05 is verified locally and awaiting review, with no push or merge. Migration 005_reviews and the unchanged 13-node workflow are live. Dashboard: http://localhost:3000. Published version: 4a1f9756-89ab-488c-9348-f9fb51e0966e. Failure simulation remains false.

See [Implementation 05](implementation-05.md) for current review contracts and [Implementation 04](implementation-04.md) for inference measurements.
The [Implementation 03 maintenance report](implementation-03-review.md) remains historical evidence of completed rotation; no credentials or keys changed during Implementation 04.

### Official Implementation Roadmap
1. [x] **Implementation 01**: Local infrastructure setup (Docker Compose, networking, multi-role PostgreSQL).
2. [x] **Implementation 02**: Data contracts, idempotent ticket ingestion, safe audit logging, and mock CRM APIs.
3. [x] **Implementation 03**: Deterministic n8n support-ticket workflow orchestration (Complete for the documented local scope).
4. [x] **Implementation 04**: Bounded local advisory enrichment using Ollama (local commit 491b719).
5. [x] **Implementation 05**: Authenticated human approval dashboard (verified, uncommitted).
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

### Run Backend Unit and Integration Test Suite (159 Tests)
```bash
docker compose exec -T backend pytest -v
```

### Run Live End-to-End n8n Webhook Acceptance Suite (192 Assertions)
Exercises normal-operation fixtures, type and top-level shape parity, correlation boundaries, sanitized validation, idempotency, tracing and telemetry. Fault testing is separate and never enables regular backend simulation:
```bash
python3 scripts/test_support_workflow.py
```

### Run Isolated Transport Faults and Runtime Verification
```bash
python3 scripts/test_workflow_faults.py
python3 scripts/verify_workflow_runtime.py
```
The isolated suite has 39 assertions and uses disposable test containers without production volumes/credentials. Run suites sequentially; synthetic application records remain.

### Run API Smoke Test
```bash
python3 scripts/smoke_test.py
```

---

## 6. Workflow Architecture (Implementation 03 with advisory extension)

The version-controlled workflow definition is stored at:
[`workflows/support_ticket_intake.json`](../workflows/support_ticket_intake.json) and mounted into the n8n container at `/workflows/support_ticket_intake.json`.

### Current 13-Node Canvas
1. `Webhook Trigger` (`node-webhook-01`): `POST /webhook/support-ticket-intake`
2. `Extract & Prepare` (`node-extract-02`): Preserves original JSON types, derives bounded safe tracing and optional event metadata.
3. `Call FastAPI Backend` (`node-backend-03`): Synchronous HTTP call with 5s bounded timeout and `neverError: true`.
4. `Route Outcome` (`node-switch-04`): Evaluates HTTP status code (`201`, `200`, `409`, `422`, fallback/503).
5. `Format Created Outcome` (`node-fmt-created-05`): Normalized 201 JSON payload.
6. `Format Duplicate Outcome` (`node-fmt-dup-06`): Normalized 200 JSON payload with `duplicate: true`.
7. `Format Conflict Outcome` (`node-fmt-conf-07`): Normalized 409 JSON payload.
8. `Format Validation Outcome` (`node-fmt-val-08`): Clean field error messages without user text reflection.
9. `Format Unavailable Outcome` (`node-fmt-err-09`): Safe generic 503 fallback suppressing internal network topology.
10. `Respond to Webhook` (`node-respond-10`): Returns HTTP response and correlation headers immediately to client.
11. `Record Workflow Run` (`node-telemetry-11`): Post-response, best-effort telemetry logging to `POST /api/workflow-runs`.
12. Only Newly Created Tickets: If node checks original response outcome after telemetry.
13. Request Advisory Enrichment: bounded 35-second POST to FastAPI; errors continue without affecting the already-delivered response.

FastAPI persists a separate versioned advisory row and never changes original ticket state.
GET /api/tickets/{id}/enrichment reads it; POST /api/tickets/{id}/enrich requests it.
See Implementation 04 for retry/lease semantics and local model setup.


---

## 7. Remaining Tasks & Handover Notes for Codex

### A. Completed Credential Rotation

Explicitly authorized maintenance on 2026-10-22 rotated only n8n_app through hidden psql password prompts. Fresh TCP authentication verified acceptance of the new password and rejection of the previous password. Only N8N_DB_PASSWORD changed in the ignored, mode-0600 .env; the existing encryption key is preserved.

FlowForge n8n was stopped, its sessions quiesced, and it was recreated with the existing image using `docker compose -p flowforge-ai up -d --no-deps --force-recreate --no-build --pull never n8n`. Restart alone does not reload environment variables. PostgreSQL and backend were not recreated. The old initialization-only password in PostgreSQL container environment is inactive and was not refreshed because recreation was prohibited.

Protected database, volume and environment backups are outside Git; both database dumps were actually restore-tested without production mounts/network. See [maintenance evidence and recovery limits](implementation-03-review.md).

### B. Preserved Historical Workflows

Only wWjX3Bi5uRDyLzGu was unpublished with the installed supported CLI, followed by the authorized n8n recreation. Its definition and all three historical executions remain. It and the three other historical drafts are inactive:

- wWjX3Bi5uRDyLzGu — 11 nodes
- 4i5roR0oitA1bfbc — 11 nodes
- DKrWyiNmb2ph8c6w — 11 nodes
- MWeQoRSWGXVBxbBP — 2 nodes

FlowForgeSupportIntake01 is now published with 13 nodes and sole ownership of the intended webhook. No other publication state changed. Do not delete or archive these records.

### C. Completed Implementations 01–06 and publication

Implementation 04 received local commit 491b719 before branching.
Implementation 05 received authorized local commit 7625989 (63 files).
Implementation 06 is complete and accepted on implementation-06-lead-intake.
The user authorized its local checkpoint, fast-forward of main, and normal pushes
of main and the 04–06 implementation branches. Preserve separate commits and all
branches; never force-push, reset or rewrite history. Read
[Implementation 06](implementation-06.md) for acceptance and limits.
Implementation 07 remains planned; do not begin without new instructions.

Lead workflow FlowForgeLeadIntake01 is separately published with 11 nodes at
POST /webhook/lead-intake. Additive migration 006_lead_intake preserves historical
lead IDs and duplicates while introducing event/email identity registries. The
existing 13-node support workflow is unchanged.

Reviewer configuration is in ignored mode-0600 .env; never print passwords.
Next.js on localhost:3000 is a server-side presentation layer; FastAPI enforces
every review operation. n8n and Ollama contracts are unchanged. Reviews use durable
PostgreSQL rows rather than waiting n8n executions.

### D. Implementation 07 local acceptance

Implementation 07 is developed on implementation-07-daily-operations-digest from
29aa141 and remains uncommitted/unpushed. Migration 007_daily_digests is applied;
FlowForgeDailyDigest01 is separately published with five nodes, 09:00 Asia/Kolkata.
The authenticated /digests page provides frozen reports and one-day backfill.
Read [Implementation 07](implementation-07.md) for exact metrics, scoped credential
provisioning, timezone alignment, offline recovery and retention observations.

Existing reviewer credentials/encryption keys are preserved. Only a new narrowly
scoped generation key and encrypted n8n header credential were added.
Do not commit, push, merge or begin Implementation 08 without new authorization.
