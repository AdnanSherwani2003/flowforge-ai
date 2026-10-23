# Three reproducible portfolio demos

All inputs below are synthetic. Use the separate fixture-backed lab:
`python3 scripts/portfolio_lab.py start`. Preconditions, private login and
loopback ports are in [setup](developer-setup.md). Run Bash from the repository.
No paid service or original workflow edits are required.

## One command verifies all three demos

```bash
python3 scripts/benchmark_portfolio.py --repetitions 3
python3 - <<'PY'
import json
from pathlib import Path
r=json.loads(Path("docs/evaluation/implementation-10-benchmark.json").read_text())
print({k:r[k] for k in ("run","passed","failed","skipped","replay_deliveries")})
for fixture in r["fixture_ids"]:
    print(fixture)
PY
```

Expected fixture-mode result:60 passed, 0 failed, 0 skipped (20 cases repeated3
times), 120 ordinary replays with zero additional canonical business records.
The JSON records IDs/dates and individual case/request timing/status without
passwords, tokens or raw model responses. Each rerun uses a fresh event namespace.
Results are measurements, not guarantees; a failure exits nonzero and records
the failed case. This command updates the local10 benchmark artifact.

## Demo A: support intake, advice and human review

**Preconditions:** healthy fixture lab, browser signed in at
http://localhost:13000 with its private generated reviewer credentials.
Default fixture mode gives predictable billing/medium advice.
For genuine local inference use the optional real-model setup; abstention is a
valid outcome, so do not promise a particular classification.

Create a private temporary request fixture and send it twice:

```bash
DEMO_DIR="$(mktemp -d)"
chmod 700 "$DEMO_DIR"
python3 - "$DEMO_DIR" <<'PY'
import json, sys, uuid
from pathlib import Path
p=Path(sys.argv[1])/"support.json"
p.write_text(json.dumps({
 "source_event_id":"portfolio-manual-"+uuid.uuid4().hex,
 "subject":"Synthetic duplicate subscription charge",
 "body":"I was charged twice for a subscription. Please review the duplicate payment."
}))
p.chmod(0o600)
PY
curl -sS -w '\nHTTP %{http_code}\n' \
  -H 'Content-Type: application/json' --data-binary @"$DEMO_DIR/support.json" \
  http://localhost:15679/webhook/support-ticket-intake
curl -sS -w '\nHTTP %{http_code}\n' \
  -H 'Content-Type: application/json' --data-binary @"$DEMO_DIR/support.json" \
  http://localhost:15679/webhook/support-ticket-intake
curl -sS -w '\nHTTP %{http_code}\n' -H 'Content-Type: application/json' \
  --data '{"subject":[]}' http://localhost:15679/webhook/support-ticket-intake
```

**Expected:** first201 with `ticket_id`, second200 with the same ID/duplicate
result, invalid422. The webhook response precedes the advisory request in the
published graph. Refresh the dashboard queue after enrichment finishes. Open the
matching ticket by subject/ID and compare original ticket versus separate advice.

1. Inspect category, priority, confidence, reason and pending review.
2. Approve the review, or reject a separate fresh ticket with a note.
3. Open decision history; a durable final decision/audit is visible.
4. Refresh and confirm the same final result. Original ticket fields are preserved.

Approval records a decision only. No email/payment/customer-action node exists.
Anonymous decisions401, hostile-origin browser decisions403 and attention-only
approval409 are exercised in benchmark cases 7–10. A review eligible for approval
does not authorize any future unimplemented dispatcher.

**Fallback:** benchmark case10 submits an instruction-injection marker and
expects attention/unknown fields. Cases 16–17 switch only the owned internal test
fixture to invalid output/503; persisted tickets remain, advice abstains or
reports unavailable. The script restores fixture mode. It never stops original
Ollama or injects faults into original services. Inspect the attention queue.
Do not call this real-model behavior/accuracy.

**Audit verification:** benchmark cases 6/8/9 compare original API records and
count exactly one final approval event. n8n telemetry is useful for trace IDs but
best effort; PostgreSQL business/review audit is authoritative. New execution
payloads are intentionally not saved in n8n; absence of full node payload history
is expected.

## Demo B: canonical lead intake

**Preconditions:** same lab. Use a new synthetic event and `example.com` email:

```bash
python3 - "$DEMO_DIR" <<'PY'
import json, sys, uuid
from pathlib import Path
key="portfolio-manual-"+uuid.uuid4().hex
lead={"source_event_id":key,"name":"Synthetic Portfolio Contact",
      "email":key+"@example.com"}
p=Path(sys.argv[1])
(p/"lead.json").write_text(json.dumps(lead))
(p/"lead-alias.json").write_text(json.dumps({
 **lead,"source_event_id":key+"-alias","email":"  "+lead["email"].upper()+"  "
}))
PY
for fixture in lead lead lead-alias; do
  curl -sS -w '\nHTTP %{http_code}\n' -H 'Content-Type: application/json' \
    --data-binary @"$DEMO_DIR/$fixture.json" \
    http://localhost:15679/webhook/lead-intake
done
curl -sS -w '\nHTTP %{http_code}\n' -H 'Content-Type: application/json' \
  --data '{"source_event_id":"portfolio-invalid","name":"Synthetic","email":"invalid"}' \
  http://localhost:15679/webhook/lead-intake
```

**Expected:**201 created, 200 event replay, 200 normalized-email duplicate; all
three valid responses identify the same canonical lead. Invalid email422.
Changing details under the remembered original event conflicts409; a new email
alias event does not overwrite the existing lead. Benchmark cases 11–15 verify
these contracts plus20 replays per repetition and business-count deltas.

**Audit verification:** benchmark digest case18 checks resulting
`lead_created`/duplicate observation counts and independent canonical-identity SQL.
Use the dashboard history/operations view and workflow trace for observations.
There is no standalone public lead-audit endpoint; do not invent one for a demo.
Canonical lead counts and observation counts intentionally differ.

## Demo C: deterministic daily digest

**Preconditions:** fixture lab and authenticated browser. Run the benchmark
command above; inspect its digest fixture entries for reporting dates and IDs.

Case18 installs **only new lab-owned synthetic fixtures**: two tickets and one
canonical lead, then dates only those generated IDs/their audit rows to noonUTC
on an unused completed day beginning2001-01-15. Source-event namespace ownership
is checked. This makes day counts deterministic without altering existing data.
No backdating command targets the original FlowForge database.

1. Open http://localhost:13000/digests?date=DATE using a recorded fixture date.
2. Inspect the frozen report: two ticket creations and one canonical lead
   creation for the day; zero duplicate lead observations for these fixtures.
3. Refresh/generate that same date. The stored digest ID, content and generation
   timestamp remain unchanged.
4. Compare case18's independent SQL ticket/lead-identity counts with report fields.
5. Inspect case20: future date rejected422; missing service/reviewer auth401.

Backlog is current at generation, even for an old reporting date, so it can
include other lab records. Activity counts are timezone-day scoped.
Do not assert a fixed backlog value or claim the report reconstructs past backlog.
The 5-node schedule runs09:00 Asia/Kolkata; this demo invokes its generation
contract explicitly. It does not wait for a real daily scheduler tick or
automatically backfill missed days.

**Failure verification:** the fresh44-check digest fault suite separately tests
invalid/malformed/unavailable outcomes and accelerated isolated scheduling.
The 49-check recovery drill covers explicit missed-day backfill and frozen
concurrent generation. Read [benchmark evidence](benchmark-report.md).

## Safe cleanup

```bash
python3 scripts/portfolio_lab.py stop
```

This retains every lab volume, generated credential, synthetic record and report.
The private `DEMO_DIR` fixtures may also be retained; no data deletion is required.
Do not use `DELETE`, `TRUNCATE`, `down -v`, volume pruning or imports over original
workflows. Subsequent lab start resumes its data; a new benchmark namespace avoids
identity collisions. Original services, personal n8n and Ollama remain running.
