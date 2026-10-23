# Implementation 09 — Integrated testing and focused security review

**Final acceptance recorded: 2026-10-24 (Asia/Kolkata).**
The user explicitly accepted Implementation 09 **WITH DOCUMENTED EXCEPTIONS**,
strictly for the existing trusted-local FlowForge AI development environment.

The historical workflow-version gap, outstanding image/platform vulnerabilities
and unauthenticated ingress are **accepted risks, not resolved vulnerabilities**.
All reports, scanner findings and encrypted history backups are retained.
This is not approval for public production deployment.

**Git commit, push and merge are not authorized.** Implementation 09 remains
unstaged/uncommitted. No additional feature or refactoring is authorized.
Open maintenance work is explicitly tracked in [section M](#m-open-security-and-maintenance-follow-ups)
and the acceptance JSON; accepting the milestone does not close those items.

Full system evidence was collected on October 23; the final exception
investigation and selected rechecks completed October 24. See the
[final exception review](implementation-09-exception-review.md) for the evidence.
No tests were rerun merely to record this documentation-only acceptance.

## A. Implementation 08 checkpoint

Accepted Implementation 08 was locally committed as
`973c408d4c6893edae8a558774d3362bd1957f61` with:

`feat: add bounded resilience checks and explicit recovery`

The exact accepted 24-file manifest, whitespace and staged secret checks were
reviewed before committing. The tree was clean afterward. Branch
`implementation-09-testing-security` was created from that checkpoint.
Implementation 07 remains local `e746ff6`. Main and origin/main remain `29aa141`.
No push, merge, branch deletion or history rewrite occurred.

## B. Security/testing overview

Reviewed the existing FastAPI/PostgreSQL authority boundary, n8n orchestration,
Next reviewer session/Origin protection, deterministic intake/digests, local
Ollama validation, transaction/concurrency constraints and recovery procedures.
Existing architecture and three published workflows were reused, without new
services, business features or external inference.

The [security assessment](security-review.md) includes the threat model, trust
diagram, endpoint inventory and evidence-backed risk matrix. Sequential
`scripts/verify_system.py` consolidates actual frontend/backend/live acceptance,
isolated faults, integrated scenarios, workflow parity and application restore.
Separate dependency and secret scans keep successful execution distinct from
clean findings.

## C. Findings by severity

| Severity / kind | Finding and current decision |
| --- | --- |
| Critical/high upstream image ratings | n8n: 9 critical/46 high; PostgreSQL: 4 critical/32 high; backend: 1 high. Ratings are scanner rules/package locations, not confirmed exploitable application vulnerabilities. Reachability remains partly unresolved. Keep local-only and plan isolated platform patch qualification. |
| Medium, fixed | Actual-body size gaps before parsing and malformed JSON reported as service failure. Byte limits and safe client errors now enforced. |
| Medium operational, unresolved | Five autosaved n8n workflow-history versions absent relative to retained 07 export; independent compaction is consistent, exact timing/cause unproven. Current definitions/executions are intact. Requires retention/preservation review. |
| Medium local residual | Unauthenticated legacy ingress/read/enrich/telemetry APIs and n8n webhooks, no global rate/storage quota. A hostile-Origin form POST actually created a synthetic lead. Loopback/CORS do not authenticate senders. |
| Moderate upstream test-tool advisory | pytest 8.4.2 CVE-2025-71176 remains; random owner-only temp root mitigates the local path. Major test-stack upgrade deferred for separate compatibility review. |
| Low local residual | Copied signed session remains usable until one-hour expiry after browser-cookie logout; no session revocation. HTTP loopback cookie is intentionally not Secure. |

No approval bypass, executed customer expression/HTML, arbitrary tool authority,
secret exposure or unexpected original business-row change was demonstrated.
That statement is bounded by this review, not proof of absence.

## D. Confirmed defects fixed

1. Added pre-parsing FastAPI ASGI ceiling of **65,536 actual bytes**, including
   chunked, omitted or misleading Content-Length. Oversize 413; invalid length
   400; malformed/too-deep/invalid-encoding JSON sanitized 422.
2. Shared streaming Next reader now caps actual bytes: login/decisions **4096**,
   digest generation **1024**. Malformed/non-object JSON is 422, genuine upstream
   unavailability remains 503. Valid API contracts and legacy ignored extras stay.
3. All backend `/api/` responses, including legacy reads/errors, are private/
   no-store. This adds no authentication.
4. Fixed a reproduced Implementation 08 SQLite memory startup failure by applying
   pool_timeout only to PostgreSQL; existing PostgreSQL bounds remain.
5. Fixed disposable PostgreSQL readiness race: wait for final PID 1 postgres,
   rather than accepting the temporary initialization server.
6. Pinned reviewed installed Python application/test versions in constraints.
   Build pip is updated to 26.2.2, then removed from runtime; global npm is removed
   from the standalone frontend runtime. Application package versions unchanged.
7. pytest defaults to a unique private temporary base; filesystem owner/mode
   regression verifies the local mitigation.

Added 11 focused backend and 11 frontend cases; integrated tests exercise actual
HTTP chunking, expired signed sessions and complete synthetic workflows, avoiding
a broad refactor.

## E. End-to-end verification

- **Support:** real published webhook → persisted original ticket → pinned real
  Windows Ollama → separate validated enrichment/review → Next authenticated
  approval → one final audit. Replay is safe; original ticket state unchanged.
- **Lead:** published webhook → canonical email/event identity → safe replay,
  cross-event email duplicate, remembered-event conflict and linked allowlisted
  telemetry. Literal `{{7*7}}` input remains data.
- **Digest:** explicit completed-day generation → persisted frozen snapshot →
  repeated generation preserves identity/time → authenticated Next display.
  Existing scheduler-equivalent/transport-fault suite rerun separately.
- **Failure:** isolated database interruption/rollback, pool exhaustion, Ollama
  offline/busy, actual 120-second lease expiry, interrupted claim, response loss,
  browser retry, component restart, missing enrichment dispatch and missed-day
  explicit recovery. Normal PostgreSQL/n8n/Ollama were not stopped for faults.
- **Security:** anonymous/expired access denied, hostile dashboard Origin denied,
  attention advisory cannot be approved, customer HTML escaped in actual Next
  output, no password/token in report HTML. Injection marker safely goes to
  attention; this does not establish comprehensive prompt-injection resistance.

## F. Actual regression results

Final command executed to completion with exit status 0 on the final application
images:

```bash
python3 -u scripts/verify_system.py
```

| Suite | Passed | Failed | Skipped |
| --- | ---: | ---: | ---: |
| Backend pytest | 233 | 0 | 0 |
| Frontend Vitest | 44 | 0 | 0 |
| Isolated recovery | 49 | 0 | 0 |
| Support webhook | 192 | 0 | 0 |
| Lead webhook | 358 | 0 | 0 |
| Real Ollama enrichment | 21 | 0 | 0 |
| Human review integration | 29 | 0 | 0 |
| API smoke | 8 | 0 | 0 |
| Digest integration | 28 | 0 | 0 |
| Digest faults / scheduler | 44 | 0 | 0 |
| Lead faults | 36 | 0 | 0 |
| Support faults | 39 | 0 | 0 |
| Integrated security / system | 43 | 0 | 0 |
| Isolated application restore (check groups) | 13 | 0 | 0 |

Counts mix pytest/Vitest cases, assertion suites and restore check groups; they
are not a single coverage metric. Every listed suite was freshly executed in
the final sequential run; no --resume or historic pass substituted.

Also passed: frontend lint, TypeScript check and production build; backend/
frontend Docker builds; published workflow/runtime parity; migration head
`007_daily_digests`. Backend emitted 108 existing deprecation warnings.

Individual reproduction commands (run sequentially with no competing writers/
inference; synthetic records remain):

```bash
cd frontend
npm test
npm run lint
npm run typecheck
npm run build
cd ..
python3 scripts/test_resilience_regressions.py --milestone 9 --backend-count 233
python3 scripts/test_recovery_stack.py --output docs/evaluation/implementation-09-recovery.json
python3 scripts/test_security_system.py
python3 scripts/verify_workflow_runtime.py
python3 scripts/verify_backup_restore.py
python3 scripts/audit_dependencies.py
python3 scripts/audit_secrets.py
```

Use Linux Node/npm from WSL (tested Node 24.22.0), not Windows npm on UNC paths.
The regression JSON records each command and counts. The real model suite runs
against Windows Ollama; only the disposable recovery suite uses a model stub.
No extra model downloaded. Initial development attempts exposed the readiness
race, a test literal/type error and an auditor cache-path failure; those were
corrected before the final full successful run.

## G. Dependency and secret scan findings

Executed pip-audit **2.10.1**, npm audit and Docker Scout **1.23.1**. The Python
scanner ran in a disposable image without application credentials/volumes.

- npm: **0 findings**, including development dependencies.
- Python initial: 14 raw entries, seven unique advisories in pip/pytest.
  Final: **two raw entries / one unique advisory** in pytest; no clean audit claim.
- Removing runtime installers reduced backend high matches **6→1** and frontend
  **10→0**. No blind framework major upgrade or platform replacement.
- Final image counts:

| Image | Critical | High | Medium | Low | Unspecified | Rules / occurrences |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| backend | 0 | 1 | 2 | 26 | 0 | 29 / 29 |
| frontend | 0 | 0 | 0 | 0 | 1 | 1 / 1 |
| n8n | 9 | 46 | 47 | 8 | 31 | 141 / 143 |
| postgres | 4 | 32 | 29 | 7 | 2 | 74 / 74 |

See package IDs/fix versions/image IDs/report hashes in
[evaluation/implementation-09-images.json](evaluation/implementation-09-images.json).
Postgres critical Go matches locate to gosu, not a Go database server; n8n has
broader runtime surfaces beyond the current node set. Remaining backend high
zlib is reported not fixed. No blanket exploitability or safety claim.

Redacted secret scan covered nonignored working files and all reachable Git
blobs, active and retained rollback secret values/encodings plus high-confidence
key/token patterns: **0 matches**. Exact final file/blob counts are in
[evaluation/implementation-09-secrets.json](evaluation/implementation-09-secrets.json).
.env is ignored/mode 0600. No credentials/encryption keys rotated. This is not
exhaustive detection of arbitrary unknown historical secrets. Raw scanner output,
database dumps, logs and private configuration remain outside Git.

## H. Data and resource preservation

[Preservation evidence](evaluation/implementation-09-preservation.json) compares
all nine application-table row-value hash multisets against the fresh pre-09
baseline. No original business record was deleted. One original pending review
changed legitimately: **ca7a03ff-1540-4e72-95cf-a6fb3364d660** was approved at
23:16:56 Asia/Kolkata on October 23. The user explicitly confirmed the decision.
Reconstructing its pending fields reproduces the baseline hash. Approval is
preserved, not undone. All other original row hashes match; no unexpected change.

Seven complete workflow exports match the pre-09 baseline. Three published
definitions match source: support13, lead11, digest5; four inactive drafts remain.
Normal failure simulation is false. Older retained 335 execution entities and
335 execution-data rows and one encrypted credential match exactly.

**Preservation exception:** the older encrypted entity export contains 14
workflow-history rows; current has nine. Five missing rows are autosaved versions
(four support, one digest), with retained rows identical. Installed n8n has
independent autosave compaction; execution pruning=false does not disable it.
No pre-09 version-row baseline/debug evidence proves removal timing/cause.
No operator history/table writes, imports or publication occurred in 09.
Prior encrypted versions remain protected outside Git. Do not claim full history
preservation or restore over current definitions. See the security assessment
for source/config findings and the runbook for the required maintenance boundary.

Only normal backend/frontend were recreated. Other 18 original containers retain
identity/image/start time/environment hashes; all mounts and .env bytes match.
Personal n8n container is untouched and its readonly volume count remains **37**.
SentinelPOMDP/Neo4j/persistent volumes/credentials/encryption keys remain unchanged.
Ollama is still loopback on Windows; model files were not changed or downloaded.

## I. Actual backup/restore verification

A new custom-format application dump was written under
`/home/adnan/.local/share/flowforge-ai/backups/`, directory0700/files0600, outside
Git. Restored into a disposable network=none PostgreSQL17/tmpfs with no normal
mounts. Exact row-value multisets for all nine tables, head007, backend readiness/
ticket reads and normal-DB preservation passed: **13 check groups, 0 failures/
skips**. Latest path/SHA256: [restore evidence](evaluation/implementation-09-restore.json).

No normal restore, n8n database/volume restore, ownership/ACL restore
(--no-owner/--no-privileges), full Windows restart or host-loss RPO/RTO drill.
The [runbook](recovery-runbook.md) now distinguishes tested isolated restore from
manual normal recovery. Restart does not reload changed environment; approved
environment maintenance requires scoped recreation with existing volumes.

## J. Remaining limitations

- Unauthenticated local ingress/read/enrichment/telemetry and real browser-form
  write path remain; upstream n8n request parsers have higher defaults than the
  backend cap. No global rate/quota or slow-upload/OS network deadline.
- One shared reviewer; stateless logout does not revoke copied bearer tokens;
  local HTTP does not provide TLS. No commercial production readiness claim.
- No outbox/sweeper/automatic write replay/missed-day backfill. Explicit retries
  and immutable identities are essential after ambiguous client timeouts.
- Model is advisory, imperfect and not an authorization engine. The earlier
  12-example synthetic quality evaluation was not rerun and proves no production
  accuracy.
- Platform image findings, pytest advisory and history-version preservation
  exception remain. Mutable base tags/Python artifacts without hashes limit
  build repeatability despite exact tested image IDs and constraints.
- Historical/crashed/manual payloads and protected backups may retain customer
  text. Minimal current telemetry does not erase historic data.
- No public penetration test, load/soak certification, physical host recovery or
  exhaustive vulnerability/reachability proof was performed.

## K. Changed files and Git status

Current branch: `implementation-09-testing-security`; HEAD remains `973c408`.
Implementation 09 changes remain **unstaged and uncommitted**. .env/backups/
credentials/build outputs are excluded. No Implementation 10.
Exact changed-file manifest is recorded in
[evaluation/implementation-09-acceptance.json](evaluation/implementation-09-acceptance.json).

Changes are limited to backend request/cache/database/test/tooling boundaries;
frontend request reader/proxy/test/runtime image; verification/scanner/restore
scripts; README/handover/runbook/security/09 docs and redacted evaluation JSON.
No workflow source, migration, compose configuration, npm lockfile or business
domain service was changed by Implementation 09.

## L. Recommended commit message

`fix: harden request boundaries and verify system security`

This is a proposal only. No Implementation 09 staging/commit was performed.

## M. Open security and maintenance follow-ups

Final acceptance acknowledges the three documented exceptions as risks; it does
not resolve them or authorize their remediation. The user approved trusted-local
acceptance on **2026-10-24 (Asia/Kolkata)**. All items below remain open. No dates,
implementation work or service changes are scheduled by this register.

| ID | Priority | Status | Required follow-up and completion evidence |
| --- | --- | --- | --- |
| FF09-SEC-01 | High | Open — accepted documented risk | Qualify vendor-supported n8n/runtime/native-library patches and remaining image findings; include the WSL development Node patch. Retain all scanner findings and verify exact image digests, workflows, credentials, migrations and rollback in isolation. **Close only with:** Compatible candidate test results and fresh per-finding scan/triage; separately approved maintenance before any original-service recreation. |
| FF09-HIST-01 | Medium operational | Open — accepted documented risk | Define protected workflow-version export/backup policy and qualify supported retention controls and isolated recovery. Preserve both encrypted archives; retain the five-version live-database gap and unproven historical cause. **Close only with:** Documented backup/retention policy and isolated recovery evidence; no direct n8n table writes or original workflow/history changes without a separately reviewed plan. |
| FF09-INGRESS-01 | Medium | Open — accepted documented risk | Qualify scoped sender authentication across n8n/backend plus appropriate body, Origin, rate and resource limits before untrusted or broader use. Maintain loopback and current webhook contracts meanwhile. **Close only with:** Authorized coordinated configuration/workflow change, published/export parity and regression evidence; no public deployment authorization. |
| FF09-TEST-01 | Moderate upstream | Open — deferred maintenance | Assess a compatible pytest/pytest-asyncio upgrade for the retained advisory; preserve the random owner-only temporary-root mitigation. **Close only with:** Compatibility tests and updated audit; no claim that the mitigation fixes the affected package. |
| FF09-AUTH-01 | Low in trusted-local scope | Open — deferred hardening | Reassess TLS/Secure cookies, copied-session revocation and distinct reviewer identities before any broader deployment. **Close only with:** Separately approved scope and authentication/session tests; broader deployment remains unapproved. |
| FF09-REC-01 | Medium operational | Open — recovery verification limitation | Qualify isolated n8n recovery, ownership/ACL restoration and host-loss RPO/RTO; full Windows reboot remains unverified. **Close only with:** Recorded isolated drills and a separately approved plan for any normal-data restore; never overwrite existing storage as a test. |
| FF09-BUILD-01 | Low | Open — reproducibility maintenance | Review immutable base-image references and Python artifact hash locking during dependency maintenance. **Close only with:** Reproducible reviewed builds and preserved dependency/compatibility evidence. |

The detailed [security assessment](security-review.md) and
[exception investigation](implementation-09-exception-review.md) remain the
supporting evidence. Keep this register and the matching JSON follow-ups open
until actual remediation/verification is reviewed. No finding is suppressed.
No credential rotation is proposed without a new confirmed exposure.

A Git checkpoint still requires explicit authorization. This acceptance does
not authorize a commit, push, merge or public deployment.

## N. Final acceptance

**ACCEPTED WITH DOCUMENTED EXCEPTIONS**, explicitly approved by the user on
2026-10-24 for the existing trusted-local development environment only. The
[October 24 exception investigation](implementation-09-exception-review.md)
identifies every missing version, replays installed compaction rules (four of
five selected), identifies separate Community 24-hour pruning eligibility
(all four support autosaves) and secures encrypted evidence outside /tmp.
Historical causation remains unproven. It enumerates all 92 critical/high image
rule rows (90 unique IDs), adds Node runtime advisories and documents ingress.
No finding was suppressed. n8n runtime patching remains a High maintenance
priority; this is not unconditional platform security approval.

Backend 233/frontend 44/smoke 8/ingress probes 17 and workflow parity passed again;
other full suites remain the October 23 run, not a new claim of execution.
The proposal now has 44 files, with ten documentation/evidence files changed
during exception investigation and no runtime code/configuration/image changes.
Implementation 09 remains unstaged/uncommitted. No push, merge, branch deletion
or Implementation 10 occurred. Final acceptance is now recorded; commit, push
and merge remain explicitly unauthorized. Follow-ups in section M remain open.
