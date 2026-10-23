# Developer setup

Validated on Ubuntu WSL2 with Docker Desktop on 2026-10-24. Use this guide from the
repository root in **Linux Bash**, not Windows npm from a UNC directory.
Clone the final portfolio source, then run the commands below from its root:

```bash
git clone https://github.com/AdnanSherwani2003/flowforge-ai.git
cd flowforge-ai
```

## Recommended: isolated portfolio lab

Prerequisites: Git, Python 3, Docker Engine/Desktop with Compose 2.24.4+ and enough
free resources for an additional small stack. Existing host validation used
Compose 5.3.1. First image builds require registry/package access. Compose's
`!override` port replacement requires 2.24.4+
([Docker documentation](https://docs.docker.com/reference/compose-file/merge/)).
No paid keys or model download are needed.

```bash
python3 scripts/portfolio_lab.py start
python3 scripts/portfolio_lab.py status
curl --fail http://localhost:18001/health
curl --fail http://localhost:18001/ready
curl --fail http://localhost:15679/healthz/readiness
python3 scripts/benchmark_portfolio.py --repetitions 3
```

Open http://localhost:13000/login. Inspect the generated username/password
privately in `$HOME/.local/share/flowforge-ai/portfolio-lab/state.json`.
Do not display this file in a recording. Its parent is 0700 and configuration
files 0600. There are no hardcoded/shared public passwords.

The script creates a unique `ff-portfolio-*` Compose project, fresh PostgreSQL
roles/two databases, applies Alembic head `007_daily_digests`, builds both apps,
imports copies of the three workflow exports and one generated digest credential
through supported n8n CLI commands, then publishes the copies. Its database and
n8n volumes are new and separately labelled. No normal `.env` is read or replaced.
The default internal model fixture has no published port.

The lab sets `N8N_USE_WORKFLOW_PUBLICATION_SERVICE=false` to use the tested CLI
publication path. The original environment retains its default editor publication
service. Lab success verifies copied workflow execution, not the original
first-owner/editor activation process.

```bash
python3 scripts/portfolio_lab.py stop
python3 scripts/portfolio_lab.py start
```

Stop affects owned lab containers only; data, volumes and private configuration
remain. Resume performs no imports or credential replacement. Never use volume
removal or a database reset as cleanup. To keep an additional lab, choose a new,
nonexistent private state path and nonconflicting ports:

```bash
python3 scripts/portfolio_lab.py start \
  --state "$HOME/.local/share/flowforge-ai/portfolio-second" \
  --backend-port 18002 --frontend-port 13001 --n8n-port 15680
```

Use the same `--state` for status, benchmark and stop. A partially provisioned
state is retained and refused on resume: inspect its private `last-error.log`,
stop its owned containers, correct the underlying issue and select a new state
path. Do not delete existing volumes to retry.

## Optional real local Ollama

The accepted environment uses native Windows Ollama 0.40.8 and
`http://host.docker.internal:11434` from Docker Desktop. The model is
`qwen2.5:3b-instruct` with full expected digest:

```text
357c53fb659c5076de1d65ccb0b397446227b71a42be9d1603d46168015c9e4b
```

After a Windows restart, open Ollama from the Start menu if it is not already
running. For a standalone installation, run `ollama serve` in a private Windows
terminal only when no server is running. Check `ollama list`, `ollama ps` and
`http://localhost:11434/api/tags` locally; do not print customer prompts/responses.
The Windows app runs its API locally
([official Windows guide](https://docs.ollama.com/windows)); server environment
changes require restarting the app
([official FAQ](https://docs.ollama.com/faq)).

On a **new developer machine only**, install Ollama from its official distribution.
If this exact model is missing, `ollama pull qwen2.5:3b-instruct` obtains the tag;
then compare its full `/api/tags` digest with the pin above. A tag may move.
A mismatch must be reviewed; do not silently change the application pin or
overwrite existing model files. No model was downloaded for Implementation 10.

For an isolated real-model lab, stop the fixture lab first, then use a new state:

```bash
python3 scripts/portfolio_lab.py start \
  --state "$HOME/.local/share/flowforge-ai/portfolio-real" --real-model
```

Check the authenticated dashboard dependency status, not just host curl:
backend-to-host connectivity can fail while Windows curl works. Normal real
Ollama integration was re-run successfully; this optional new real-model lab
mode was not separately provisioned. The default 20-case benchmark requires the
fixture; real mode skips its two model-fault cases and successful advice may
vary/abstain.

Keep Ollama's local binding and firewall restrictions. Do not bind publicly or
use a tunnel to solve networking. Docker Desktop forwarding to the existing
loopback server worked here. Native Linux host-gateway routing and other hosts
were not validated. AI outage leaves ticket intake available; restore Ollama,
inspect the dependency diagnostic, then explicitly retry eligible enrichment.
Ordinary ticket replays do not retry AI.

## Fresh regular environment: manual reference

These commands are **only for a new machine with no existing FlowForge project,
volumes or configuration**. The original environment is already configured:
do not run initialization/import/provisioning over it. Prefer the isolated lab
when demonstrating beside existing personal n8n.

1. Check Docker inventory and ports 8001/3000/5679 before proceeding. Existing
   project resources mean stop and follow the current [handover](codex-handover.md);
   do not replace configuration or credentials.
2. Create ignored `.env` exclusively from the template; generate secrets without
   printing them:

```bash
python3 - <<'PY'
from pathlib import Path
import os, secrets
text = Path(".env.example").read_text()
for key in ("POSTGRES_ADMIN_PASSWORD", "FLOWFORGE_DB_PASSWORD",
            "N8N_DB_PASSWORD", "N8N_ENCRYPTION_KEY"):
    text = text.replace(key + "=replace_me", key + "=" + secrets.token_urlsafe(32))
with Path(".env").open("x") as handle:
    os.chmod(".env", 0o600)
    handle.write(text)
PY
docker compose config --quiet
docker compose build backend frontend
python3 scripts/setup_reviewer.py --generate
docker compose up -d postgres
```

Wait for PostgreSQL healthy using `docker compose ps`. Then:

```bash
docker compose run --rm --no-deps backend alembic upgrade head
docker compose up -d n8n
```

Open http://localhost:5679 and create a private first-owner account locally.
Supported CLI imports below are for this fresh database only; they are not
maintenance commands for an existing installation:

```bash
docker compose exec -T n8n n8n import:workflow --input=/workflows/support_ticket_intake.json
docker compose exec -T n8n n8n import:workflow --input=/workflows/lead_intake.json
python3 scripts/setup_digest_service.py
docker compose exec -T n8n n8n import:workflow --input=/workflows/daily_operations_digest.json
docker compose up -d backend frontend
```

The digest provisioner requires the imported lead workflow's owner project. If
the CLI imported into an unassigned project, use the authenticated editor to
resolve ownership before provisioning; do not edit managed tables. In the editor,
verify the digest credential reference and publish all three flows. The normal
publication-service configuration needs authenticated editor publication;
CLI publish alone is not assumed to register routes. Verify:

```bash
python3 scripts/smoke_test.py
curl --fail http://localhost:8001/ready
```

`verify_workflow_runtime.py` also expects the existing environment's seven-flow
inventory/four inactive drafts; on a new three-flow installation its historical
draft assertion is not applicable. Use its published-definition/migration checks
as reference and the isolated benchmark for a fresh three-flow acceptance;
do not manufacture or import old drafts to satisfy that inventory assertion.

Full first-owner UI provisioning/manual regular install was **not** repeated.
Fresh roles/databases, migrations, source builds, copied workflows/credential and
three-flow HTTP demos **were** exercised in the separate lab. No factory-clean
Windows host, cold network-cache install or full reboot was tested.

## Configuration reference

| Variable(s) in private .env | Purpose |
| --- | --- |
| POSTGRES_ADMIN_PASSWORD / FLOWFORGE_DB_PASSWORD / N8N_DB_PASSWORD | Distinct DB credentials; fresh-init only |
| N8N_ENCRYPTION_KEY | Encrypts n8n credentials; preserve with backups |
| FLOWFORGE_REVIEWER_* | Username, generated Argon2 hash and signing secret; setup_reviewer.py |
| FLOWFORGE_DIGEST_SERVICE_KEY | Narrow generation key; setup_digest_service.py |
| GENERIC_TIMEZONE / FLOWFORGE_DIGEST_TIMEZONE | Schedule/report timezone alignment |
| FLOWFORGE_ENABLE_SIMULATION=false | Normal operations must not inject failures |
| FLOWFORGE_ENRICHMENT_ENABLED=true | Optional advisory enrichment |
| OLLAMA_BASE_URL / OLLAMA_MODEL / OLLAMA_MODEL_DIGEST | Local endpoint and exact reviewed model |
| OLLAMA_TIMEOUT_SECONDS=25 / OLLAMA_NUM_GPU=-1 | Bounded inference; automatic accelerator selection |

Database passwords in initialization variables do not rotate existing database
roles. `docker compose restart` does not reload changed container environment.
Any existing credential rotation needs an approved backup/change/recreation plan,
preserved volumes and explicit verification; see [recovery](recovery-runbook.md).

## Local development and troubleshooting

Host frontend checks require Linux Node/npm and `npm ci` in `frontend`; use a
patched compatible Node release. The measured host Node 24.22.0 remains an open
patch follow-up, not a recommended security baseline. Docker builds use lockfiles
and existing reviewed image definitions. Do not run Windows npm against a UNC cwd.

```bash
cd frontend
npm ci
npm test
npm run lint
npm run typecheck
npm run build
cd ..
python3 scripts/verify_portfolio.py
```

The consolidated verifier also requires the configured **normal** services,
existing real model and running fixture lab. It creates uniquely named synthetic
records, preserving originals. It is not a clean-machine installer.
Use `--skip-recovery` only when deliberately omitting that drill; evidence records
the omission. Individual commands are listed in the benchmark report.

For port collisions, choose distinct lab ports; never stop unrelated containers.
For 401, sign in again; do not disable auth. For n8n404, inspect published status
and webhook path before replaying with the same event identity. `health` is
process liveness; `ready` includes database availability, not optional Ollama.
For failed provisioning, preserve private logs/state. Safe lab shutdown is
`portfolio_lab.py stop`; do not use destructive Docker cleanup.
