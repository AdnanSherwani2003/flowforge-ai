# FlowForge AI — Codex Handover Documentation

## Current checkpoint — 2026-10-24

Implementation 09 is committed at
`64f7a477253f000b60b202ecba44c136dd76e59a`, accepted with documented exceptions
for trusted-local use. Implementation 10 has received final acceptance with
documented exceptions. The user explicitly authorized its local commit,
fast-forward integration into `main` and publication of the 07–10 branches and
`main`. The release is based on that clean 09 checkpoint; see Git for final SHAs.
No release tag, public runtime deployment or additional implementation is authorized.

Read the [current roadmap](roadmap.md), [developer setup](developer-setup.md),
[architecture](architecture.md), [demos](portfolio-demos.md),
[fresh benchmark evidence](benchmark-report.md) and
[Implementation 10 report](implementation-10.md). The separate portfolio lab
imports copies into new storage only; its default model is an explicitly labelled
controlled fixture. Original services/configuration/workflows are preserved.

Earlier status sections below are historical handoff snapshots. In particular,
Implementation 09's old uncommitted/no-Git-authorization text predates its later
authorized local checkpoint. All three security exceptions and seven follow-ups
remain open. Approval records decisions only; customer delivery/actions are not
implemented. Do not describe a future delivery gate as existing functionality.

Welcome to **FlowForge AI**! This document provides the engineering context, runtime architecture, verification commands, and safety boundaries required for OpenAI Codex to seamlessly continue development.

---

## 1. Project Purpose & Philosophy

FlowForge AI is a **local-first AI workflow automation platform** designed to automate repetitive business operations while strictly maintaining **human approval, auditability, data minimization, and deterministic failure recovery**.

Core Architectural Principles:
1. **Local-First & Zero Paid Cloud Dependencies**: Uses Docker Desktop for application services and an existing native Windows Ollama for local inference; no paid inference dependency.
2. **FastAPI & PostgreSQL as the Source of Truth**: n8n serves exclusively as an orchestrator and integration router. All schema validation, idempotency checks, conflict resolution, and data persistence reside firmly in FastAPI and PostgreSQL.
3. **Data Minimization & Privacy**: Ticket content is intentionally stored in business tables and passes through n8n memory. Validation errors omit raw inputs; audit/telemetry use bounded identifiers and allowlisted metadata. New completed workflow payloads are not retained under the configured no-save policy, but historical/crashed executions and backups can contain raw content. Execution-data pruning is disabled; independent workflow-version compaction is a separate unresolved preservation exception documented in Implementation 09.
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
- **Release Branches**: `main` and retained `implementation-10-portfolio-release`; verify current branch/tip with Git before further work.

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

**Current status:** All ten implementations have final functional acceptance
for the trusted-local portfolio scope. The authorized final Git release
integrates 07–10 after 29aa141, preserving e746ff6, 973c408 and 64f7a47 plus the
separate Implementation 10 commit. Latest migration is 007_daily_digests;
08/09/10 add no migration.
Three published support/lead/digest workflows have 13/11/5 nodes; four drafts stay
inactive. Failure simulation is false. The final release changes Git only.
Read [Implementation 09](implementation-09.md), [security review](security-review.md)
and [recovery runbook](recovery-runbook.md) before further work. Implementation
09 is accepted with documented exceptions for trusted-local development only.
The platform findings, unauthenticated ingress and history-version gap remain
open risks, not resolved vulnerabilities. Final Git publication is authorized;
public production deployment remains unauthorized.

### Official Implementation Roadmap
1. [x] **Implementation 01**: Local infrastructure setup (Docker Compose, networking, multi-role PostgreSQL).
2. [x] **Implementation 02**: Data contracts, idempotent ticket ingestion, safe audit logging, and mock CRM APIs.
3. [x] **Implementation 03**: Deterministic n8n support-ticket workflow orchestration (Complete for the documented local scope).
4. [x] **Implementation 04**: Bounded local advisory enrichment using Ollama (local commit 491b719).
5. [x] **Implementation 05**: Authenticated human approval dashboard (published).
6. [x] **Implementation 06**: Lead intake and deduplication.
7. [x] **Implementation 07**: Daily operations digest (e746ff6).
8. [x] **Implementation 08**: Resilience/recovery (973c408).
9. [x] **Implementation 09**: Testing/security; accepted with documented exceptions for trusted-local development (64f7a47).
10. [x] **Implementation 10**: Developer handoff, reproducible portfolio demos and final release preparation; accepted with documented exceptions.

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

### Run Backend Unit and Integration Test Suite (233 Tests)
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
Implementation 07 is now accepted and locally checkpointed; see the current status below.

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
29aa141 and was accepted and locally committed as e746ff6cd59eba100504f9c2ccb36ea22a261457.
It remains unpushed/unmerged. Migration 007_daily_digests is applied;
FlowForgeDailyDigest01 is separately published with five nodes, 09:00 Asia/Kolkata.
The authenticated /digests page provides frozen reports and one-day backfill.
Read [Implementation 07](implementation-07.md) for exact metrics, scoped credential
provisioning, timezone alignment, offline recovery and retention observations.

Existing reviewer credentials/encryption keys are preserved. Only a new narrowly
scoped generation key and encrypted n8n header credential were added.
### E. Implementation 08 checkpoint and Implementation 09 review

Implementation 08 was accepted and locally committed as 973c408 after its
24-file manifest, whitespace and staged secret review. A clean tree was verified
before creating implementation-09-testing-security. Implementation 09 is
uncommitted/unstaged. Main/origin main remain 29aa141. Do not push/merge or begin 10.

Implementation 09 adds bounded actual-byte request parsing, safe malformed JSON
errors, no-store legacy responses, the SQLite pool compatibility correction,
private pytest temp roots and reproducible security/restore/scanner procedures.
Runtime pip/npm installers were removed; existing app package versions remain.

The final sequential system command passed backend 233, frontend 44, recovery 49,
support 192, lead 358, enrichment 21, review 29, smoke 8, digest 28, digest faults 44,
lead faults 36, support faults 39, integrated security 43 and restore 13 check groups;
each has zero failures/skips. Lint/typecheck/build/runtime parity passed.
Dependency scans still report pytest plus platform image findings; no clean
security sign-off. See full evidence/commands in Implementation 09.

All original app row hashes match except the user's explicitly confirmed
approval of review ca7a03ff-1540-4e72-95cf-a6fb3364d660 during testing.
Do not undo it. Current seven workflow definitions and retained executions/
credential match; five autosaved workflow-history versions are absent relative
to the older encrypted export. Independent n8n compaction is consistent with this,
but timing/cause is unproven. Preserve the prior export and resolve the retention
exception through approved maintenance, never direct table writes.

Only normal backend/frontend were recreated. Other 18 original containers,
all mounts/.env bytes and personal n8n's 37 workflows were verified unchanged.
A fresh application-only backup was restored into a disposable isolated instance;
normal restore/n8n restore/full Windows reboot/ownership recovery are untested.


### F. Implementation 09 final exception investigation

October24 final decision: **ACCEPTED WITH DOCUMENTED EXCEPTIONS** by the user,
strictly for trusted-local development. The three exceptions remain accepted
risks, not resolved vulnerabilities. No commit/push/merge is authorized. Read
[the final exception report](implementation-09-exception-review.md) and its
92-row critical/high catalog before maintenance. All original41 files were
reviewed; total proposal is44 after three new report/evidence files.

Offline compaction selects four missing versions. Community's separate24-hour
pruning rule makes all four support autosaves eligible, including the24-node
intermediate draft; no log proves the exact historical task. Protected encrypted
archive copies now preserve old/current evidence outside /tmp. Do not modify
original history or restore an old draft over the published13-node workflow.

n8n Node26.7.0 remains below fixed26.12.1; bundled runtime patch qualification is
a High priority. Most native/feature/tooling preconditions are absent from the
current fixed workflows; do not extend that conclusion to arbitrary editor use.
Frontend Node22.23.4 already includes the Brotli backport.
Unauthenticated local ingress remains Medium; current approval enforcement stays.
Backend233/frontend44/smoke8/ingress17 and runtime parity passed again. Other
full suites remain the previous evidence, not newly executed claims.


### G. Carry-forward work after Implementation 09 acceptance

Use the stable IDs in the
[open follow-up register](implementation-09.md#m-open-security-and-maintenance-follow-ups):
FF09-SEC-01 (platform/runtime patches), FF09-HIST-01 (history retention/backup),
FF09-INGRESS-01 (sender authentication/resource limits), FF09-TEST-01 (pytest),
FF09-AUTH-01 (session/TLS/identities), FF09-REC-01 (remaining recovery drills) and
FF09-BUILD-01 (build reproducibility). All remain open. No maintenance, feature
work, public deployment or Git operation is implied by acceptance.
Retain all investigation evidence and encrypted history backups.
