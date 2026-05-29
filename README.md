# SokoFlow

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python: 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/release/python-3120/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.111.0-green.svg)](https://fastapi.tiangolo.com/)

**Headless WhatsApp ERP for Kenyan SMEs**

SokoFlow is a backend ERP engine designed for small and medium-sized enterprises in Kenya. It exposes its entire interface through WhatsApp conversations, eliminating the need for app downloads, complex training, or traditional UI navigation. In SokoFlow, **the interface is the conversation.**

---

## The Vision

Traditional ERPs are often too complex or expensive for SMEs. SokoFlow bridges this gap by leveraging a platform everyone already uses: WhatsApp. By turning complex business processes into natural conversations, we empower business owners to manage inventory, sales, and reports right from their pockets.

## Key Features

- **Conversational Interface:** Manage your business via simple WhatsApp messages.
- **State-Driven Workflow:** A robust Finite State Machine (FSM) ensures conversations are consistent and reliable.
- **Real-Time Inventory:** Track products and stock levels as transactions happen.
- **Automated Reporting:** Generate PDF sales reports and receipts on demand.
- **Asynchronous Processing:** Powered by Celery for high performance and reliability.
- **Built for Scale:** Cloud-native architecture ready for production.

## Tech Stack

| Layer              | Technology                     |
| ------------------ | ------------------------------ |
| **Core API**       | FastAPI + Pydantic             |
| **Worker / Queue** | Celery + Redis                 |
| **State Engine**   | Custom FSM + Redis Sessions    |
| **Database**       | PostgreSQL 15                  |
| **Reports**        | ReportLab (PDF Generation)     |
| **Infrastructure** | Docker + Docker Compose        |
| **Quality**        | Ruff, MyPy, Pytest (TDD-first) |

---

## Quick Start

### Prerequisites

- [Docker Desktop](https://www.docker.com/products/docker-desktop/)
- [Python 3.12+](https://www.python.org/downloads/)
- `make` utility

### Setup

1. **Clone the repository:**

   ```bash
   git clone https://github.com/your-username/sokoflow.git
   cd sokoflow
   ```

2. **Configure environment:**

   ```bash
   cp .env.example .env
   # Edit .env to set your local secrets and configurations
   ```

3. **Start the services:**

   ```bash
   make up
   ```

4. **Verify installation:**
   ```bash
   curl http://localhost:8000/health
   ```

---

## Engineering Principles

1. **Conversations as State Machines:** We don't just parse strings; we manage stateful interactions.
2. **Smart Workers, Dumb Webhooks:** Logic resides in the worker layer for maximum responsiveness.
3. **Contract-First Integration:** External systems are handled via strict interfaces.
4. **Observable by Design:** Logging, correlation IDs, and health checks are baked in.
5. **Simulation over Integration:** We use a custom chat simulator to test flows before touching real APIs.

## Roadmap

- **W1–4:** Core business logic (products, inventory, sales) — TDD-first.
- **W5–8:** Dockerization, CI/CD, and staging environments.
- **W9–12:** FSM conversation engine & WhatsApp integration.
- **W13–16:** Async reports, chaos testing, and Swahili support.

---

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

_Built for the future of Kenyan SMEs._
