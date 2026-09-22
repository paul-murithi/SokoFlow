# SokoFlow

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python: 3.12](https://img.shields.io/badge/python-3.12-blue.svg)](https://www.python.org/downloads/release/python-3120/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.111.0-green.svg)](https://fastapi.tiangolo.com/)
[![Test Coverage](https://img.shields.io/badge/Coverage-88%25-brightgreen.svg)](tests/)
[![Code Style: Ruff](https://img.shields.io/badge/code%20style-ruff-000000.svg)](https://github.com/astral-sh/ruff)

**Headless WhatsApp ERP & Conversational Commerce Engine for Kenyan SMEs**

SokoFlow is a backend ERP engine designed for small and medium-sized enterprises (SMEs) in Kenya. It exposes its entire operational surface through natural WhatsApp conversations—eliminating app downloads, UI navigation overhead, and expensive training for non-technical shop owners. In SokoFlow, **the conversation is the user interface.**

---

## 1. See SokoFlow in Action

### Loom Video Demo

[Watch the 5-Minute SokoFlow Walkthrough](https://www.loom.com/share/your-loom-demo-id-here) _(https://www.loom.com/share/2aff352666d24821b91cb99c7373b33b)_

### Interactive Web UI Simulator

SokoFlow ships with an integrated chat simulator for local end-to-end testing without external WhatsApp API charges or webhooks infrastructure.

- **Web UI Mode:** `http://localhost:3000` (provides a WhatsApp-like web interface to send messages and receive asynchronous bot replies & PDF reports).
- **CLI Mode:** Interactive terminal prompt (`make simulate`).

---

## 2. Key Features

- **Conversational FSM Engine:** Deterministic Finite State Machine managing stateful multi-turn dialogues over stateless WhatsApp webhooks.
- **Transactional Inventory & Sales:** Atomic sale recording, immediate inventory deduction, and snapshot unit pricing.
- **Asynchronous Background Processing:** Offloads daily report generation and alert delivery out of the latency-critical webhook path using Celery workers.
- **Low-Stock Threshold Detection & Alerts:** Triggers automatic event notifications when inventory drops to or below set thresholds.
- **Automated PDF Report Generation:** Dynamic daily summary report generation using ReportLab delivered as WhatsApp document media.
- **HMAC Webhook Verification & Deduplication:** HMAC SHA-256 signature verification and Redis-backed message deduplication (`dedup_ttl_seconds`).
- **Multi-Language Support (Localization):** Dynamic message template rendering supporting Swahili (`sw`) and English (`en`).
- **Zero-External API Dependencies:** Built-in simulator adapter allows complete offline development and verification.

---

## 3. System Architecture & Visuals

### Diagram A: High-Level System Architecture

```mermaid
flowchart TD
    A["WhatsApp API / Web Simulator"] -->|"HTTP POST /webhook/whatsapp"| B["FastAPI Webhook Endpoint"]

    B -->|"HMAC-SHA256 Signature Check"| B
    B -->|"Check & Set message_id (dedup)"| C[("Redis Cache")]
    B -->|"Enqueue Task"| D[("Celery Broker · Redis DB 1")]

    D --> E["Conversation Worker (Celery)"]

    E --> F[("PostgreSQL")]
    E --> G[("Redis Sessions (FSM State)")]

    F --> H["MessageSender"]
    H -->|"Outbound Response"| A

    classDef entry fill:#1f6feb,stroke:#0d3b7a,color:#fff,stroke-width:1px;
    classDef gateway fill:#f59e0b,stroke:#92600a,color:#111,stroke-width:1px;
    classDef store fill:#10b981,stroke:#065f46,color:#fff,stroke-width:1px;
    classDef worker fill:#8b5cf6,stroke:#4c1d95,color:#fff,stroke-width:1px;
    classDef sender fill:#ef4444,stroke:#7f1d1d,color:#fff,stroke-width:1px;

    class A entry;
    class B gateway;
    class C,D,F,G store;
    class E worker;
    class H sender;
```

**Flow summary**

1. WhatsApp (or the local simulator) POSTs an inbound message to the FastAPI webhook.
2. FastAPI verifies the HMAC signature and checks Redis for a duplicate `message_id`.
3. A valid, non-duplicate message is enqueued to the Celery broker (Redis DB 1) — the webhook itself does no business logic.
4. The Conversation Worker picks up the task, reads/writes FSM session state in Redis, and persists confirmed data to PostgreSQL.
5. The MessageSender (mock or real) delivers the outbound response back through the same channel.

### Diagram B: Conversation Lifecycle & State Transitions

```mermaid
stateDiagram-v2
    [*] --> IDLE

    IDLE --> ADD_PRODUCT_NAME: intent = add product
    IDLE --> RECORD_SALE_PRODUCT: intent = sale
    IDLE --> CHECK_STOCK_PRODUCT: intent = check stock
    IDLE --> REPORT_PENDING: intent = report
    IDLE --> IDLE: intent = help

    %% --- ADD_PRODUCT flow ---
    state "ADD_PRODUCT Flow" as ADD_PRODUCT {
        ADD_PRODUCT_NAME --> ADD_PRODUCT_PRICE: name received
        ADD_PRODUCT_PRICE --> ADD_PRODUCT_QTY: price received
        ADD_PRODUCT_QTY --> CONFIRM_ADD: quantity received
        CONFIRM_ADD --> ADD_PRODUCT_NAME: restart
    }
    CONFIRM_ADD --> IDLE: confirmed (product persisted)

    %% --- RECORD_SALE flow ---
    state "RECORD_SALE Flow" as RECORD_SALE {
        RECORD_SALE_PRODUCT --> RECORD_SALE_QTY: product matched (fuzzy)
        RECORD_SALE_QTY --> CONFIRM_SALE: quantity received
        CONFIRM_SALE --> RECORD_SALE_PRODUCT: restart
    }
    CONFIRM_SALE --> IDLE: confirmed (sale recorded,\nstock deducted)

    %% --- CHECK_STOCK flow ---
    state "CHECK_STOCK Flow" as CHECK_STOCK {
        CHECK_STOCK_PRODUCT --> [*]: display stock level
    }
    CHECK_STOCK_PRODUCT --> IDLE: response sent

    %% --- REPORT flow ---
    REPORT_PENDING --> IDLE: report delivered (async)

    %% --- Low stock branch off confirmed sale ---
    CONFIRM_SALE --> LOW_STOCK_CHECK: on confirm
    state LOW_STOCK_CHECK <<choice>>
    LOW_STOCK_CHECK --> QUEUE_ALERT: below threshold
    LOW_STOCK_CHECK --> IDLE: above threshold
    QUEUE_ALERT --> IDLE: alert task queued

    %% --- Universal overrides ---
    ADD_PRODUCT_NAME --> IDLE: cancel / menu
    ADD_PRODUCT_PRICE --> IDLE: cancel / menu
    ADD_PRODUCT_QTY --> IDLE: cancel / menu
    RECORD_SALE_PRODUCT --> IDLE: cancel / menu
    RECORD_SALE_QTY --> IDLE: cancel / menu
    CHECK_STOCK_PRODUCT --> IDLE: cancel / menu

    ADD_PRODUCT_PRICE --> ADD_PRODUCT_PRICE: invalid input (retry, max 3)
    RECORD_SALE_QTY --> RECORD_SALE_QTY: invalid input (retry, max 3)

    ADD_PRODUCT_PRICE --> ERROR: 3rd consecutive invalid input
    RECORD_SALE_QTY --> ERROR: 3rd consecutive invalid input
    ERROR --> IDLE: apology message
```

**Notes**

- `IDLE` is the resting state; every incoming message is routed by the Intent Resolver into one of the three primary flows (or `REPORT_PENDING`).
- `cancel` / `menu` is a universal override accepted from any non-`IDLE` state — it clears context and returns to `IDLE`.
- Invalid input re-prompts from the same state (up to 3 times) before the FSM forces a transition to `ERROR` → `IDLE`.
- A confirmed sale branches through a `LOW_STOCK_CHECK` decision point; if inventory drops below its threshold, a low-stock alert task is queued asynchronously before returning to `IDLE`.

### Diagram C: Asynchronous PDF Report Generation Flow

```mermaid
sequenceDiagram
    autonumber
    actor User
    participant API as FastAPI Webhook
    participant Worker as Celery Report Worker
    participant DB as PostgreSQL
    participant Sender as MessageSender

    User->>API: "report today"
    API->>Worker: Enqueue report_tasks.generate_daily_report(phone, date)
    API-->>User: "Generating your daily report... I'll send it in a moment."
    Note over API: Webhook returns 200 OK\nin under 100ms

    Worker->>DB: Query sales, inventory & low-stock data for the day
    DB-->>Worker: Sales rows, revenue total, top products

    Worker->>Worker: Render PDF (ReportLab)\nsummary table + totals + alerts
    Worker->>Worker: Store PDF in /tmp (UUID filename)

    Worker->>Sender: send_document(phone, pdf_path, caption)
    Sender-->>User: Deliver PDF as WhatsApp document

    Worker->>Worker: Delete temp file
    Worker->>Worker: FSM state → IDLE
```

**Notes**

- Steps 1–3 happen synchronously and fast — the webhook acknowledges the user immediately, before any real work starts.
- Steps 4 onward run entirely inside the `report_tasks` Celery queue (lower concurrency, expected to be slow — see §6.2).
- The PDF is generated with ReportLab, written to a temp file, delivered via `MessageSender.send_document()`, then cleaned up once delivery is confirmed.
- On completion, the FSM session for that phone number transitions back to `IDLE`.

---

## 4. Core Engineering Concepts & Design Decisions

### Stateful Conversations over Stateless Webhooks

WhatsApp webhooks send isolated HTTP `POST` payloads. SokoFlow uses Redis-backed session management ([ADR 001](docs/adr/001-redis-for-sessions.md)) under `session:{phone_number}` keys with a 30-minute TTL (`SESSION_TTL_SECONDS=1800`). The FSM tracks state, active step context, and transient user inputs across HTTP boundaries.

### Smart Workers, Dumb Webhooks

The FastAPI webhook endpoint only performs lightweight HMAC SHA-256 verification, payload validation, and Redis message deduplication. The payload is enqueued into Celery (`conversation_tasks` queue) within milliseconds, keeping webhook response times minimal and resilient against worker timeouts.

### Transaction-per-Item Sales Model

Rather than complex cart states (which increase drop-off risk during mobile chat interactions), sales are recorded as individual transaction events ([ADR 002](docs/adr/002-sales-data-modeling-single%20Row-vs-header-detail.md)).

### Snapshot Unit Pricing

When a sale is recorded, `sale.unit_price` is captured from `Product.price` at that exact timestamp ([ADR 003](docs/adr/003-sales-pricing-source.md)). This guarantees historical revenue reports remain accurate even if catalog product prices change later.

### Last Write Wins Concurrency

Product edits use a PATCH model evaluated under Last Write Wins ([ADR 004](docs/adr/004-last-write-for-updates.md)), optimizing for single-merchant operation scenarios typical in Kenyan SMEs without unnecessary locking overhead.

### SQL File Loader for Complex Reporting

Analytical and report aggregation queries are decoupled into raw `.sql` files under `app/sql/` and loaded dynamically via `app/sql/loader.py` ([ADR 005](docs/adr/005-sql-file-workflow-for-handwritten-queries.md)). This maintains ORM models for CRUD while enabling readable handwritten SQL for analytical joins.

### Best-Effort Asynchronous Alert Enqueuing

Database transactions for sales and inventory deduction commit authoritatively first. If stock drops below threshold, a low-stock alert Celery task is enqueued best-effort ([ADR 007](docs/adr/007-best-effort-low-stock-alert-enqueue.md)), preventing notification delivery failures from rolling back valid business transactions.

---

## 5. Tech Stack

| Layer               | Technology           | Description                                                          |
| :------------------ | :------------------- | :------------------------------------------------------------------- |
| **Core Framework**  | FastAPI (0.111.0)    | Asynchronous REST API & Webhook handler                              |
| **State Engine**    | Custom Python FSM    | Deterministic state machine with Intent Resolver                     |
| **Session Cache**   | Redis 7              | Session storage, deduplication & Celery broker                       |
| **Database**        | PostgreSQL 15        | Relational persistence with SQLAlchemy 2.0 (AsyncPG)                 |
| **Migrations**      | Alembic              | Version-controlled database schema migrations                        |
| **Task Queue**      | Celery 5.4           | Asynchronous conversation, alert, and report workers                 |
| **PDF Engine**      | ReportLab 4.2        | Dynamic PDF document generation for daily reports                    |
| **Package Manager** | uv                   | Lightning-fast Python package and venv management                    |
| **Code Quality**    | Ruff / MyPy / Pytest | Linting, strict type checking, and unit/integration testing          |
| **Containers**      | Docker & Compose     | Multi-container orchestration with profiles (`infra`, `full`, `dev`) |

---

## 6. Quick Start Guide

### Prerequisites

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) installed and running
- [Python 3.12](https://www.python.org/downloads/)
- [`uv`](https://github.com/astral-sh/uv) (recommended) or standard Python `venv`
- `make` utility

---

### Method A: Local Development Setup (Recommended)

Run infrastructure in Docker, while running the app and workers directly on your host machine for quick iteration.

1. **Clone repository:**

   ```bash
   git clone https://github.com/paul-murithi/SokoFlow.git
   cd SokoFlow
   ```

2. **Configure environment:**

   ```bash
   cp .env.example .env
   ```

3. **Start local infrastructure (PostgreSQL & Redis):**

   ```bash
   make infra
   ```

4. **Install Python dependencies:**

   ```bash
   uv sync --locked
   ```

5. **Run database migrations:**

   ```bash
   make migrate
   ```

6. **Start Application Services (in separate terminal windows):**
   - **FastAPI API server:**
     ```bash
     uv run uvicorn app.main:app --reload --port 8000
     ```
   - **Conversation Worker:**
     ```bash
     uv run celery -A app.tasks worker -Q conversation_tasks --loglevel=info
     ```
   - **Report Worker:**
     ```bash
     uv run celery -A app.tasks worker -Q report_tasks --loglevel=info
     ```
   - **Chat Simulator Web UI & Receiver:**
     ```bash
     uv run python tools/chat_simulator.py --server --port 3000
     ```

7. **Verify Health:**
   ```bash
   curl http://localhost:8000/health
   ```

---

### Method B: Full Stack Docker Setup (Production Simulation)

Run the entire ecosystem (API, workers, Beat scheduler, Redis, Postgres) inside Docker containers.

1. **Configure Docker environment:**

   ```bash
   cp .env.docker.example .env.docker
   ```

2. **Build and start full container stack:**

   ```bash
   make up-full
   ```

3. **Apply migrations inside container:**

   ```bash
   docker compose exec api alembic upgrade head
   ```

4. **Tail container logs:**

   ```bash
   make logs
   ```

5. **Stop full stack:**
   ```bash
   make down
   ```

---

## 7. Running the Chat Simulator

SokoFlow includes a built-in simulator that emulates WhatsApp webhook payloads, HMAC signing, and receiving asynchronous bot replies.

### Option 1: Web UI Simulator (Interactive Browser Interface)

1. Start the simulator server:
   ```bash
   uv run python tools/chat_simulator.py --server --port 3000
   ```
2. Open your browser to `http://localhost:3000`.
3. Type messages in the chat interface to test complete flows visually.

### Option 2: CLI Interactive Mode

Launch an interactive terminal chat session:

```bash
make simulate
```

or with custom parameters:

```bash
python tools/chat_simulator.py --phone 254712345678 --message "add product"
```

---

## 8. Example End-to-End Business Workflow

Below is a complete multi-turn conversation flow executed through the simulator:

### Step 1: Add a Product

- **User:** `add product`
- **Bot:** `"What is the name of the product you want to add?"`
- **User:** `Milk 1L`
- **Bot:** `"What is the selling price for Milk 1L in KES?"`
- **User:** `120`
- **Bot:** `"How many items of Milk 1L are currently in stock?"`
- **User:** `5`
- **Bot:** `"Please confirm adding Milk 1L at KES 120.00 with stock 5. Reply YES to confirm or CANCEL to abort."`
- **User:** `YES`
- **Bot:** `"Product 'Milk 1L' created successfully!"`

### Step 2: Record a Sale & Trigger Low-Stock Alert

- **User:** `record sale`
- **Bot:** `"Which product was sold?"`
- **User:** `Milk 1L`
- **Bot:** `"How many items of Milk 1L were sold?"`
- **User:** `4`
- **Bot:** `"Confirm sale of 4 x Milk 1L for KES 480.00? Reply YES to confirm."`
- **User:** `YES`
- **Bot:** `"Sale recorded! 4 x Milk 1L sold for KES 480.00."`
- **Bot (Async Alert):** `"Low Stock Alert: Milk 1L has only 1 remaining in stock."`

### Step 3: Switch Language & Generate PDF Daily Report

- **User:** `locale sw`
- **Bot:** `"This shop is now configured to use Swahili for outgoing messages."`
- **User:** `generate report`
- **Bot:** `"Tunamobilisha ripoti yako ya siku... utapokea hivi karibuni."`
- **Bot (Async Document):** _(Delivers `daily_report_2026_09_22.pdf` media file attached to chat)_

---

## 9. Testing & Code Quality

SokoFlow follows TDD practices with comprehensive unit and integration test suites.

### Running Tests & Coverage

```bash
uv run pytest
```

Current test results:

- **Pass Rate:** 100% (119 passed)
- **Measured Line Coverage:** **88%** (exceeds mandatory 85% project threshold)

### Linting & Static Type Analysis

```bash
# Run Ruff lint check
make lint

# Run Ruff code formatter
make format

# Run MyPy strict type checking
make typecheck
```

---

## 10. Repository Structure

```text
sokoflow/
├── app/
│   ├── api/               # FastAPI application, routes & webhook handler
│   │   └── routes/        # Endpoint definitions (webhook, health, products, sales, reports)
│   ├── core/              # Global configuration, database setup, redis connection & error handling
│   ├── dto/               # Data Transfer Objects for service boundaries
│   ├── fsm/               # Conversation Finite State Machine engine & handlers
│   │   └── flows/         # Flow-specific logic (add product, record sale, stock lookup, report)
│   ├── models/            # SQLAlchemy database domain entities (Shop, Product, Inventory, Sale)
│   ├── repositories/      # Database access layer & data queries
│   ├── schemas/           # Pydantic schemas for request/response validation
│   ├── services/          # Core domain business logic, PDF generation & localization
│   ├── sql/               # Handwritten SQL files for analytical reports & SQL loader
│   ├── utils/             # Helper utilities, error mappings & custom exceptions
│   └── workers/           # Celery task definitions, queues, & MessageSender integration
├── alembic/               # Alembic database migration scripts & versions
├── celery_app/            # Celery instance configuration & queue bindings
├── docs/                  # Architecture Decision Records (ADRs) & technical documentation
│   └── adr/               # Numbered ADR markdown files (001 - 007)
├── tools/                 # Developer tools (chat simulator Web UI/CLI)
├── tests/                 # Automated test suite (unit, integration, fixtures & factories)
├── Dockerfile             # Multi-stage production container build definition
├── docker-compose.yml     # Services specification (Postgres, Redis, API, Workers, Beat, Simulator)
├── Makefile               # Task runner & developer shortcut commands
└── pyproject.toml         # Dependencies, tools configuration (Ruff, MyPy, Pytest)
```

---

## 11. Configuration & Environment Variables

| Variable                | Description                                                             | Default / Example                                                    |
| :---------------------- | :---------------------------------------------------------------------- | :------------------------------------------------------------------- |
| `APP_ENV`               | Application execution environment (`development`, `test`, `production`) | `development`                                                        |
| `DATABASE_URL`          | PostgreSQL connection string (asyncpg driver)                           | `postgresql+asyncpg://sokoflow:sokoflow_dev@localhost:5432/sokoflow` |
| `REDIS_URL`             | Redis instance URL for FSM session caching                              | `redis://localhost:6379/0`                                           |
| `CELERY_BROKER_URL`     | Redis URL for Celery task broker                                        | `redis://localhost:6379/1`                                           |
| `SESSION_TTL_SECONDS`   | Inactivity TTL for conversational FSM sessions                          | `1800` (30 mins)                                                     |
| `DEDUP_TTL_SECONDS`     | Inactivity TTL for webhook message deduplication                        | `60` (1 min)                                                         |
| `MAX_FSM_ERRORS`        | Max invalid consecutive inputs before resetting FSM state to IDLE       | `3`                                                                  |
| `SENDER_BACKEND`        | Transport backend adapter (`mock` for simulator, `whatsapp` stub)       | `mock`                                                               |
| `MESSAGE_SENDER_URL`    | Outbound callback endpoint for mock delivery                            | `http://localhost:3000`                                              |
| `WHATSAPP_APP_SECRET`   | Secret key used for HMAC SHA-256 webhook signature verification         | _(Set in `.env`)_                                                    |
| `WHATSAPP_VERIFY_TOKEN` | Verification token for WhatsApp webhook handshake                       | _(Set in `.env`)_                                                    |

---

## 12. Scope & Intentional Limitations

- **Simulated Transport:** Live Meta WhatsApp Cloud API credentials are not required. Outbound messaging uses the `MockMessageSender` contract and the built-in Chat Simulator.
- **Single-Item Transactions:** The current FSM records sales one item per conversation flow. Multi-item cart capabilities are intentionally deferred ([ADR 002](docs/adr/002-sales-data-modeling-single%20Row-vs-header-detail.md)).
- **Best-Effort Alerts:** Low-stock notifications are dispatched best-effort post-commit without a transactional outbox table ([ADR 007](docs/adr/007-best-effort-low-stock-alert-enqueue.md)).
- **Last Write Wins Updates:** Concurrent product updates overwrite without optimistic version locking ([ADR 004](docs/adr/004-last-write-for-updates.md)).

---

## 13. Architecture Decision Records (ADRs)

Key design decisions are documented in detail within [`docs/adr/`](docs/adr/):

- [ADR 001: Use Redis for FSM Session Storage](docs/adr/001-redis-for-sessions.md)
- [ADR 002: Sales Data Modeling – Single Row vs Header-Detail](docs/adr/002-sales-data-modeling-single%20Row-vs-header-detail.md)
- [ADR 003: Sales Unit Price Source Snapshotting](docs/adr/003-sales-pricing-source.md)
- [ADR 004: Last Write Wins Strategy for Product Updates](docs/adr/004-last-write-for-updates.md)
- [ADR 005: SQL File Workflow for Handwritten Queries](docs/adr/005-sql-file-workflow-for-handwritten-queries.md)
- [ADR 006: Handle Large Low-Stock Result Sets in Daily Reports](docs/adr/006-handle-large-low-stock-result-sets-in-daily-reports.md)
- [ADR 007: Best-Effort Low-Stock Alert Enqueue](docs/adr/007-best-effort-low-stock-alert-enqueue.md)

---

## 14. License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
