# Implementation 03 — Final maintenance and acceptance

Verified 2026-10-22 (Asia/Calcutta), following explicit user authorization for password rotation, unpublishing only the stale workflow, and a local Git checkpoint.

**Implementation 03 is complete for its documented local portfolio scope.** All maintenance and required regression checks succeeded. No push, merge, or Implementation 04 work is authorized by this checkpoint.

## Maintenance results

- Rotated only PostgreSQL role n8n_app using hidden psql password prompts. A cryptographically generated password remained in process memory until written to the ignored .env; neither password was placed in shell arguments, scratch source, output, or tracked files.
- Fresh TCP authentication against flowforge_n8n succeeded with the new password and failed with the previous password.
- Stopped/drained only FlowForge n8n; n8n_app sessions reached zero. Updated only N8N_DB_PASSWORD in .env, validated resolved Compose configuration in memory, and recreated only FlowForge n8n using the existing image.
- Preserved N8N_ENCRYPTION_KEY, FlowForge volume identities, all other environment values, PostgreSQL container, and backend container. The PostgreSQL container's old initialization-only N8N_DB_PASSWORD environment is intentionally unchanged; it does not set the password of an existing role and the revoked value no longer authenticates.
- Used the installed supported command after checking its help:
  `docker compose -p flowforge-ai exec n8n n8n unpublish:workflow --id=wWjX3Bi5uRDyLzGu`.
  After recreation, that ID is inactive with activeVersionId null. Its definition and all three historical executions remain. No workflow was deleted or archived.
- FlowForgeSupportIntake01 remains published at 32f4ea75-e33b-4941-b368-d89303e349d1, with 11 nodes matching the version-controlled export and sole ownership of POST support-ticket-intake. All three other drafts remain inactive; no other publication state changed.

## Backup and rollback readiness

Protected recovery directory (outside Git):

`/home/adnan/.local/share/flowforge-ai/backups/2026-10-22-maintenance-0ec9b3c9`

Directory mode 0700; sensitive files mode 0600. It contains custom-format dumps of both dedicated FlowForge databases, the FlowForge n8n volume archive, pre/post-rotation .env backups, supported published workflow exports, and safe verification metadata. Never publish these files.

Both dumps were actually restored into a separate PostgreSQL container with network=none, tmpfs storage and no production mounts. Every captured record ID matched. The restore used --no-owner --no-privileges, so data/schema recovery was exercised; ownership/ACL restoration remains part of an actual recovery procedure. The volume archive was readable, included config, and passed path checks. Recovery prerequisites were verified before rotation; the hidden password mechanism was dry-run on the disposable checker. A startup timing issue on the first restore-check attempt was corrected by waiting for the final PostgreSQL process; both restores then succeeded before any production mutation.

Rollback was prepared to restore the previous role password and environment together and recreate only FlowForge n8n if required. Live rollback was unnecessary. Restore snapshots to a separate recovery target first; do not reset working databases to fix authentication. Protected pre-rotation configuration still contains sensitive rollback material; retain it with restricted access until the user chooses a backup-retention policy.

## Database preservation

| Application table | Before maintenance | After verification |
| --- | ---: | ---: |
| tickets | 210 | 235 |
| audit_events | 313 | 348 |
| leads | 14 | 15 |
| workflow_runs | 469 | 552 |

Increases are retained synthetic preflight/regression records. All pre-existing IDs remain.

n8n counts remained: five workflow definitions, 20 workflow-history rows, 333 historical execution rows and 333 execution-payload rows. Three stale-workflow executions remain unchanged in inventory. Credentials table was empty before and after; there were no saved credential records on which to exercise a decryption/use test. Its fingerprint and the original encryption key were preserved.

Migration remains 003_workflow_runs_unique; no production migration/reset was performed. New completed normal executions left no additional n8n execution payload rows. Historical executions were not sanitized, deleted, or claimed sanitized. All 83 new application telemetry records passed the metadata allowlist inspection.

## Regression results from this maintenance run

| Command | Passed | Failed | Skipped |
| --- | ---: | ---: | ---: |
| docker compose -p flowforge-ai exec -T backend pytest -q | 82 tests | 0 | 0 |
| python3 scripts/test_support_workflow.py | 192 assertions | 0 | 0 |
| python3 scripts/test_workflow_faults.py | 36 assertions | 0 | 0 |
| python3 scripts/smoke_test.py | 8 stages | 0 | 0 |

The runtime verification script also passed: Compose/runtime agreement, simulation false, matching published export, stale workflow unpublished, intended webhook route, migration, VARCHAR(100) tracing columns and telemetry uniqueness.

PostgreSQL concurrency, input type/shape parity, tracing, sanitized errors, duplicate/conflicting replay, actual ECONNRESET/ECONNREFUSED, bounded timeouts, post-commit retry and best-effort telemetry were exercised. The isolated fault suite used a separate tmpfs n8n database and its documented legacy startup-registration setting; normal service configuration and simulation remained unchanged. Backend pytest reported 53 existing dependency deprecation warnings. No dependency upgrade was bundled.

## Git checkpoint and safety

The local checkpoint includes the existing engineering corrections plus maintenance documentation and a stale-state assertion in scripts/verify_workflow_runtime.py. The exact 17-file inventory appears in the historical corrections report below. Before committing, inspect every modified/untracked path, check staged inventory/whitespace, and scan staged blobs as well as repository content for known credential values/encodings, provider tokens, private keys, credential-bearing URLs and suspicious literal secret assignments. Do not add .env, backups, private logs, or temporary maintenance helpers.

Staged verification passed for exactly 17 changed/new files. Content inspection covered every indexed repository blob (including staged content), known current and revoked credentials and encoded variants, provider tokens, private keys, JWTs, literal credential URLs and suspicious secret assignments: zero findings. Workflow exports contain no credentials or pinned payloads. .env, backups and private helpers are absent from the index. Both unstaged and staged whitespace checks passed.

The authorized local commit message is `fix(impl-03): finalize workflow reliability and maintenance` on `implementation-03-deterministic-workflow`. Its hash is available through `git log -1`; no push/merge is part of this checkpoint.

All 18 other baseline containers retained their IDs, start times and images; this includes the personal n8n, SentinelPOMDP and Neo4j resources. Only the authorized FlowForge n8n container was replaced. Dedicated test containers were stopped after use; no test schemas remained.

## Remaining limitations and next milestone

This remains a localhost portfolio deployment: ingress is unauthenticated, telemetry is best effort rather than durable, /health is a shallow liveness check, historical/crashed execution payloads may contain customer content, and dependency/runtime deprecation warnings remain. Wider ingress requires explicit authentication and retention work. These are documented scope limitations, not regressions introduced by maintenance.

No further maintenance approval is needed for the two completed actions. The local checkpoint is authorized after the successful staged checks above. Do not push, merge, or start Implementation 04 without the user's next instructions.

The earlier reports below are preserved as dated engineering history. Their pending-approval statements describe the earlier state and are superseded by this maintenance result.

---

# Implementation 03 — Final engineering corrections

Current verification date: 2026-10-22 (Asia/Calcutta).
Git baseline remains 26a1184 on implementation-03-deterministic-workflow; no commit/push/merge was made.

**Recommendation: the requested engineering corrections are verified; final acceptance remains conditional on approved credential rotation and stale-workflow unpublishing.** Neither approval-dependent action was executed. Implementation 04 was not started.

## A–C. Bugs fixed and technical changes

- Preserved complete JSON payloads through n8n so Pydantic controls type, shape, whitespace and length validation. Removed per-field String(...) coercion.
- Added a shared TraceId contract (1–100 safe ASCII identifier characters) to ticket headers and workflow telemetry. Rejected invalid correlation/execution metadata before persistence; generated missing correlation IDs; returned a fresh safe correlation for rejected webhook metadata.
- Prevented invalid/oversized event metadata from breaking 422 telemetry: record null plus safe rejection flags instead of coercing or truncating rejected input.
- Restored correlation/execution IDs in both ticket IntegrityError recovery audit paths. Forced real PostgreSQL races verify duplicate and conflicting losers.
- Restricted safe_detail to status/error-code enums and boolean flags; arbitrary customer/error text is rejected. Fixed 503/conflict formatting to avoid trusting raw upstream detail.
- Made post-response telemetry semantics explicit in JSON and X-FlowForge-Telemetry: best-effort.
- Activated supported n8n no-save settings for success, error, manual and progress data. Disabled periodic pruning to preserve historical rows; documented transient/crashed-run retention.
- Removed the misleading conn-reset backend branch. Added an isolated proxy and disposable n8n engine that prove actual ECONNRESET, refusal, timeout, post-commit timeout and telemetry outage behavior.
- Split normal acceptance from fault testing. Normal backend simulation remains false; the public workflow no longer forwards simulation hooks.
- Made PostgreSQL test schemas unique; configured PostgreSQL failures now fail tests instead of silently skipping.

## B. Files modified or added

| Area | Files |
| --- | --- |
| Backend | backend/app/api/tickets.py; backend/app/schemas/tracing.py (new); backend/app/schemas/workflow_run.py; backend/app/services/ticket_service.py |
| Regressions | backend/tests/test_tracing_contracts.py (new); backend/tests/test_postgres_integration.py |
| Runtime/workflow | compose.yaml; workflows/support_ticket_intake.json |
| Scripts | scripts/test_support_workflow.py; scripts/test_normal_workflow.py (new); scripts/fault_proxy.py (new); scripts/test_workflow_faults.py (new); scripts/verify_workflow_runtime.py (new) |
| Documentation | README.md; docs/implementation-03.md; docs/codex-handover.md; docs/implementation-03-review.md (existing uncommitted review preserved below) |

## D. Tests and evidence

| Verification | Result |
| --- | --- |
| Backend pytest on rebuilt running backend | 82 passed; seven real PostgreSQL tests, including forced six-worker duplicate and conflicting races |
| Live normal-operation acceptance | 192 assertions; also available through the original test_support_workflow.py entrypoint |
| Isolated transport and telemetry suite | 36 assertions; Linux ECONNRESET independently observed and n8n execution data contained ECONNRESET/ECONNREFUSED/timeout codes |
| API smoke | Eight stages passed |
| Workflow consistency | Published export matches repository; disposable supported import/export round trip matches tested node definitions |
| Runtime/database | Simulation false in Compose/container/application; trace columns VARCHAR(100); migration 003 and telemetry unique constraint present |
| Privacy | After active global configuration, new completed normal runs left zero execution/payload rows; historical baseline rows retained |
| Safety | All recorded pre-test application/audit/telemetry IDs and n8n historical execution IDs retained; named mounts and credential fingerprint unchanged |
| Git | Whitespace clean; work remains uncommitted on the original branch |

Full test commands, fault outcomes, privacy limits, and installed-version CLI activation caveat are documented in [Implementation 03](implementation-03.md). The disposable engine uses legacy startup registration because CLI publication in the installed version does not by itself register the default publication service's routes. That configuration differs from the real instance; genuine transport behavior is still exercised by the same installed HTTP nodes/branching/formatting definition.

## E–J. Status, limits, safety and approvals

- Intended published workflow: FlowForgeSupportIntake01, version 32f4ea75-e33b-4941-b368-d89303e349d1, 11 nodes, sole owner of POST support-ticket-intake.
- Stale workflow wWjX3Bi5uRDyLzGu remains active/published with the same path; the three other drafts remain inactive. Read-only CLI export, database queries and the editor dropdown confirmed its state and supported Unpublish action. None was unpublished/deleted.
- For approved unpublishing: export the stale version, open exactly /workflow/wWjX3Bi5uRDyLzGu, select **Unpublish** from the dropdown beside Publish, confirm that ID, then verify intended publication/route ownership and rerun normal acceptance. Prefer this editor path over relying on CLI publication-side effects.
- Credential rotation remains pending. Existing database credentials and N8N_ENCRYPTION_KEY were compared in memory and preserved during n8n recreation. Use the detailed rotation runbook preserved below after approval; it uses hidden password prompts and container recreation, not restart.
- Rebuilt/recreated only FlowForge backend and recreated only FlowForge n8n for new configuration. PostgreSQL container/volumes were not recreated/reset. No migrations were applied because none were required.
- Tests used unique disposable schemas and two uniquely named fault containers with tmpfs test storage. Only containers created by the harness were stopped. Synthetic application records remain.
- Personal n8n/volume, SentinelPOMDP, Neo4j, unrelated resources and Git history were not targeted.
- Remaining limits: exposed password, stale competing publication, unauthenticated localhost ingress, non-durable telemetry, shallow backend readiness, historical/crashed execution payloads, and dependency/runtime deprecation warnings.
- No rotation, unpublish, deletion of existing workflows/history, commit, push, merge, or Implementation 04 work was performed.

## Current acceptance gates

1. Approve unpublishing only wWjX3Bi5uRDyLzGu through the supported editor; preserve its definition/history and every other draft.
2. Approve the n8n_app rotation maintenance window and protected backup/recovery procedure below; preserve the existing encryption key and named volumes.
3. Verify fresh new-password authentication, old-password rejection, intended route ownership, disabled simulation, normal acceptance, telemetry and data preservation after those operations.
4. Review and approve a final Implementation 03 checkpoint separately; no commit/push is authorized yet.
5. Begin Implementation 04 only after final acceptance and the user's next instructions.

The historical review below is retained verbatim as baseline evidence. Its original outstanding engineering findings are superseded by the corrections above; its credential-rotation procedure remains a plan requiring approval.

---

# Implementation 03 — Codex acceptance review

Review date: 2026-10-22 (Asia/Calcutta). Baseline: `26a1184`, branch `implementation-03-deterministic-workflow`.

## Decision

**Functional milestone verified; final acceptance withheld.** Resolve the credential exposure, duplicate active publication, input-contract mismatch, and telemetry/privacy gaps before treating Implementation 03 as final. Implementation 04 was not started.

## Repository and environment

- Checkout initially clean; configured origin matches the supplied GitHub URL. No fetch, push, merge, commit, or workflow publication/deletion performed.
- Read README, handover, Implementations 01–03, Compose, backend handlers/services/contracts/migrations/tests, acceptance scripts, and workflow definition. No applicable AGENTS.md found in the repository or searched parent locations.
- FlowForge backend and PostgreSQL healthy; backend /health and n8n /healthz both HTTP 200. HTTP ports bind to 127.0.0.1:8001 and 127.0.0.1:5679. PostgreSQL has no host-published port.
- Docker Engine 29.6.2; running backend Python 3.12.15, n8n image 2.43.8, PostgreSQL image 17-alpine. Live Alembic revision is 003_workflow_runs_unique; the workflow/execution unique constraint exists.
- Running backend app, tests, and Alembic Python files match repository bytes.
- FlowForge mounts are flowforge-ai_postgres_data and flowforge-ai_n8n_data. Personal n8n, SentinelPOMDP, and Neo4j were not targeted by commands.
- .env is ignored, untracked, and mode 0600. Current local secret values were compared in memory against reachable Git blobs: no matches. This is not an exhaustive historical secret scan.

## Runtime correction and verification

Compose resolved ENABLE_FAILURE_SIMULATION=false, but the existing backend container had true. The published workflow maps a caller's JSON simulate field to X-FlowForge-Simulate, so the live hook was publicly triggerable within the local ingress boundary.

After testing the existing enabled state, recreated **only backend**, using:

```bash
cd /home/adnan/projects/flowforge-ai
docker compose up -d --no-deps --force-recreate --no-build --pull never backend
```

The new container environment and instantiated application settings both report false. All four webhook simulate values (503, timeout, conn-reset, timeout-after-persist) now return ordinary 201 creations; a direct backend simulation header also returns 201. Backend remains healthy. No credentials or volumes were changed.

## Tests

| Verification | Result |
| --- | --- |
| Existing backend pytest suite | 30/30 passed, including five real PostgreSQL tests and concurrent ticket/telemetry uniqueness |
| Existing live acceptance suite, before disabling simulation | 35/35 passed; timeout approximately 5.07 seconds |
| Additional normal-operation webhook checks, after recreation | 24/24 passed: ten fixtures, response correlation header, duplicate/conflict, seven validation cases, persistence, audit trace/minimization, telemetry |
| Existing API smoke script, after recreation | All eight stages passed |
| Simulation disabled probes | Four webhook modes and direct backend header all ignored as intended |

The PostgreSQL tests use and remove their dedicated test_isolated_integration schema, not application tables. It did not exist before the run. Live probes add synthetic tickets, audit events, telemetry, execution history, and one smoke-test lead; these were retained.

Test limitations:
- The existing acceptance script expects enabled simulation and cannot serve unchanged as the normal-operation acceptance gate. Separate normal and explicitly enabled reliability runs; always restore false through container recreation.
- The conn-reset handler checks a transport entry that is not guaranteed in the ASGI scope, then raises HTTP 503. A passing status-code assertion does **not** establish a real TCP reset. Verify with an isolated fault proxy or controlled test server.
- Existing pytest has six deprecation warnings. Its PostgreSQL fixture can skip connectivity failures and uses a fixed schema name; use unique schema names before parallel CI runs.

## Published workflow and draft inventory

The intended workflow FlowForgeSupportIntake01 is active and published at version 2cf6d2f1-cdc1-40dd-ba41-33182a631713. Both editor and published nodes/connections exactly match workflows/support_ticket_intake.json.

The 11 nodes are Webhook Trigger; Extract & Prepare; Call FastAPI Backend; Route Outcome; five outcome formatters (Created, Duplicate, Conflict, Validation, Unavailable); Respond to Webhook; Record Workflow Run. Branches route 201/200/409/422 plus fallback 503. Backend timeout is 5000 ms; telemetry timeout is **3000 ms**, contrary to the documentation's blanket 5-second claim. Both HTTP nodes continue on transport errors. Telemetry runs after the response within the same execution; it is best effort, not a durable background queue.

Only one webhook registration currently exists: POST support-ticket-intake → FlowForgeSupportIntake01.

| Previously documented draft | Actual state | Review |
| --- | --- | --- |
| wWjX3Bi5uRDyLzGu | **Active and published**, 11 nodes | Older parameter definitions; same webhook path. No current route registration. Publication collision/startup risk; obtain approval to unpublish, preserving it. |
| 4i5roR0oitA1bfbc | Inactive, 11 nodes | Older intake definition, not empty; parameter differences in eight nodes |
| DKrWyiNmb2ph8c6w | Inactive, 11 nodes | Older intake definition, not empty; parameter differences in eight nodes |
| MWeQoRSWGXVBxbBP | Inactive, 2 nodes | Test Webhook Flow: POST test-ping → Set Response |

No drafts were deleted, edited, activated, or unpublished.

## Outstanding issues

1. **Credential exposure remains unresolved.** .env and running n8n database password agree; a fresh TCP connection as n8n_app succeeds. This verifies consistency, not that the previously exposed password has been rotated. n8n_app is not superuser and cannot create roles/databases. Rotate before acceptance.
2. **Input contracts diverge.** Extract & Prepare applies String(...) to non-string values. A probe with numeric source_event_id, object subject, and array body returns 422 directly from FastAPI but 201 through n8n. Preserve original types and let backend validation decide. Add webhook regression coverage.
3. **Telemetry disappears for accepted requests.** A 101-character correlation header produces webhook 201 but telemetry lookup remains 404: ticket ingestion accepts it while WorkflowRunCreate limits it to 100. Oversized invalid source_event_id similarly cannot fit the telemetry schema. Bound/normalize tracing consistently and retain safe summaries of rejected input. Both IntegrityError recovery audit paths in ticket_service omit correlation_id and execution_id.
4. **Privacy claims exceed implementation.** Execution history stores raw webhook/backend data; 19 of 215 existing execution payload rows matched synthetic subject/body markers before this review's new probes. Extraction forwards subject/body and does not remove them from earlier node history. Agree on future execution-data saving/retention settings before real customer traffic; preserve existing history pending approval.
5. **Telemetry ingress is host-accessible and trusts arbitrary safe_detail.** It is exposed through localhost:8001, not exclusively the Docker network as documented. No API/webhook authentication exists. Use an allowlist/bounded metadata schema; add service authentication before wider ingress.
6. **503 response formatting trusts backend detail.** Format Unavailable Outcome forwards body.detail on HTTP 503. Current handlers return safe fixed text, but the workflow itself does not enforce the claimed generic boundary. Prefer a fixed safe message with approved diagnostic metadata.
7. **Operational health is shallow.** /health does not probe PostgreSQL. Current pool_pre_ping helps reconnects but does not make this endpoint a readiness check. Dependency ranges and mutable base tags also prevent identical rebuilds; lock versions/digests in a follow-up rather than upgrading during rotation.

## Safe n8n_app rotation — plan only, approval required

Do not execute until the user approves a short FlowForge n8n maintenance window. Restart does not refresh container environment variables; recreate the container. PostgreSQL's init script runs only on an empty data directory, so editing .env alone cannot change the live role password.

1. Scope every command explicitly to /home/adnan/projects/flowforge-ai and project flowforge-ai. Record current image ID/digest, volumes, encryption-key identity, five workflow IDs, published versions, route owner, and credentials record count without secret values. Resolve the duplicate active workflow with separate user approval before restarting n8n.
2. Prepare protected, verified backups of both FlowForge databases and n8n_data, together with the existing N8N_ENCRYPTION_KEY and restricted configuration. Dumps and snapshots contain confidential data: keep them outside Git, access-restricted/encrypted, with a tested recovery method.
3. Generate a strong replacement in a password manager or non-logging local helper. Keep old configuration briefly in protected recovery storage. Do not place either password in chat, command arguments, shell history, Compose output, or diagnostic logs. Preserve N8N_ENCRYPTION_KEY exactly.
4. Pause incoming FlowForge submissions, let in-flight executions finish, then stop only FlowForge n8n:
   `docker compose -p flowforge-ai stop n8n`.
5. Open an interactive admin psql session in FlowForge PostgreSQL:
   `docker compose -p flowforge-ai exec postgres psql -U flowforge_admin -d postgres`.
   Use `\password n8n_app` and enter the new value at its hidden prompts. Avoid literal ALTER ROLE passwords in SQL text or shell commands. Update only N8N_DB_PASSWORD in .env using a private editor/non-logging helper; retain mode 0600 and existing ownership.
6. Check configuration without printing secrets (`docker compose -p flowforge-ai config --quiet`), then recreate only n8n using the existing local image:
   `docker compose -p flowforge-ai up -d --no-deps --force-recreate --no-build --pull never n8n`.
   Named mounts remain attached. Do not recreate PostgreSQL: its N8N_DB_PASSWORD environment variable is initialization input and may remain stale until a planned future maintenance; the live role and .env are authoritative.
7. Verify a **fresh TCP** n8n_app connection against flowforge_n8n using the new password and verify rejection of the old password without printing either. Local socket psql succeeds via trust here and is not a password test. Verify n8n health/readiness, workflow/credential counts and IDs, mounted volume identities, unchanged encryption key, published version, route owner, normal webhook create/replay/conflict/422, and telemetry.
8. If startup fails, keep ingress paused and repair forward: confirm role/.env/container consistency and encryption key/volume identity. Do not reset or restore application databases merely to repair authentication. If a temporary credential rollback is explicitly authorized, restore both role password and .env, then recreate only n8n; never leave the exposed password as the final state.
9. Reopen ingress after checks. Remove protected obsolete credential copies according to an agreed retention policy. Review the earlier disclosure location for restricted access/redaction with approval; changing Git files cannot revoke exposed credentials.

References: [Docker restart behavior](https://docs.docker.com/reference/cli/docker/compose/restart/), [Compose up and volume preservation](https://docs.docker.com/reference/cli/docker/compose/up/).

## Exact gate before Implementation 04

1. Obtain approval to unpublish the stale active workflow; preserve all four drafts.
2. Approve and execute the credential rotation above; verify fresh authentication and webhook continuity.
3. Fix input-type preservation, tracing bounds/rejected-event telemetry, concurrent audit trace fields, and generic 503 formatting; verify targeted regressions.
4. Agree on execution-data privacy/retention and metadata allowlists. Keep host ingress local until authentication is designed.
5. Separate normal acceptance from fault tests; substantiate or correct the TCP-reset claim. Re-run backend and normal webhook checks with simulation false at completion.
6. Reconcile README/Implementation 03 completion claims and limitations with evidence, then create a final reviewed Git checkpoint. No push without authorization.
7. Only after acceptance and the user's next instructions, begin Implementation 04.
