# ── SokoFlow Developer Makefile ──────────────────────────────────
# Usage: make <target>
# Run `make help` to see all available commands.

.PHONY: help infra infra-down up-full down logs shell \
        test lint format typecheck \
        migrate migration simulate chaos clean

# ── Default ──────────────────────────────────────────────────────
help:
	@.venv/lib/python3.12/site-packages/PIL/__pycache__/ImageChops.cpython-312.pyc ""
	@.venv/lib/python3.12/site-packages/PIL/__pycache__/ImageChops.cpython-312.pyc "SokoFlow — Available Commands"
	@.venv/lib/python3.12/site-packages/PIL/__pycache__/ImageChops.cpython-312.pyc "─────────────────────────────────────────────────────────"
	@.venv/lib/python3.12/site-packages/PIL/__pycache__/ImageChops.cpython-312.pyc "DAILY DEVELOPMENT:"
	@.venv/lib/python3.12/site-packages/PIL/__pycache__/ImageChops.cpython-312.pyc "  make infra              Start Postgres + Redis only"
	@.venv/lib/python3.12/site-packages/PIL/__pycache__/ImageChops.cpython-312.pyc "  make infra-down         Stop infra containers"
	@.venv/lib/python3.12/site-packages/PIL/__pycache__/ImageChops.cpython-312.pyc "  Then in separate terminals:"
	@.venv/lib/python3.12/site-packages/PIL/__pycache__/ImageChops.cpython-312.pyc "    uvicorn app.main:app --reload"
	@.venv/lib/python3.12/site-packages/PIL/__pycache__/ImageChops.cpython-312.pyc "    celery -A app.tasks worker -Q conversation_tasks --loglevel=debug"
	@.venv/lib/python3.12/site-packages/PIL/__pycache__/ImageChops.cpython-312.pyc "    celery -A app.tasks worker -Q report_tasks --loglevel=debug"
	@.venv/lib/python3.12/site-packages/PIL/__pycache__/ImageChops.cpython-312.pyc ""
	@.venv/lib/python3.12/site-packages/PIL/__pycache__/ImageChops.cpython-312.pyc "FULL STACK IN DOCKER (production simulation):"
	@.venv/lib/python3.12/site-packages/PIL/__pycache__/ImageChops.cpython-312.pyc "  make up-full            Build and start everything in Docker"
	@.venv/lib/python3.12/site-packages/PIL/__pycache__/ImageChops.cpython-312.pyc "  make down               Stop all Docker services"
	@.venv/lib/python3.12/site-packages/PIL/__pycache__/ImageChops.cpython-312.pyc "  make logs               Tail all container logs"
	@.venv/lib/python3.12/site-packages/PIL/__pycache__/ImageChops.cpython-312.pyc "  make shell              Open shell inside api container"
	@.venv/lib/python3.12/site-packages/PIL/__pycache__/ImageChops.cpython-312.pyc ""
	@.venv/lib/python3.12/site-packages/PIL/__pycache__/ImageChops.cpython-312.pyc "CODE QUALITY:"
	@.venv/lib/python3.12/site-packages/PIL/__pycache__/ImageChops.cpython-312.pyc "  make test               Run pytest (requires infra running)"
	@.venv/lib/python3.12/site-packages/PIL/__pycache__/ImageChops.cpython-312.pyc "  make lint               Run flake8"
	@.venv/lib/python3.12/site-packages/PIL/__pycache__/ImageChops.cpython-312.pyc "  make format             Run black"
	@.venv/lib/python3.12/site-packages/PIL/__pycache__/ImageChops.cpython-312.pyc "  make typecheck          Run mypy"
	@.venv/lib/python3.12/site-packages/PIL/__pycache__/ImageChops.cpython-312.pyc ""
	@.venv/lib/python3.12/site-packages/PIL/__pycache__/ImageChops.cpython-312.pyc "DATABASE:"
	@.venv/lib/python3.12/site-packages/PIL/__pycache__/ImageChops.cpython-312.pyc "  make migrate            Apply pending Alembic migrations"
	@.venv/lib/python3.12/site-packages/PIL/__pycache__/ImageChops.cpython-312.pyc "  make migration m='msg'  Generate new migration"
	@.venv/lib/python3.12/site-packages/PIL/__pycache__/ImageChops.cpython-312.pyc "─────────────────────────────────────────────────────────"

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
