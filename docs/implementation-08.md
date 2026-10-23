# Implementation 08 — Resilience and recovery

Verified locally on 2026-10-23, Asia/Kolkata. Acceptance is pending.
Branch: `implementation-08-resilience-recovery`.
No Implementation 08 commit, push, merge or Implementation 09 work.

## A. Authorized Implementation 07 checkpoint

`e746ff6cd59eba100504f9c2ccb36ea22a261457`
`feat: add authenticated daily operations digests`

Verified the exact 39-file scope against the accepted manifest, inspected changes,
checked ignored configuration and staged secret variants/whitespace, and compared
all three published workflows with source before committing. The working tree was
clean after the commit, then the requested Implementation 08 branch was created.
Main and origin/main remain `29aa141`. Older evaluation JSON is historical evidence
of its original pre-acceptance verification; it was not rewritten to imply a new run.

## B–D. Overview, gaps and changes

Existing transport fault, idempotency, concurrency, strict model validation and
digest timezone coverage was extensive. This milestone adds recovery evidence,
not another business workflow or infrastructure service.

Three small runtime changes:

1. PostgreSQL connection establishment: 3 seconds; pool checkout: 2 seconds;
   server statement timeout: 5 seconds; lock timeout: 3 seconds. Pre-ping remains.
   Operational errors and pool exhaustion return sanitized 503 + Retry-After: 2.
   No write is automatically retried.
2. `GET /health` stays process liveness. `GET /ready` checks SELECT 1 against the
   required application DB and returns 200/503, no-store. Docker backend health
   uses readiness. Authenticated `GET /api/reviewer/dependencies` checks the
   configured local Ollama model name/digest using bounded /api/tags, with a
   two-second total deadline and 64-KiB response limit. It never generates a
   completion; optional AI does not gate unrelated functions.
3. When an interrupted processing lease expires, an explicit enrichment POST
   reconciles it to unavailable, creates an attention review and a safe
   `ticket_enrichment_interrupted` audit in the same transaction. Its old token
   cannot complete. GET remains read-only; retries remain explicit and capped.

Gaps discovered:

- Process health previously reported success during DB failure; connection/pool
  waits lacked explicit application settings.
- An expired claim could become unavailable without a visible attention review.
- Actual restart/pool recovery and review response loss lacked a combined drill.
- A ticket can commit before n8n dispatches enrichment. A crash in that gap leaves
  no enrichment row; duplicate intake correctly skips inference. Explicit /enrich
  repairs this case. An outbox/background sweeper is outside this focused scope.
- Local schedules skip missed runs and require deliberate one-day backfill.
- Connection and server timeouts do not establish a universal HTTP deadline for
  arbitrary network/OS suspension; ambiguous responses still require replay.

No migration, new dependency, paid service, model download, dashboard redesign,
new workflow, autonomous action or change to ticket/lead identity rules.

## E. Resilience and consistency matrix

| Failure scenario / component | Expected behavior and authority | Existing coverage | New coverage / recovery |
| --- | --- | --- | --- |
| DB unavailable / FastAPI | 503, no fabricated success; committed business DB rows authoritative | Mock operational errors, uniqueness/concurrency | Actual isolated PG stop/start, readiness vs liveness, same backend pool recovers; restore DB availability and replay identity |
| DB session lost after flush | Ticket and audit commit together or neither | Existing transaction structure | Real pg_terminate_backend injected between flush and audit in isolated DB; 503, zero partial rows, same event succeeds on retry |
| Slow SQL / pool exhaustion | Bounded wait, rollback, usable connection afterward | Limited explicit timing evidence | Actual pg_sleep cancellation near 5s; real full pool times out near 2s; recover connection and retry deliberately |
| Ticket response lost / n8n | source_event_id resolves same ticket; changed payload conflicts | Support after-persist timeout/reset fault suite | Existing suite rerun; no exactly-once network claim |
| Lead response lost / n8n | Event ledger/email identity resolves canonical lead | Lead after-persist and concurrent duplicates | Existing suite rerun, same identity survives isolated n8n restart |
| n8n restart | Published versions/paths persist; business records independent | Read-only runtime export checks | Real isolated restart with same storage, no reimport, exact exports and original webhook replays; normal production PG-backed n8n not interrupted |
| Ticket committed, AI dispatch absent | Ticket valid, enrichment GET 404 | Only new tickets trigger AI | Simulated missing-dispatch boundary, actual duplicate webhook skips AI, explicit POST creates result |
| Optional Ollama unavailable | Ticket 201, explicit unavailable result, other services ready | Mock transports, real local model integration | Stop/start disposable upstream; model-metadata diagnostics; concurrent explicit recovery adds one attempt |
| Backend interrupted mid-inference | Durable processing lease, stale completion blocked | Unit stale-token and lease tests | Real backend kill/restart during HTTP inference, real 120-second expiry, attention review and one audit, cap of 3 attempts |
| Invalid AI / advice | Reject invalid output, no generated instruction execution | Strict schema, bounded output, injection/tool-call tests | Existing backend and pinned real-model regressions rerun; no action mechanism added |
| Dashboard offline / stored suggestion | Enrichment and Review survive without browser | Auth/review API and UI tests | Actual Next restart, relogin/refresh recover durable history; pending forms are not committed decisions |
| Review committed, browser response lost | Immutable Review + atomic audit authoritative | Identical/conflicting decisions and PostgreSQL races | TCP connection closed after successful Next/backend commit; replay preserves timestamp, one final audit; backend auth authoritative |
| Digest generated, response lost | Date/timezone unique frozen report authoritative | Digest after-persist timeout and PostgreSQL concurrency | Existing faults rerun; concurrent reviewer/service-key replays preserve original metrics/time |
| Scheduler offline | Skip missed jobs; no bulk catch-up | Real accelerated isolated timer, timezone/DST tests | Restart produces no historical backfill; manual yesterday/default and explicit old-date backfill; existing historical reports unchanged |
| Telemetry fails after business commit | Business rows authoritative; workflow_runs best effort | Existing support/lead/digest faults | Rerun all faults; inspect entity first, never fabricate telemetry or recreate business data |

The operation may have committed when a client sees a timeout/disconnect. Retry
the same event/decision/date, inspect the authoritative record, and distinguish
safe replay from a new operation. A suggestion stored while Next is offline needs
only reload/relogin; unavailable/missing AI needs explicit recovery; missed reports
need manual generation. Missing telemetry does not invalidate accepted business data.

## F–G. Executed tests and regressions

| Suite | Passed | Failed | Skipped |
| --- | ---: | ---: | ---: |
| Backend (214 prior + 8 recovery tests) | 222 | 0 | 0 |
| Frontend | 33 | 0 | 0 |
| New isolated restart/recovery stack | 49 | 0 | 0 |
| Support webhook | 192 | 0 | 0 |
| Lead webhook | 358 | 0 | 0 |
| Real local Ollama enrichment | 21 | 0 | 0 |
| Human review integration | 29 | 0 | 0 |
| API smoke | 8 | 0 | 0 |
| Digest API/Next integration | 28 | 0 | 0 |
| Isolated digest faults and schedule timer | 44 | 0 | 0 |
| Isolated lead faults | 36 | 0 | 0 |
| Isolated support faults | 39 | 0 | 0 |

Frontend lint and TypeScript checks passed. Backend image build passed.
Production publication/migration/runtime verification passed. Live /health and
/ready returned 200; optional diagnostic required auth (401 without it) and
reported the actual pinned local model available. Windows Ollama listener was
127.0.0.1:11434. Backend still connects through host.docker.internal.

The new stack uses real PostgreSQL 17, built FastAPI/Next images and installed
n8n 2.43.8 in a dedicated test network. n8n storage is SQLite in this disposable
fixture; normal n8n remains PostgreSQL-backed. The local Ollama HTTP fixture
simulates valid metadata/completions, process outage and delayed inference.
It is **not** evidence of model quality or real Windows-process restart.
Lease expiry waits the actual 120 seconds without changing clocks or rows.
The mid-transaction injection terminates only its own isolated PG session.
The missing-dispatch test deliberately represents the boundary with a direct
ticket insert API call, not a claim that an actual n8n crash was timed there.

Run corrections before the final green results: fixed a unit-test monkeypatch
target; replaced unsupported n8n publish --all with explicit stable IDs; used a
valid synthetic example.com email; rediscovered ephemeral host ports after
container restart; read final decided_at from the authoritative backend rather
than the intentionally minimal Next response. Fixed the regression runner's
success-text marker for the lead suite. Initial attempts were incomplete/failed
and are not reported as successful acceptance runs. The final 49-check run and
all regression rows above actually executed.

The new harness removes only uniquely labeled test containers and its network;
it removes plaintext fixture configuration and retains private synthetic DB
artifacts under /tmp/ff-recovery-* outside Git. No normal volume is attached.
Earlier milestone evaluation files remain unchanged. Current results:
`docs/evaluation/implementation-08-*.json`.

## H. Preservation

Fresh pre-change business-row hashes compared with final rows: zero missing or
changed original rows across all nine application tables. New synthetic test
records remain. Existing frozen digest rows are byte-value preserved.

All seven complete workflow exports are identical: three active workflows and
four inactive drafts. Supported encrypted n8n entity exports were privately
decrypted in memory: all 335 execution entities, 335 execution-data rows and the
one credential match retained Implementation 07 export hashes, with zero missing
or changed rows. No direct n8n PostgreSQL access or mutation was used.

All 20 existing containers accounted for. Only the normal backend was recreated;
the other 19 retain their IDs, images and start timestamps. Original mount
definitions and ignored .env bytes are unchanged. Other container environment
hashes are unchanged; recreated backend values match unchanged Compose settings
(after normalizing Compose's dollar escaping). Personal n8n still has 37 workflows,
counted through a read-only mount. Reviewer/database/encryption credentials,
SentinelPOMDP, Neo4j, original n8n and all persistent Docker volumes are preserved.

## I. Changed files

See the exact manifest in `evaluation/implementation-08-acceptance.json`.
Runtime changes: database bounds, system routes, sanitized errors, lease recovery,
backend Docker healthcheck. Tests: eight backend tests, isolated fixture/harness,
regression runner and optional digest-suite output paths. Documentation: this
report, recovery runbook, README/handover and sanitized evaluation evidence.

## J–K. Security and remaining limits

- Loopback exposure remains; PostgreSQL has no host port. Optional diagnostics
  require the existing reviewer session and return categorical states only.
- No credentials, raw customer text, model responses or internal traces added to
  telemetry. Recovery audit holds only enrichment ID/status/diagnostic code.
- There is no automatic enrichment sweeper/outbox or write retry. Explicit retries
  may exhaust their existing cap; manual handling then remains necessary.
- Historical/manual n8n data may contain prior payloads; it is preserved rather
  than claiming erasure. Existing local legacy intake/telemetry trust boundaries
  remain unsuitable for public deployment.
- No full Windows/WSL/Docker Desktop reboot, production n8n interruption,
  production DB interruption, actual Windows Ollama kill, database restore,
  arbitrary packet-blackhole test, load/soak or production security certification.
  These are not test skips; they were outside the executed suites.
- DB server/pool deadlines bound common waits, not every possible OS/network stall.
  Per-call network ambiguity remains; there is no exactly-once delivery guarantee.
- Backend suite retains 106 existing library deprecation warnings.
- Implementation 09 remains reserved for consolidated testing/security review.

## L–N. Git, proposed checkpoint and manual actions

Implementation 08 remains unstaged and uncommitted on its requested feature branch.
No push or merge. Main/origin main stay 29aa141; Implementation 07 branch stays at
e746ff6. Suggested later commit:

`feat: add bounded resilience checks and explicit recovery`

No setup, migration, credential change or model download is required on this
machine. Review this acceptance report before authorizing an Implementation 08
commit. For an actual offline incident, follow [the recovery runbook](recovery-runbook.md);
request-driven AI recovery and individual digest backfill require an operator.
Host reboot and restore drills remain separately planned/manual procedures.

## Reproduce

```bash
docker compose build backend frontend
docker compose up -d --no-deps --force-recreate backend
python3 scripts/test_recovery_stack.py
python3 scripts/test_resilience_regressions.py
python3 scripts/verify_workflow_runtime.py
# With a Linux Node runtime:
cd frontend
npm test
npm run lint
npm run typecheck
```

`--resume` on the regression runner reuses only already recorded successful suites
from this milestone; omit it for a fresh complete run. Use explicit --output paths
on digest/lead/review suites to preserve prior milestone evidence. Run sequentially
without competing Ollama inference. Each normal integration run retains synthetic
records; the isolated restart suite does not modify production services.
