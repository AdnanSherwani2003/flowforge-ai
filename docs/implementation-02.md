# Implementation 02 — Data Contracts & Mock Business APIs

## 1. Objectives

Implementation 02 delivers the core data contracts, persistence layer, idempotency engine, and business API contracts for **FlowForge AI**. The objective is to establish a rock-solid, production-grade foundation for incoming business operations before connecting the deterministic n8n support-ticket workflow (Implementation 03) and bounded Ollama AI enrichment (Implementation 04).

Key goals accomplished:
- **Relational Persistence**: PostgreSQL 17 integration via SQLAlchemy 2.x and psycopg 3, strictly separated from n8n internal databases.
- **Strict Data Contracts**: Pydantic v2 schemas enforcing string bounds, whitespace stripping, and format normalization.
- **Idempotent Ticket Intake**: Deterministic SHA-256 canonical hashing guaranteeing duplicate detection and conflict rejection at the database boundary.
- **Safe Audit Logging**: Append-only audit events storing operational tracing metadata without leaking full ticket bodies, credentials, or sensitive personal data.
- **Mock CRM Interface**: Local lead capture API with email normalization and idempotency support to facilitate future n8n lead-intake workflows.
- **Comprehensive Automated Testing**: 24 deterministic automated tests including contract validation, race condition handling, and PostgreSQL integration in isolated schemas.

---

## 2. Architecture & Design Decisions

### Modular Backend Layout
```
backend/
├── alembic.ini                   # Alembic configuration
├── alembic/                      # Database migration scripts
│   ├── env.py                    # Migration execution environment
│   └── versions/                 # Versioned migration revisions
│       └── 001_initial_data_contracts.py
├── app/
│   ├── main.py                   # FastAPI application initialization & error handlers
│   ├── api/                      # Route controllers
│   │   ├── health.py             # System health endpoint
│   │   ├── tickets.py            # Customer support ticket endpoints
│   │   └── mock_crm.py           # Mock CRM lead endpoints
│   ├── core/
│   │   ├── config.py             # Pydantic BaseSettings environment loader
│   │   └── database.py           # Engine & SessionLocal factory
│   ├── models/                   # SQLAlchemy 2.x Declarative Models
│   │   ├── base.py
│   │   ├── ticket.py
│   │   ├── lead.py
│   │   └── audit_event.py
│   ├── schemas/                  # Pydantic v2 validation contracts
│   │   ├── common.py
│   │   ├── ticket.py
│   │   ├── lead.py
│   │   └── audit_event.py
│   └── services/                 # Business logic & idempotency
│       ├── hasher.py             # Canonical JSON SHA-256 hasher
│       ├── audit_service.py      # Sanitized audit trail logger
│       ├── ticket_service.py     # Idempotent ticket service
│       └── lead_service.py       # Idempotent lead intake service
├── tests/                        # Automated pytest suite
│   ├── conftest.py
│   ├── test_health.py
│   ├── test_tickets.py
│   ├── test_ticket_contracts.py
│   ├── test_duplicate_protection.py
│   ├── test_concurrency.py
│   ├── test_audit.py
│   ├── test_mock_crm.py
│   ├── test_db_resilience.py
│   └── test_postgres_integration.py
└── requirements.txt
```

### Key Architectural Decisions

1. **Synchronous SQLAlchemy with FastAPI Session Dependency**:
   - Chose standard synchronous session management (`sessionmaker` yielding a `db: Session`) rather than async SQLAlchemy.
   - *Rationale*: For transaction-heavy database workflows with strict rollback and lock handling, synchronous SQLAlchemy combined with Uvicorn worker concurrency provides predictable connection pooling, simpler debugging, and rock-solid transaction boundaries without event-loop starvation.
2. **Deterministic Canonical Hashing for Idempotency**:
   - Instead of checking equality across mutable Python models, incoming payloads are serialized into canonical JSON (stripped strings, sorted keys, compact separators `(",", ":")`) and hashed with SHA-256.
   - When the same `source_event_id` arrives:
     - If `payload_hash` matches: Replay HTTP 200 with `duplicate: true`.
     - If `payload_hash` differs: Reject with HTTP 409 Conflict.
3. **Database-Enforced Uniqueness & Concurrency Safety**:
   - Application-level lookups alone are vulnerable to race conditions (Time-of-Check to Time-of-Use).
   - We enforce unique B-tree indexes on `source_event_id` in PostgreSQL.
   - If two identical events are flushed concurrently, the losing thread catches `IntegrityError`, issues a session rollback, re-queries the winning record, and returns the idempotent response gracefully.
4. **Append-Only Sanitized Audit Trail**:
   - The `audit_events` table logs operational metrics (`subject_length`, `body_length`, `email_domain`, `status`, event types) rather than full request bodies or credentials, preventing security leaks in persistent storage.

---

## 3. Database Schema

All custom application tables belong exclusively to the `flowforge` database (owned by `flowforge_app`). The `flowforge_n8n` database remains strictly isolated.

### Table: `tickets`
| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | `VARCHAR(36)` | PRIMARY KEY | UUID string identifier |
| `source_event_id` | `VARCHAR(128)` | UNIQUE, NOT NULL | External caller event ID |
| `subject` | `VARCHAR(200)` | NOT NULL | Validated ticket subject |
| `body` | `TEXT` | NOT NULL | Validated ticket description |
| `status` | `VARCHAR(50)` | NOT NULL, DEFAULT 'received' | Processing lifecycle state |
| `category` | `VARCHAR(50)` | NOT NULL, DEFAULT 'unknown' | Triage classification |
| `payload_hash` | `VARCHAR(64)` | NOT NULL, INDEXED | SHA-256 canonical hash |
| `created_at` | `TIMESTAMPTZ` | NOT NULL, DEFAULT now() | Creation timestamp |
| `updated_at` | `TIMESTAMPTZ` | NOT NULL, DEFAULT now() | Last update timestamp |

**Indexes**:
- `ix_tickets_source_event_id` (UNIQUE B-tree)
- `ix_tickets_payload_hash` (B-tree)
- `ix_tickets_created_at_id` (Composite B-tree for deterministic pagination)

### Table: `leads`
| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | `VARCHAR(36)` | PRIMARY KEY | UUID string identifier |
| `source_event_id` | `VARCHAR(128)` | UNIQUE, NOT NULL | External caller event ID |
| `normalized_email` | `VARCHAR(255)` | NOT NULL, INDEXED | Trimmed, lowercase email |
| `name` | `VARCHAR(100)` | NOT NULL | Contact full name |
| `status` | `VARCHAR(50)` | NOT NULL, DEFAULT 'new' | Lead pipeline status |
| `payload_hash` | `VARCHAR(64)` | NOT NULL | SHA-256 canonical hash |
| `created_at` | `TIMESTAMPTZ` | NOT NULL, DEFAULT now() | Ingestion timestamp |

**Indexes**:
- `ix_leads_source_event_id` (UNIQUE B-tree)
- `ix_leads_normalized_email` (B-tree)
- `ix_leads_created_at_id` (Composite B-tree for deterministic pagination)

### Table: `audit_events`
| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | `VARCHAR(36)` | PRIMARY KEY | UUID string identifier |
| `entity_id` | `VARCHAR(64)` | NOT NULL, INDEXED | Referenced ticket/lead ID |
| `event_type` | `VARCHAR(64)` | NOT NULL, INDEXED | Event name (e.g., `ticket_created`) |
| `actor` | `VARCHAR(64)` | NOT NULL, DEFAULT 'system' | Submitting identity |
| `timestamp` | `TIMESTAMPTZ` | NOT NULL, DEFAULT now() | Audit event timestamp |
| `safe_detail` | `JSON` | NOT NULL | Sanitized operational dictionary |

**Indexes**:
- `ix_audit_events_entity_id` (B-tree)
- `ix_audit_events_event_type` (B-tree)
- `ix_audit_events_entity_timestamp` (Composite B-tree)

---

## 4. API Inventory & Contracts

### 4.1 System Endpoints
- `GET /health`: Health verification endpoint.
  - **Response 200**: `{"status": "ok", "service": "flowforge-core", "version": "0.1.0"}`

### 4.2 Support Ticket Endpoints
- `POST /api/tickets`: Submit a customer support ticket.
  - **Request Body**:
    ```json
    {
      "source_event_id": "evt-ticket-101",
      "subject": "Printer network timeout",
      "body": "Floor 2 printer is unreachable on 10.0.4.15."
    }
    ```
  - **Response 201 Created** (New event):
    ```json
    {
      "id": "e2e8e45b-a94a-44fd-9c0e-6bb85b6d7825",
      "source_event_id": "evt-ticket-101",
      "subject": "Printer network timeout",
      "body": "Floor 2 printer is unreachable on 10.0.4.15.",
      "status": "received",
      "category": "unknown",
      "created_at": "2026-10-20T13:35:00Z",
      "updated_at": "2026-10-20T13:35:00Z",
      "duplicate": false
    }
    ```
  - **Response 200 OK** (Idempotent duplicate):
    Returns existing record with `"duplicate": true`.
  - **Response 409 Conflict** (Conflicting payload with identical event ID):
    `{"detail": "Conflict: source_event_id 'evt-ticket-101' already exists with different payload content."}`
  - **Response 422 Unprocessable Entity** (Malformed or invalid inputs).

- `GET /api/tickets/{ticket_id}`: Retrieve single ticket.
  - **Response 200**: Ticket object.
  - **Response 404**: `{"detail": "Ticket '{ticket_id}' not found"}`.

- `GET /api/tickets?limit=20&offset=0`: List tickets with bounded pagination.
  - **Query Parameters**:
    - `limit`: Integer (1 to 100, default 20).
    - `offset`: Integer (>= 0, default 0).
  - **Response 200**:
    ```json
    {
      "items": [...],
      "total": 42,
      "limit": 20,
      "offset": 0
    }
    ```

- `GET /api/tickets/{ticket_id}/audit`: Retrieve audit history for a ticket.
  - **Response 200**:
    ```json
    {
      "ticket_id": "e2e8e45b-a94a-44fd-9c0e-6bb85b6d7825",
      "audit_events": [
        {
          "id": "c55ed8b9-...",
          "entity_id": "e2e8e45b-...",
          "event_type": "ticket_created",
          "actor": "api_client",
          "timestamp": "2026-10-20T13:35:00Z",
          "safe_detail": {
            "source_event_id": "evt-ticket-101",
            "subject_length": 23,
            "body_length": 45,
            "category": "unknown",
            "status": "received"
          }
        }
      ]
    }
    ```

### 4.3 Mock CRM Endpoints
- `POST /api/mock-crm/leads`: Ingest a lead.
  - **Request Body**:
    ```json
    {
      "source_event_id": "lead-evt-201",
      "name": "Jane Doe",
      "email": "   Jane.Doe@Example.COM   "
    }
    ```
  - **Response 201 Created**:
    ```json
    {
      "id": "da5baa87-...",
      "source_event_id": "lead-evt-201",
      "normalized_email": "jane.doe@example.com",
      "name": "Jane Doe",
      "status": "new",
      "created_at": "2026-10-20T13:35:10Z",
      "duplicate": false
    }
    ```
  - **Response 200 OK**: Duplicate replayed with `"duplicate": true`.
  - **Response 409 Conflict**: Conflicting lead data.

- `GET /api/mock-crm/leads/{lead_id}`: Retrieve lead by ID (HTTP 200 or 404).
- `GET /api/mock-crm/leads?limit=20&offset=0`: List leads with bounded pagination.

---

## 5. Input Validation Rules

| Field | Rule | Error |
|---|---|---|
| `source_event_id` | 1–128 characters after trim. Whitespace-only rejected. | HTTP 422 |
| `subject` | 1–200 characters after trim. Whitespace-only rejected. | HTTP 422 |
| `body` | 1–5,000 characters after trim. Whitespace-only rejected. | HTTP 422 |
| `name` | 1–100 characters after trim. Whitespace-only rejected. | HTTP 422 |
| `email` | Valid RFC email. Normalized to lowercase and trimmed. Max 255 chars. | HTTP 422 |
| `limit` | Integer 1–100. | HTTP 422 |
| `offset` | Integer >= 0. | HTTP 422 |

---

## 6. Migration and Operational Commands

### Migration Execution Model: Explicit CLI vs Automatic Startup
In FlowForge AI, database migrations require an **explicit command** (`docker compose run --rm backend alembic upgrade head`) and are deliberately **not run automatically** on backend container startup.

**Engineering Rationale**:
1. **Concurrency and Race Prevention**: In multi-replica or auto-restarting container architectures, running migrations automatically during application boot introduces race conditions where multiple containers execute concurrent DDL statements against the same schema.
2. **Failure Isolation**: If a migration fails, separating migration execution from application boot allows operators to inspect and remediate schema errors independently without crashing healthy existing application workers.
3. **Audited Deployments**: Decoupling schema application from service initialization adheres to standard 12-factor application lifecycle practices.

### Applying Database Migrations
```bash
docker compose run --rm backend alembic upgrade head
```

### Checking Current Migration Version
```bash
docker compose run --rm backend alembic current
```

### Running the Test Suite
```bash
docker compose run --rm backend pytest -v
```

### Executing Live End-to-End Smoke Test
```bash
python3 scripts/smoke_test.py
```

---

## 7. Acceptance Verification Evidence

| Acceptance Criterion | Verification Method | Result | Evidence |
|---|---|---|---|
| Backend starts healthy | Docker Compose healthcheck | PASSED | `flowforge-ai-backend-1 Up (healthy)` |
| Database migrations apply | Alembic CLI | PASSED | `Running upgrade -> 001_initial_data_contracts` |
| New tickets persist | Live POST + PostgreSQL SELECT | PASSED | Verified in `flowforge.tickets` table |
| Deterministic Idempotency | Replay identical payload | PASSED | HTTP 200, `duplicate: true`, identical ID |
| Conflict Rejection | Replay different payload | PASSED | HTTP 409 Conflict, original record intact |
| Concurrency Safety | 5 concurrent worker threads | PASSED | Handled via PostgreSQL unique index & session rollback |
| Sanitized Audit Records | Audit table query | PASSED | Operational metrics logged without sensitive bodies/credentials |
| Mock CRM APIs | Lead ingestion & normalization | PASSED | Email normalized to lowercase, duplicates detected |
| Healthcheck Compatibility | `GET /health` | PASSED | `{"status":"ok","service":"flowforge-core","version":"0.1.0"}` |
| Original n8n Untouched | Container inspection | PASSED | `n8n` container and `n8n_data` preserved on port 5678 |
| FlowForge n8n Available | `GET http://127.0.0.1:5679/healthz` | PASSED | `{"status":"ok"}` on port 5679 |

---

## 8. Known Limitations & Roadmap Alignment

1. **Deterministic Workflow & AI Enrichment Staging**:
   - Ticket status initializes to `'received'` and category to `'unknown'`.
   - **Implementation 03** implements the deterministic n8n support-ticket triage workflow.
   - **Implementation 04** introduces bounded Ollama AI enrichment.
   - **Implementation 05** introduces human approval and the operational dashboard.
2. **Lead Scoring Deferred**: The mock CRM currently accepts and stores leads with status `"new"`. Lead qualification and automated routing belong to Implementation 06.
3. **Authentication Scope**: Open local endpoints appropriate for local-first portfolio architecture. Dashboard authentication and API keys will be scoped in future phases.
