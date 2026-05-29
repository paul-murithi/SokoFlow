# ── SokoFlow Developer Makefile ──────────────────────────────────
# Usage: make <target>
# Run `make help` to see all available commands.

.PHONY: help infra infra-down up-full down logs shell \
        test lint format typecheck \
        migrate migration simulate chaos clean

# ── Default ──────────────────────────────────────────────────────
help:
	@echo ""
	@echo "SokoFlow — Available Commands"
	@echo "─────────────────────────────────────────────────────────"
	@echo "DAILY DEVELOPMENT:"
	@echo "  make infra              Start Postgres + Redis only"
	@echo "  make infra-down         Stop infra containers"
	@echo "  Then in separate terminals:"
	@echo "    uvicorn app.main:app --reload"
	@echo "    celery -A app.tasks worker -Q conversation_tasks --loglevel=debug"
	@echo "    celery -A app.tasks worker -Q report_tasks --loglevel=debug"
	@echo ""
	@echo "FULL STACK IN DOCKER (production simulation):"
	@echo "  make up-full            Build and start everything in Docker"
	@echo "  make down               Stop all Docker services"
	@echo "  make logs               Tail all container logs"
	@echo "  make shell              Open shell inside api container"
	@echo ""
	@echo "CODE QUALITY:"
	@echo "  make test               Run pytest (requires infra running)"
	@echo "  make lint               Run flake8"
	@echo "  make format             Run black"
	@echo "  make typecheck          Run mypy"
	@echo ""
	@echo "DATABASE:"
	@echo "  make migrate            Apply pending Alembic migrations"
	@echo "  make migration m='msg'  Generate new migration"
	@echo "─────────────────────────────────────────────────────────"

# ── Infrastructure only ───────────────────────────────────────────
infra:
	docker compose up postgres redis -d

infra-down:
	docker compose stop postgres redis

# ── Full stack in Docker ──────────────────────────────────────────
up-full:
	docker compose --profile full up -d

down:
	docker compose --profile full down

logs:
	docker compose --profile full logs -f

shell:
	docker compose exec api bash

# ── Testing & quality (run locally against infra) ─────────────────
test:
	pytest

lint:
	flake8 app tests

format:
	black app tests tools

typecheck:
	mypy app --ignore-missing-imports

# ── Database ──────────────────────────────────────────────────────
migrate:
	alembic upgrade head

migration:
	alembic revision --autogenerate -m "$(m)"

# ── Simulator & chaos ─────────────────────────────────────────────
simulate:
	python tools/chat_simulator.py --phone $(p) --message "$(msg)"

chaos:
	python tools/chaos_runner.py

# ── Clean ─────────────────────────────────────────────────────────
clean:
	docker compose --profile full down -v --remove-orphans
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	find . -type d -name ".pytest_cache" -exec rm -rf {} +
	rm -f .coverage coverage.xml
