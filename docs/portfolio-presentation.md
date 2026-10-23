# Portfolio presentation

## Project overview

FlowForge AI addresses repeated business intake, inconsistent ticket triage and
manual daily reporting with visual n8n orchestration and deterministic FastAPI
rules. PostgreSQL owns identities, original records, advisory results, human
decisions and audit. Next.js exposes an authenticated review/report workspace.
Local Ollama contributes optional bounded advice; business intake survives model
failure. No paid inference service or customer-action dispatcher is required.

The main engineering work is transactional idempotency, explicit validation,
separate advice/decision records, truthful failure outcomes, timezone-aware
frozen digests and reproducible fault/recovery evidence. This is a trusted-local
portfolio with documented security exceptions, not a public production service.

## Interview preparation

| Question | Grounded answer |
| --- | --- |
| Why FastAPI alongside n8n? | n8n routes webhooks/schedules visually; FastAPI enforces contracts, transactions and authorization independently of workflow editing. |
| Is processing synchronous? | Intake commits synchronously before its response. Support inference follows the response within n8n; no durable queue/outbox is implemented. |
| What if the sender loses a response? | Replay the same stable event. PostgreSQL identity constraints return the canonical record; changed remembered payloads conflict. |
| What prevents concurrent duplicates? | Unique constraints and transactional conflict handling/locks, not a lookup alone. Tests include concurrent intake/review/recovery. |
| Where is validation applied? | Actual byte limits, JSON/object/field validation and Pydantic contracts precede business writes; model output has a separate strict schema. |
| Are all replays write-free? | No. Canonical ticket/lead identities do not duplicate; audit/observation metadata can legitimately grow. |
| How does human approval control actions? | Approval/rejection is authenticated and durably audited. No outward dispatcher exists; a future dispatcher needs its own enforced approval gate. |
| Can the LLM execute instructions? | No tools/interpreter path exists. Candidate text is untrusted, validated and stored as advice; deterministic markers/uncertainty abstain. |
| What happens when Ollama fails? | Original tickets persist. Timeouts/busy/unavailable are explicit; bounded eligible retries require an operator, with a durable lease and three-attempt cap. |
| Why not claim exactly once? | HTTP delivery is ambiguous. Transactional identities provide replay safety for defined business effects, not exactly-once transport. |
| How does a digest stay repeatable? | One database snapshot, completed-day/timezone identity and frozen stored content; backlog is current at generation, not reconstructed history. |
| What does Compose prove? | Fresh isolated roles/databases, migrations, copied workflows and app builds were exercised. It does not prove every host/network/editor-owner path. |
| How secure is the system? | Review/digest authorization and boundary hardening exist; legacy unauthenticated ingress, image findings and missing autosaves remain accepted local risks. |
| What do the benchmarks mean? |20 compound scenarios repeated3 times in a serial fixture lab:60 passes, 120 replays without extra canonical records. They are not production load/accuracy evidence. |
| What was genuinely measured with a model? | Fresh real-Ollama integration passed21 checks. Historical12-example quality was11/12 category and 10/12 priority, too small for production conclusions. |
| What would you improve next? | First resolve the seven tracked patch/retention/ingress/test/auth/recovery/build follow-ups through separate approved maintenance. |

## Recording plan

No screen-recording capability was available for this task. The supplied PNG is
a genuine screenshot of the existing isolated sign-in UI; no video or simulated
product screen is presented as a recording. Use an existing local recorder to
follow this5–6minute script.

Before recording: start the lab, run the benchmark once, note its synthetic IDs/
digest date, sign in privately, close configuration/terminal history containing
credentials, and show only synthetic lab data. Do not capture password managers,
tokens, original customer records, encrypted backups or other projects. Use
loopback URLs; no public tunnel.

| Time | Shot | Suggested narration |
| --- | --- | --- |
|0:00–0:25|README intro and existing sign-in asset|“FlowForge AI combines visual orchestration with deterministic business APIs and local advisory AI.”|
|0:25–0:55|Architecture Mermaid|“n8n coordinates; FastAPI validates and commits; PostgreSQL is authoritative. Next.js presents human review.”|
|0:55–2:10|DemoA new synthetic ticket, response, separate advice, review, decision history|“Intake responds before inference. Advice is separate; approval records a human decision. No customer delivery is implemented.”|
|2:10–2:55|DemoB first lead/replay/email alias responses|“Stable events and canonical email prevent another canonical lead. Changed remembered requests conflict.”|
|2:55–3:45|DemoC stored completed-day report and independent counts|“Two tickets and one canonical lead match fixture data. Repeating the date returns the same frozen report; backlog is a current snapshot.”|
|3:45–4:35|Benchmark JSON summary and fresh test table|“Twenty scripted scenarios ran three times; 120 replays added zero canonical business records. Fixture timings are not real inference or load testing.”|
|4:35–5:10|Recovery summary and security exceptions|“Tickets survive model outages. Explicit recovery handles interrupted work; image, history and ingress exceptions remain open.”|
|5:10–5:35|Roadmap and handoff links|“The ten-milestone local portfolio is documented and ready for review. Public deployment needs further security work.”|

Use `portfolio-demos.md` for exact commands; do not improvise production actions.
If real Ollama is shown, identify that mode on-screen and allow abstention/failure.
For repeatable fallback shots, use the lab benchmark's controlled fault evidence,
clearly labelled. Do not edit media to imply a fixture is genuine inference.

## CV-ready entry

**FlowForge AI — Local AI Automation Portfolio**

Python, FastAPI, n8n, PostgreSQL, SQLAlchemy/Alembic, Next.js/React, Ollama, Docker

- Built support intake, canonical lead deduplication and frozen daily reporting,
  separating original records, bounded AI advice and authenticated human decisions.
- Verified20 end-to-end scenarios across 3 isolated fixture-backed repetitions;
 120 replay deliveries created zero additional canonical ticket/lead records.
- Added reproducible integration/fault/recovery verification; fresh checks included
 233 backend tests and 44 frontend tests, with documented trusted-local security limits.

These measurements refer to [Implementation 10 evidence](benchmark-report.md).
Do not claim production accuracy, customer deployment, reduced staffing costs,
automatic customer replies or a vulnerability-free release.

**Short introduction:** “I built a self-hosted workflow portfolio where n8n
orchestrates and FastAPI/PostgreSQL enforce the business rules. Local AI provides
bounded advice, humans record decisions, and replay/failure behavior is tested.”
