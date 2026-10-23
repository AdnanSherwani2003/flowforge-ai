# Implementation 10 benchmark and verification

Measured on 2026-10-24 in the existing WSL2/Docker Desktop development environment.
[Raw benchmark](evaluation/implementation-10-benchmark.json),
[command/log manifest](evaluation/implementation-10-verification.json) and
[preservation evidence](evaluation/implementation-10-preservation.json) are the
source of truth. Historical reports remain unchanged.

## Method and reproduction

```bash
python3 scripts/portfolio_lab.py start
python3 scripts/benchmark_portfolio.py --repetitions 3
python3 scripts/verify_portfolio.py
```

The benchmark uses an ownership-checked `ff-portfolio-*` Compose project with
new PostgreSQL/n8n volumes, source-built FastAPI/Next.js, n8n 2.43.8 and migration
`007_daily_digests`. Host bindings are loopback 18001/13000/15679. The model is a
controlled HTTP fixture advertising the application's pinned
`qwen2.5:3b-instruct` metadata; it is **not inference**. Existing real Windows
Ollama 0.40.8 was tested separately, without model download.

Each run has a random synthetic event namespace. Twenty compound scenarios run
serially three times. There is no load generator, concurrency saturation test or
explicit discarded warmup; containers are already ready and caches/model state
are not controlled. Raw evidence records all case durations plus labelled HTTP
status/duration samples; fixture IDs/dates permit UI inspection. Passwords,
tokens, customer text and raw model responses are excluded.

Case duration includes polling and, where relevant, Docker/SQL/schema checks or a
group of 20 replays. HTTP duration measures individual requests including expected
errors/polls. The two populations answer different questions; neither is
end-user human decision time. P95 uses sorted nearest rank, ceil(0.95*n).
Three support-create samples give a P95 equal to the slowest observation.

## Roadmap targets versus observed results

| Target | Fresh observed result | Interpretation |
| --- | --- | --- |
|20/20 end-to-end cases|20/20 in each of 3 repetitions; 60 passed, 0 failed, 0 skipped|Serial controlled-fixture scenarios, not production accuracy |
|0 duplicate business writes across 20 replays|20 support plus20 lead replays per repetition; 120 total; 0 extra canonical rows|Audit/observation writes may legitimately occur |
|0 unapproved outward actions|No delivery/action implementation or customer-action nodes exist|Structural invariant; outbound-traffic runtime metric is N/A |
|Accepted advice schema-valid; invalid advice falls back|3/3 accepted fixture outputs validated; invalid/503/injection paths checked each repetition|Observed100% of 3 accepted examples, not universal model correctness |
|Actual task duration|60 cases: median 72.111 ms; P95 1461.627 ms|Heterogeneous compound scenario durations |
|Actual HTTP duration|270 requests: median 59.736 ms; P95 96.337 ms|Includes polling and expected rejections |
|Initial support response|3 requests: median 60.898 ms; P95 145.909 ms|Fixture lab webhook response; excludes later inference |
|Recovery|49 passed, 0 failed, 0 skipped; 191.61 seconds|Separate isolated live stack, HTTP model stub |

Authorization checks exercise anonymous denial, hostile browser Origin denial,
attention-only approval rejection, final decision idempotency and original-ticket
immutability. They do not demonstrate an external dispatch gate: none is
implemented. A future outward action must enforce a separate approved-decision
gate before delivery.

## The 20 scripted cases

| Case | Assertion |
| --- | --- |
|1|Process and database readiness |
|2|Support webhook creates an original ticket |
|3|20 support replays create no additional ticket |
|4|Changed remembered support event conflicts409 |
|5|Invalid support rejected422 |
|6|Post-response schema-valid advice and separate review |
|7|Unauthenticated decision denied401 |
|8|Same-origin human decision, hostile-origin denial, original unchanged |
|9|Decision replay retains one final approval audit |
|10|Injection marker abstains and attention cannot be approved |
|11|Lead creation |
|12|20 lead replays create no extra canonical lead |
|13|Whitespace/case-normalized email identity |
|14|Changed remembered lead event conflicts409 |
|15|Invalid email rejected422 |
|16|Controlled invalid model output becomes attention |
|17|Controlled model503 leaves original ticket and unavailable result |
|18|Completed-day digest matches independently queried ticket/identity counts |
|19|Frozen digest replay and actual Next.js HTML |
|20|Invalid future date and unauthorized digest generation rejected |

Each repetition creates four support test tickets, one canonical lead plus an
email-alias observation; the digest fixture separately creates two tickets and
one canonical lead on its unused completed day. Case5/15 invalid requests and
conflicts must not create business records. See raw fixture IDs for principal
support/lead/digest identities; not every auxiliary test identity is listed.
All records remain in the owned lab.

## Fresh verification results

All rows below were executed during10. Counts combine test functions and suite
assertions/check groups as labelled; they must not be summed into a claim about
independent production cases.

| Suite | Passed | Failed | Skipped |
| --- | ---: | ---: | ---: |
|Backend pytest tests|233|0|0|
|Frontend Vitest tests|44|0|0|
|Support webhook checks|192|0|0|
|Lead workflow checks|358|0|0|
|Real Ollama integration checks|21|0|0|
|Human review integration checks|29|0|0|
|API smoke checks|8|0|0|
|Digest integration checks|28|0|0|
|Digest isolated fault checks|44|0|0|
|Lead isolated fault checks|36|0|0|
|Support isolated fault checks|39|0|0|
|Isolated recovery checks|49|0|0|
|Portfolio scenarios, 3 repetitions|60|0|0|

Frontend lint/typecheck/production build and published 13/11/5-node parity passed.
Normal failure simulation is disabled; Compose/runtime model/credential settings
agree and migration head is applied. The real-model suite created 3 synthetic
tickets, with initial webhook timings72/73/62 ms; those are **not inference
latency measurements**.

The first verification attempt exposed a fault-test assumption at a calendar-day
boundary: its first accelerated scheduled run can correctly create a new daily
report201, rather than replay yesterday's existing report200. The test now
permits at most one created 201 followed by duplicate200 responses for the same
frozen ID. The corrected44-check suite and full sequential verifier passed.
No application or published-workflow logic changed.

## Recovery evidence

[Fresh49 checks](evaluation/implementation-10-recovery.json) exercised an isolated
live PostgreSQL/FastAPI/n8n/Next.js stack: statement/pool bounds, interrupted DB
sessions, response loss, component restarts, auth/decision persistence, model
outage, concurrent claims, actual120 second lease expiry, three-attempt cap,
post-response dispatch gap, explicit inference recovery and missed-day backfill.
No original service was restarted to obtain this evidence.

The separate portfolio lab's stop/resume check verifies private configuration
bytes persist without workflow reimport. Lab volumes remain; no reset is used.
See [lifecycle evidence](evaluation/implementation-10-lab.json).

## Historical evidence and omitted checks

The 12-example real-model quality evaluation from 04 was **not rerun**:
category agreement11/12, priority10/12; one lockout over-prioritized, one vague
outage safely abstained. Historical median inference latency was597 ms GPU and
3189 ms CPU. Twelve synthetic examples do not establish production accuracy.
Fixture timing cannot replace these quality/inference measurements.

Implementation 09's43-check integrated security suite, 13-check isolated app
restore drill, pip/npm audits and image/advisory scans were not rerun in 10.
Their findings/evidence remain visible and unresolved; backend/frontend security
regressions and fresh secret checks were executed. No new clean-scan claim is made.
Original/n8n restore, ownership recovery, full Windows reboot, a factory-clean
host and independent multi-developer install were not exercised.

The manual fresh normal editor-owner setup is documented but not fully tested.
The automatic isolated lab used a CLI-compatible publication setting; original
published-workflow parity was verified separately. Mutable images, host load,
small sample sizes and existing caches limit portability and repeatability of
timings. These measurements are not throughput, availability or latency SLAs.
