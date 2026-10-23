# FlowForge AI

A local-first AI workflow automation platform built with n8n, FastAPI, PostgreSQL, Ollama, and Next.js.

## Project Goal

Automate repetitive business operations while retaining human approval, auditability, and failure recovery.

## Official Implementation Roadmap

1. **Implementation 01**: Local infrastructure setup (Verified).
2. **Implementation 02**: Data contracts, idempotent ticket ingestion, safe audit logging, and mock CRM APIs (Verified).
3. **Implementation 03**: Deterministic n8n support-ticket workflow orchestration (Complete and verified).
4. **Implementation 04**: Bounded local AI enrichment using Ollama (Complete; commit 491b719).
5. **Implementation 05**: Authenticated human approval and Next.js dashboard (Complete; commit 7625989).
6. **Implementation 06**: Deterministic lead intake and email deduplication (Complete and accepted for the local-first scope).
7. **Implementation 07**: Deterministic daily operations digest (Accepted; local commit e746ff6).
8. **Implementation 08**: Resilience and recovery (Accepted; local commit 973c408).
9. **Implementation 09**: Integrated testing/security (Accepted with documented exceptions for trusted-local development; uncommitted).

## Technology Stack

- **n8n Community 2.43.8**: Workflow orchestration (Dedicated host port 5679)
- **FastAPI**: Backend API & business logic (Host port 8001)
- **PostgreSQL 17**: Persistent application data (Internal port 5432)
- **SQLAlchemy 2.x & psycopg 3**: Database ORM and synchronous connection pooling
- **Alembic**: Versioned database migrations
- **Pydantic v2**: Strict data contracts & input validation
- **Docker Compose**: Local infrastructure
- **Ollama 0.40.8**: Existing local Windows runtime; pinned qwen2.5:3b-instruct model
- **Next.js, React, TypeScript, Tailwind CSS**: Reviewer dashboard
- **pytest, Vitest and Testing Library**: Automated testing

## Current Status

**Implementation 05 is running locally at [localhost:3000](http://localhost:3000).**
It provides an authenticated overview, review queue, original/AI comparison,
approval/rejection confirmations and durable decision history. Approval records
human review only; no external action or ticket-state mutation follows.

Implementations 01–06 are complete and published for the intended local-first scope.
Implementation 07 is accepted and checkpointed locally at e746ff6; it has not been pushed or merged.
Implementation 08 is checkpointed locally at 973c408.
Implementation 09 was accepted with documented exceptions on 2026-10-24 for trusted-local development only; it remains uncommitted and unstaged on implementation-09-testing-security.
Main/origin main remain 29aa141; no new push or merge.
See the [Implementation 09 acceptance report](docs/implementation-09.md) and
[security assessment](docs/security-review.md). Functional checks pass; platform
dependency findings, unauthenticated ingress and a five-autosave n8n history
discrepancy remain explicit acceptance limitations.
See [resilience evidence](docs/implementation-08.md) and the [local recovery runbook](docs/recovery-runbook.md).
See [Implementation 07](docs/implementation-07.md) for authenticated daily reports,
counting rules, the 09:00 schedule and missed-day recovery.
Implementation 04 is commit 491b719 and Implementation 05 is commit 7625989;
Implementation 06 adds the separate deterministic lead workflow. The accepted
history retains separate implementation commits and feature branches, with
fast-forward publication to main. See [Implementation 06](docs/implementation-06.md)
for lead behavior, preserved historical duplicates and acceptance evidence.

See [Implementation 05](docs/implementation-05.md) for local login setup,
architecture, security boundaries and acceptance. Existing
[Implementation 04](docs/implementation-04.md) documents local model setup and
[restart recovery](docs/implementation-04.md#windows-restart-and-unavailable-service-recovery).
The [Implementation 03 review](docs/implementation-03-review.md) records historical maintenance.

## Workflow Location

The reproducible workflow definition is version-controlled at:
- `workflows/support_ticket_intake.json`
- `workflows/lead_intake.json` — separate 11-node lead workflow
- `workflows/daily_operations_digest.json` — separate five-node daily schedule
- Workflows directory mounted read-only inside FlowForge n8n; support export at: `/workflows/support_ticket_intake.json`

## Service Addresses

| Service | Address |
| :--- | :--- |
| **Reviewer Dashboard** | http://localhost:3000 |
| **Daily Digest** | http://localhost:3000/digests |
| **FastAPI Core** | http://localhost:8001 |
| **API Documentation** | http://localhost:8001/docs |
| **FlowForge n8n** | http://localhost:5679 |
| **Process Liveness** | http://localhost:8001/health |
| **Database Readiness** | http://localhost:8001/ready |
| **Lead Webhook Endpoint** | http://localhost:5679/webhook/lead-intake |
| **Support Webhook Endpoint** | http://localhost:5679/webhook/support-ticket-intake |

---

## Operational Commands

### 1. Database Migrations
```bash
docker compose run --rm backend alembic upgrade head
```

### 2. Backend Unit and Integration Tests (233 tests)
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

### 6. Human Review

Open http://localhost:3000 and sign in as the configured reviewer. Passwords remain
in ignored local configuration. See [setup and demo](docs/implementation-05.md#local-setup-and-demonstration).

```bash
python3 scripts/test_review_integration.py
```

The 13-node n8n workflow is unchanged; completed enrichment creates a durable
review through FastAPI. No waiting n8n execution is needed.

### 7. Lead Intake

POST a fresh synthetic source_event_id, name and email to the lead webhook.
Replay returns the same lead; another event with the same normalized email returns
200 with duplicate_reason email and preserves existing details. Changed content
for a remembered event returns 409. See [contracts and demo](docs/implementation-06.md).

```bash
python3 scripts/test_lead_workflow.py  # 358 assertions, 20 scenarios
python3 scripts/test_lead_faults.py    # 36 isolated assertions
```

### 8. Daily Operations Digest

Sign in at http://localhost:3000/digests. Select a completed date to view or generate
a frozen report. Period activity and current backlog are displayed separately.
Repeated generation preserves the original report and timestamp. Backfill missed
days individually; a powered-off local n8n cannot run its 09:00 Asia/Kolkata job.
See [setup, authentication and exact counting rules](docs/implementation-07.md).

```bash
python3 scripts/test_digest_integration.py
python3 scripts/test_digest_faults.py
```

### 9. Resilience and Recovery

```bash
python3 scripts/test_recovery_stack.py
python3 scripts/test_resilience_regressions.py
```

The first command creates an isolated synthetic stack, uses a model stub and waits
for the actual 120-second inference lease. Only its labeled test containers and
network are removed. Private synthetic database artifacts are retained outside
Git; plaintext fixture configuration is removed. The second command reruns existing
suites against normal local services and preserves their synthetic records.
Run without competing inference. See the recovery runbook for safe operator steps.

### 10. Workflow Maintenance

Use the authenticated n8n editor or supported API to update and publish the intended stable workflow: `FlowForgeSupportIntake01`, `FlowForgeLeadIntake01` or `FlowForgeDailyDigest01`. Production CLI import is not a read-only check: it deactivates imported workflows. Do not unpublish or delete other workflows without approval.

Completed execution data is configured not to be saved. Manual/debug retention was observed for two digest runs; see Implementation 07 for evidence and limits. Ticket content is intentionally stored in the business database and may exist in transient/crashed n8n executions and historical records. Application telemetry retains allowlisted metadata and is best effort.

See [Implementation 03](docs/implementation-03.md) for contracts, privacy limits, fault coverage, and safe credential-rotation guidance. See [Implementation 04](docs/implementation-04.md) for current advisory AI behavior. See [Implementation 06](docs/implementation-06.md) for current lead behavior. See [Implementation 07](docs/implementation-07.md) for daily reporting. Implementation 08 adds bounded database waits, separate readiness, interrupted-enrichment recovery visibility and isolated restart tests. No Implementation 09 work has started.

This is an engineering portfolio project, not a commercial SaaS platform.


## Integrated verification and security review

From Ubuntu WSL, with normal FlowForge services, Linux Node/npm and the existing
Windows Ollama available, run sequentially without competing writers/inference:

```bash
python3 scripts/verify_system.py
python3 scripts/audit_dependencies.py
python3 scripts/audit_secrets.py
```

The verification command runs frontend tests/lint/types/build, existing backend
and live acceptance suites, isolated fault/recovery checks, integrated security
scenarios, published workflow parity and a disposable application restore.
It creates synthetic records and a protected backup outside Git. Scans report
findings separately; successful execution does not mean no vulnerabilities.
The restore uses a network-isolated new PostgreSQL instance, never normal data.

Request bodies are now bounded by actual bytes: backend 65,536; dashboard login
and decisions 4096; digest generation 1024. Oversize returns 413; malformed JSON
returns sanitized 422. Legacy unauthenticated ingestion remains a trusted-local
limitation, including browser-form writes through n8n. AI stays advisory and human
approval records a decision only.

Execution pruning does not control workflow-version compaction. An older
encrypted export has five autosaved versions absent from the current instance;
current definitions/published versions and retained executions still match.
See the report before changing retention or restoring history. Implementation 09
requires separate explicit Git checkpoint authorization; Implementation 10 has not started.


The [October 24 final exception investigation](docs/implementation-09-exception-review.md)
records the investigation supporting the user's **2026-10-24 acceptance with
documented exceptions**, strictly for trusted-local development. It
distinguishes autosave compaction from Community age pruning, preserves encrypted
evidence outside /tmp, enumerates each critical/high image finding and records
the remaining ingress/runtime risks. Implementation 09 remains uncommitted.


The three exceptions remain accepted risks, not resolved vulnerabilities.
[Open security and maintenance follow-ups](docs/implementation-09.md#m-open-security-and-maintenance-follow-ups)
carry the outstanding work forward. Acceptance does not authorize a Git commit,
push, merge or public production deployment.
