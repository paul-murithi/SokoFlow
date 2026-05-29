# SokoFlow Developer Makefile 
# Usage: make <target>

.PHONY: help up down logs shell test lint format typecheck migrate \
        simulate chaos clean

# Default
help:
	@echo ""
	@echo "SokoFlow — Available Commands"
	@echo "─────────────────────────────────────────────────────"
	@echo "  make up          Start all services (detached)"
	@echo "  make dev         Start all services + simulator"
	@echo "  make down        Stop all services"
	@echo "  make logs        Tail logs for all services"
	@echo "  make shell       Open a shell inside the api container"
	@echo ""
	@echo "  make test        Run the full test suite with coverage"
	@echo "  make lint        Run flake8 linter"
	@echo "  make format      Run black formatter"
	@echo "  make typecheck   Run mypy type checker"
	@echo ""
	@echo "  make migrate     Run pending Alembic migrations"
	@echo "  make migration m='message'   Create new migration"
	@echo ""
	@echo "  make simulate p=254712345678 msg='hello'  Send a test message"
	@echo "  make chaos       Run the chaos test suite"
	@echo ""
	@echo "  make clean       Remove containers, volumes, cache"
	@echo "─────────────────────────────────────────────────────"

# Docker
up:
	docker compose up -d

dev:
	docker compose --profile dev up -d

down:
	docker compose down

logs:
	docker compose logs -f

shell:
	docker compose exec api bash

# Testing
test:
	docker compose exec api pytest

test-local:
	pytest

lint:
	flake8 app tests

format:
	black app tests tools

typecheck:
	mypy app --ignore-missing-imports

# Database
migrate:
	docker compose exec api alembic upgrade head

migration:
	docker compose exec api alembic revision --autogenerate -m "$(m)"

# Simulator
simulate:
	python tools/chat_simulator.py --phone $(p) --message "$(msg)"

# Chaos
chaos:
	python tools/chaos_runner.py

# Clean
clean:
	docker compose down -v --remove-orphans
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	find . -type d -name ".pytest_cache" -exec rm -rf {} +
	find . -type d -name "htmlcov" -exec rm -rf {} +
	rm -f .coverage coverage.xml
