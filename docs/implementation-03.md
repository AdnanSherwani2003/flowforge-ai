# Implementation 03 — Deterministic support-ticket workflow

Updated 2026-10-22 after Codex engineering corrections.

**Implementation 03 is complete for its documented local portfolio scope. Authorized password rotation and stale-workflow unpublication succeeded; all required regression checks passed again. Implementation 04 has not started. See the [final maintenance record](implementation-03-review.md).**

## Architecture and published definition

FastAPI owns validation, business transactions, audit events, and idempotency. PostgreSQL is the business source of truth. n8n orchestrates requests and sends best-effort telemetry after responding.

- Workflow: FlowForge AI - Support Ticket Intake
- Published ID: FlowForgeSupportIntake01
- Verified published version: 32f4ea75-e33b-4941-b368-d89303e349d1
- Source: workflows/support_ticket_intake.json
- Production webhook: http://localhost:5679/webhook/support-ticket-intake
- Backend: http://localhost:8001; PostgreSQL is not exposed on a host port.
- Current migration: 003_workflow_runs_unique; no schema migration was needed for these corrections.

| Node | Responsibility |
| --- | --- |
| Webhook Trigger | Accept POST JSON; use Respond to Webhook for the response |
| Extract & Prepare | Preserve the original JSON payload; derive safe tracing and optional event metadata |
| Call FastAPI Backend | Forward original JSON and tracing headers; 5000 ms timeout; continue on HTTP/transport errors |
| Route Outcome | Branch on 201, 200, 409, 422; use fallback for unavailable/unexpected responses |
| Format Created Outcome | 201, created |
| Format Duplicate Outcome | 200, duplicate_replayed, original ticket ID |
| Format Conflict Outcome | 409, fixed safe conflict message |
| Format Validation Outcome | 422, sanitized field messages |
| Format Unavailable Outcome | 503, fixed safe message independent of upstream error detail |
| Respond to Webhook | Send JSON outcome and tracing/telemetry headers |
| Record Workflow Run | Send bounded allowlisted metadata after response; 3000 ms timeout; continue on errors |

Exactly 11 nodes. The published export matches repository nodes, connections, settings, name, ID, and active state.

## Validation and correlation contract

Original JSON is forwarded without stringifying individual fields or trimming them in n8n. Pydantic rejects numbers, booleans, null, arrays, objects, missing fields, and whitespace-only values in required string fields. Valid ticket strings still use backend whitespace trimming and existing length limits. Invalid top-level JSON shapes also return 422 consistently.

Correlation and execution IDs share backend TraceId: **1–100 ASCII characters from A–Z, a–z, 0–9, dot, underscore, colon, and hyphen**. Neither is silently truncated or normalized. The telemetry columns are already VARCHAR(100); audit identifiers live in JSON and receive the same validated values.

- Missing correlation ID: n8n generates corr-{execution_id}; direct API ingestion generates a UUID-based correlation ID.
- Present but invalid correlation ID: backend validation rejects with 422 **before ticket persistence**.
- n8n forwards the original client correlation header for validation. For rejected metadata it returns a new safe tracing ID and records correlation_rejected=true, without retaining the invalid value in application telemetry.
- Missing/invalid/oversized source event IDs do not get coerced into telemetry strings: metadata is null when invalid, with a bounded rejection flag where applicable. Original payload validation remains the backend's responsibility.
- All normal and uniqueness-recovery audit paths retain correlation_id and execution_id.
- 422 errors contain field/type/message, not Pydantic raw input or customer subject/body.

## Response and telemetry semantics

A successful webhook response confirms the business ticket was committed or replayed. It does not promise telemetry delivery.

Every formatted response includes:

```json
{
  "http_status_code": 201,
  "status": "accepted",
  "outcome": "created",
  "ticket_id": "<ticket UUID>",
  "source_event_id": "<validated event ID>",
  "duplicate": false,
  "correlation_id": "<safe correlation ID>",
  "execution_id": "<n8n execution ID>",
  "telemetry": "best_effort",
  "timestamp": "<ISO timestamp>"
}
```

Response headers are X-Correlation-ID, X-FlowForge-Execution-ID, and X-FlowForge-Telemetry: best-effort. Telemetry runs later in the same n8n execution; it is not a durable queue. A telemetry outage cannot retract an already delivered ticket response.

Workflow telemetry is idempotent on (workflow_name, execution_id). Its safe_detail accepts only bounded status/error-code enums and boolean flags: status, duplicate, error_code, correlation_rejected, source_event_id_rejected. Arbitrary metadata and raw error strings are rejected. Historical metadata is preserved.

## Privacy and retention

Customer subject/body are intentionally persisted in PostgreSQL tickets. They pass through n8n memory and internal HTTP requests. IDs are caller-controlled: callers must not put customer content or credentials in IDs.

Installed n8n 2.43.8 supports the following settings; these are active in FlowForge Compose and explicitly set on the intended workflow:

```yaml
EXECUTIONS_DATA_SAVE_ON_SUCCESS: "none"
EXECUTIONS_DATA_SAVE_ON_ERROR: "none"
EXECUTIONS_DATA_SAVE_ON_PROGRESS: "false"
EXECUTIONS_DATA_SAVE_MANUAL_EXECUTIONS: "false"
EXECUTIONS_DATA_PRUNE: "false"
```

The final flag disables age/count cleanup of historical records. The no-save policy still disposes of newly completed in-flight executions through n8n's supported lifecycle. No historical execution deletion was requested or executed.

Important limits:
- n8n can persist initial execution input while a run is in flight. Interrupted/crashed runs can leave data behind.
- Before global settings were recreated, test executions could be soft-deleted while their payload rows remained physically present. Those records were retained.
- Historical payloads, old error records, snapshots, and backups may contain customer content.
- Editor previews, browser state, pinning, manual changes to workflow saving settings, and exception diagnostics can retain or reveal data.
- New completed normal-operation acceptance runs left no execution_entity/execution_data rows after the active no-save/prune-disabled configuration.
- Application audit/telemetry retain approved identifiers and safe metadata; they do not deliberately store raw ticket subjects or bodies.

See [n8n execution settings](https://docs.n8n.io/hosting/configuration/environment-variables/executions/). Installed configuration and lifecycle code were also inspected; do not infer version-specific behavior solely from newer documentation.

## Fault isolation and reliability

Compose defaults failure simulation to false. The regular backend environment and instantiated settings are false. The normal workflow no longer maps a caller's simulate field/header to a backend test header. Ordinary callers cannot activate its hooks.

The misleading ASGI transport.abort simulation branch was removed. Genuine network faults now use scripts/fault_proxy.py exclusively in scripts/test_workflow_faults.py:

| Fault | Demonstrated transport/result | n8n outcome | Replay behavior |
| --- | --- | --- | --- |
| HTTP 503 | Real upstream HTTP 503 with a synthetic private-detail canary | Safe HTTP 503, service_unavailable; canary absent | First retry creates; following replay deduplicates |
| Refusal | Closed Docker-internal port; n8n records ECONNREFUSED | Same safe HTTP 503 | No ticket persisted |
| TCP reset | Established socket aborted with SO_LINGER(1,0); independent ECONNRESET probe and n8n ECONNRESET evidence | Same safe HTTP 503 | No ticket persisted |
| Request timeout | Proxy delays beyond the 5000 ms request bound; n8n records a transport timeout | Same safe HTTP 503, approximately 5 seconds | No ticket persisted |
| Timeout after commit | Proxy commits through the unchanged normal backend, then delays its response | Same safe HTTP 503, approximately 5 seconds | First replay returns 200 duplicate; exactly one ticket |
| Telemetry outage | Separate telemetry request receives HTTP 503 | Business response remains 201 with explicit best-effort semantics | Ticket committed; telemetry may be absent |

The harness runs the installed n8n image with a separate tmpfs SQLite database and a uniquely named synthetic proxy. It mounts no production volumes, uses no production credentials, and never enables normal backend simulation. Test-only execution data is retained until the disposable engine stops so transport codes can be inspected read-only.

CLI publishing in this version does not populate the default publication service's webhook registrations by itself. The disposable engine uses the installed supported N8N_USE_WORKFLOW_PUBLICATION_SERVICE=false startup-registration setting; the real instance keeps its default publication service. The workflow node behavior is shared, but this activation difference is an explicit coverage limitation. The harness waits for both readiness and route registration.

## Verification commands and results

Run suites sequentially with no unrelated ticket writers; persistence assertions compare ticket totals. Live synthetic application records are retained.

```bash
cd /home/adnan/projects/flowforge-ai
docker compose exec -T backend pytest -q
python3 scripts/test_support_workflow.py
# Equivalent normal suite:
python3 scripts/test_normal_workflow.py
python3 scripts/test_workflow_faults.py
python3 scripts/smoke_test.py
python3 scripts/verify_workflow_runtime.py
git diff --check
```

- Backend: 82 passing tests, including seven real PostgreSQL tests and forced six-request duplicate/conflict races.
- Normal webhook acceptance: 192 assertions, covering ten fixtures, primitive/container/missing/whitespace field types, invalid top-level shapes, correlation boundaries, telemetry, audit, persistence, idempotency, and disabled hooks.
- Isolated transport/telemetry faults: 36 assertions, including genuine reset and import/export round-trip verification.
- API smoke: all eight stages passed.
- Runtime verification: Compose/environment agreement, disabled simulation, matching published export, intended route owner, migration, ID column lengths, and telemetry uniqueness.
- Existing dependency deprecation warnings remain; no dependency upgrade was bundled.

## Workflow lifecycle and completed maintenance

The real workflow was edited and published using the authenticated n8n editor. Production CLI import was deliberately avoided because it deactivates imported workflows. Re-importing the source is not a harmless read-only operation. Use supported editor/API updates and publish only the intended ID.

Authorized maintenance on 2026-10-22 used the installed supported CLI to unpublish only wWjX3Bi5uRDyLzGu, followed by the planned n8n recreation. It is inactive with activeVersionId null. Its 11-node definition and three historical executions remain, along with the other three inactive drafts. The intended workflow remains published and owns the sole registered POST route.

The n8n_app password was rotated through hidden psql prompts, only its ignored .env entry was changed, and only FlowForge n8n was recreated using the existing image. Fresh TCP authentication accepts the replacement and rejects the previous password. Encryption key and volumes are unchanged. PostgreSQL and backend were not recreated. Both database backups were restore-tested in an isolated tmpfs PostgreSQL container before mutation; the volume/config backups remain protected outside Git.

All regression suites were rerun successfully after maintenance: 82 backend tests, 192 normal assertions, 36 isolated fault assertions and eight API smoke stages; zero failed/skipped. See [the maintenance report](implementation-03-review.md) for preservation counts, backup/recovery limits and Git checkpoint evidence.

Other known limits: unauthenticated localhost APIs/webhook, best-effort telemetry, shallow /health readiness, historical raw payload retention, and unpinned dependency ranges. Wider ingress requires authentication and an explicit retention policy.

Implementation 03 is ready for final acceptance in its stated scope after the authorized local checkpoint. Do not begin Implementation 04 or push/merge without the user's next instructions.
