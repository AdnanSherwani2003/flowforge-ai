# Local recovery runbook

Scope: local Docker Desktop + Ubuntu WSL2 installation. Run Linux commands from
/home/adnan/projects/flowforge-ai. Keep .env private (0600 and ignored).
Personal n8n at 5678, SentinelPOMDP, Neo4j and all existing volumes are outside
these procedures. Never use volume deletion, database resets, pruning or direct
writes to n8n tables.

## Startup after Windows restart

1. Start Docker Desktop; wait for its engine. Open Ubuntu WSL and run `docker info`.
2. In the repository run `docker compose up -d`. Existing volumes are reused.
   For already initialized services, migrations remain at 007_daily_digests.
   Do not rerun provisioning or import existing workflows as a startup step.
3. Run `docker compose ps`; PostgreSQL, backend and frontend should be healthy.
   n8n currently has no Compose healthcheck; check
   `curl --fail http://localhost:5679/healthz/readiness` separately.
4. Check `curl --fail http://localhost:8001/health` (process alive) and
   `curl --fail http://localhost:8001/ready` (required database available).
   Docker backend health now uses /ready. An unhealthy dependency does not make
   Compose automatically restart services or rerun transactions.
5. Sign in at localhost:3000. Existing browser sessions may expire; relogin.
   Sign-in uses the existing reviewer credentials, never a new account.

**Evidence:** clean startup, migrations and individual component restarts tested
in isolated infrastructure. A full Windows/Docker Desktop/WSL reboot was not
performed in Implementation 08; the host startup sequence is documented.

Changed environment values require `docker compose up -d --no-deps --force-recreate backend`
(or the specifically affected service). `restart` retains the existing environment.
Do not recreate the normal n8n to test interruption. Credential rotation is a
separate approved procedure from Implementation 03.

## Identify readiness problems

| Signal | Meaning | Response |
| --- | --- | --- |
| /health 200, /ready 503 | Backend alive, required DB unavailable | Inspect scoped PostgreSQL state; restore availability, retry same operation |
| /health fails | Backend process unavailable | Inspect `docker compose logs --tail 100 backend`, start only that service |
| /ready 200, enrichment unavailable | Optional AI problem | Check Windows Ollama; intake/reviews/digests remain usable |
| Dashboard login works but data fails | Next alive, backend/auth/DB may be unavailable | Check backend readiness, relogin, reload authoritative record |
| n8n readiness 200, webhook fails | Workflow may be unpublished or wrong owner/path | Verify published definitions and normalized outcome |

Authenticated GET /api/reviewer/dependencies uses the existing bearer session.
It checks only local /api/tags with a two-second total deadline and a bounded
response, verifies the configured name/digest, and returns available,
model_unavailable, unavailable or disabled. It does not load/generate a model.
Do not paste bearer tokens or credentials into shared logs. No upstream body,
database URL or exception trace is returned. Optional AI does not gate /ready.

Database connections use a three-second establishment timeout, two-second pool
checkout timeout, five-second server statement timeout and three-second lock
timeout. Pool exhaustion and operational failures return sanitized 503 with
Retry-After: 2. There is no automatic replay of writes. These bounds are not a
universal HTTP deadline: OS DNS/network stalls or a suspended DB process can
outlast server-side timeouts. Caller timeouts can leave an ambiguous commit;
inspect/replay the same identity rather than assume rollback.

## n8n webhook ownership and restart

Run `python3 scripts/verify_workflow_runtime.py`. This uses supported read-only
CLI exports and application-schema checks; no direct n8n database access.
Expected owners and source sizes:

- FlowForgeSupportIntake01: /webhook/support-ticket-intake, 13 nodes.
- FlowForgeLeadIntake01: /webhook/lead-intake, 11 nodes.
- FlowForgeDailyDigest01: 5 nodes, 09:00 Asia/Kolkata.

Four inactive drafts remain preserved. Test webhooks are not production paths.
Review normalized outcomes: a completed n8n execution alone does not prove
business success. Production CLI import deactivates imported workflows; never
use it to repair an already published workflow casually. Use the authenticated
editor and publish only an authorized change, then synchronize the export.

If the scoped production n8n actually stops, `docker compose start n8n` reuses
storage and configuration. Restart recovery was tested with identical workflow
definitions in a disposable SQLite-backed n8n, including a real restart and
webhook replay. Normal n8n uses PostgreSQL; its restart was deliberately not
forced. Read-only production publication/export parity is checked separately.

## Windows Ollama

Use the existing Windows Ollama application/startup entry. If the tray app is
not running, start Ollama from the Start menu. A terminal alternative is
`ollama serve` with the existing local configuration; do not launch a second
server if one already owns 11434. Do not change OLLAMA_HOST to a public bind.

Windows PowerShell: `ollama list`. Expected local identifier:
`qwen2.5:3b-instruct` and SHA-256
`357c53fb659c5076de1d65ccb0b397446227b71a42be9d1603d46168015c9e4b`.
No new pull/download is required. Do not delete model files.
Backend route remains http://host.docker.internal:11434. Check the authenticated
dependency diagnostic from the backend path; WSL localhost alone is not proof.

Actual pinned-model enrichment/review regressions are run separately from the
resilience harness's model stub. Stopping the real Windows process and a full
Windows reboot were not performed. Upstream process outage/recovery was tested
against a disposable HTTP service.

## Interrupted and unavailable enrichment

The ticket is authoritative and committed before advisory inference.
If GET enrichment returns 404 after an accepted ticket, n8n may have stopped
between its response and the enrichment call. Duplicate intake deliberately skips
AI. Inspect the ticket, then explicitly POST its /enrich endpoint once to create
the missing result. There is no outbox or automatic repair of this dispatch gap.
A successful ticket webhook does not promise completed AI enrichment.
GET /api/tickets/{ticket_id}/enrichment reads the current result; GET is read-only.
A processing response uses HTTP 202 and Retry-After: 2 on POST.

A backend interruption can leave a durable processing lease. Wait 120 seconds;
POST /api/tickets/{ticket_id}/enrich (without retry flag) reconciles an expired
lease to unavailable/lease_expired, creates an attention review and a safe audit.
Recovery is request-driven, not a background sweeper; GET/refresh alone does not
expire the lease. The old lease token cannot publish a late result.

After fixing Ollama, explicitly POST the same endpoint with
`?retry_unavailable=true`. At most three total attempts are allowed per
ticket/model/digest/prompt/schema version. Concurrent callers share a conditional
claim. Ordinary duplicate requests do not call the model again. When exhausted,
use manual handling; do not edit database attempts or silently change model
versions to evade the cap. Invalid/ambiguous recommendations remain advisory and
cannot be approved as valid results. No generated instruction is executed.

## Lost responses, decisions and duplicate delivery

| Ambiguous operation | Authoritative record | Safe recovery |
| --- | --- | --- |
| Ticket stored, response lost | Ticket unique source_event_id | Retry identical payload with same event ID; changed payload conflicts |
| Lead stored, response lost | lead_events + normalized-email identity + canonical lead | Retry same event/content; different event/email match preserves original details |
| Ticket stored, AI unavailable | Ticket plus versioned enrichment | Inspect enrichment; explicit bounded retry after upstream recovery |
| Suggestion stored, dashboard offline | Enrichment and review | Restart frontend/relogin; reread current review/revision |
| Review committed, response lost | Immutable final Review + atomic audit | Repeat identical action, reviewer and note; conflicting action returns 409 |
| Digest generated, response lost | Unique date/timezone frozen daily_digests row | Generate same date; returns original ID, timestamp and metrics |

There is no exactly-once network delivery guarantee. Transactions, uniqueness
and replay resolve ambiguity. Refresh before making a new decision; a changed
revision/version requires review. Pending forms are not durable decisions;
only a successful database commit is authoritative.

## Missed daily digests

Jobs are skipped while local n8n is down; no unlimited automatic backfill.
Sign in at /digests, select one completed date in the configured timezone, click
Generate report. Repeat deliberately for each missing day. Duplicate manual or
scheduled calls return the frozen original. Reports cannot be refreshed in place.
Late arrivals are intentionally absent from already saved reports; backlog is
captured at generation even for old dates. Align DIGEST_TIMEZONE and published
workflow timezone; changing aliases creates distinct report identities.
Existing fault/schedule tests cover a real accelerated timer. Implementation 08
adds restart/no-backfill and concurrent manual/service-equivalent recovery.

## Missing best-effort telemetry

Inspect the actual ticket/lead/review/digest first. workflow_runs can be absent
after an accepted response; this is not evidence the business transaction failed.
Correlate event ID, returned entity ID, X-Correlation-ID and execution ID.
Never recreate a business object merely to fill telemetry. Replaying an
accepted operation safely resolves its business identity but cannot promise to
reconstruct the lost original telemetry. Do not inject synthetic success rows.
Historical/manual n8n payloads may remain despite no-save settings; do not delete
them during recovery.

## PostgreSQL backups, restore and rollback

Before any separately authorized schema or credential maintenance, take a
protected application-only custom-format dump from WSL:

```bash
umask 077
backup_dir="$HOME/.local/share/flowforge-ai/backups/manual-$(date -u +%Y%m%dT%H%M%SZ)"
mkdir -p "$backup_dir"
docker compose exec -T postgres pg_dump -U flowforge_admin -d flowforge -Fc > "$backup_dir/flowforge.dump"
test -s "$backup_dir/flowforge.dump"
docker compose exec -T postgres pg_restore --list < "$backup_dir/flowforge.dump" > "$backup_dir/catalog.txt"
```

Verify exit status and protect both files (0600, directory 0700). A catalog check
does not establish restorability. Existing Implementation 07 protected backup
and catalog verification are documented; **restore has not been executed**.

Restore only into a separately provisioned disposable PostgreSQL instance and
new empty database, isolated from normal FlowForge. Supply the dump privately,
run pg_restore there, then verify migration, row counts, constraints and APIs.
Do not run --clean, drop/recreate the normal DB or restore over business records.
A real recovery restore, host failure drill, recovery time and recovery point
objectives remain untested/manual; obtain an explicit restore plan and approval
before touching normal data. Never restore n8n entities through raw table writes;
preserve its matching encryption key and use supported export/import guidance.

Implementation 08 has no migration. Reverting its application code is possible,
but does not undo audit/review records produced by recovery. Never downgrade a
database to match old code without assessing compatibility and preserving data.
Application rollback is not data rollback. Restart policies are not backups.
