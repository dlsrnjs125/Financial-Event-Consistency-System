.PHONY: help install dev run test test-unit test-integration test-consistency format format-check lint check docker-up docker-down docker-restart docker-logs health ready metrics clean

PYTHON ?= .venv/bin/python
PIP ?= .venv/bin/pip
UVICORN ?= .venv/bin/uvicorn
BLACK ?= .venv/bin/black
ISORT ?= .venv/bin/isort
FLAKE8 ?= .venv/bin/flake8
PYTEST ?= .venv/bin/pytest
DOCKER_COMPOSE ?= docker-compose

APP_MODULE ?= app.main:app
HOST ?= 0.0.0.0
PORT ?= 8000
FORMAT_PATHS ?= backend/app backend/tests/unit/test_phase1_app.py
LINT_PATHS ?= backend/app backend/tests/unit/test_phase1_app.py

help:
	@echo "Financial Event Consistency System"
	@echo ""
	@echo "Backend"
	@echo "  make install              Install backend dependencies into .venv"
	@echo "  make dev                  Run FastAPI with reload"
	@echo "  make run                  Run FastAPI without reload"
	@echo ""
	@echo "Quality"
	@echo "  make test                 Run all backend tests"
	@echo "  make test-unit            Run unit tests"
	@echo "  make test-integration     Run integration tests"
	@echo "  make test-consistency     Run consistency tests"
	@echo "  make format               Run black and isort"
	@echo "  make format-check         Check black and isort formatting"
	@echo "  make lint                 Run flake8"
	@echo "  make check                Run format-check, lint, and tests"
	@echo ""
	@echo "Docker"
	@echo "  make docker-up            Start docker compose services"
	@echo "  make docker-down          Stop docker compose services"
	@echo "  make docker-restart       Restart docker compose services"
	@echo "  make docker-logs          Tail docker compose logs"
	@echo ""
	@echo "Health"
	@echo "  make health               Call /health"
	@echo "  make ready                Call /ready"
	@echo "  make metrics              Call /metrics"

install:
	$(PIP) install -r backend/requirements.txt

dev:
	PYTHONPATH=backend $(UVICORN) $(APP_MODULE) --host $(HOST) --port $(PORT) --reload

run:
	PYTHONPATH=backend $(UVICORN) $(APP_MODULE) --host $(HOST) --port $(PORT)

test:
	$(PYTHON) -m pytest

test-unit:
	$(PYTHON) -m pytest backend/tests/unit -v

test-integration:
	$(PYTHON) -m pytest backend/tests/integration -v

test-consistency:
	$(PYTHON) -m pytest backend/tests/consistency -v

format:
	$(ISORT) --profile black -p app $(FORMAT_PATHS)
	$(BLACK) $(FORMAT_PATHS)

format-check:
	$(ISORT) --profile black -p app --check-only $(FORMAT_PATHS)
	$(BLACK) --check $(FORMAT_PATHS)

lint:
	$(FLAKE8) --max-line-length=88 --extend-ignore=E203,W503 $(LINT_PATHS)

check: format-check lint test

docker-up:
	$(DOCKER_COMPOSE) up -d

docker-down:
	$(DOCKER_COMPOSE) down

docker-restart:
	$(DOCKER_COMPOSE) restart

docker-logs:
	$(DOCKER_COMPOSE) logs -f

health:
	curl -s http://localhost:$(PORT)/health
	@echo ""

ready:
	curl -s http://localhost:$(PORT)/ready
	@echo ""

metrics:
	curl -s http://localhost:$(PORT)/metrics

clean:
	find . -type d -name "__pycache__" -prune -exec rm -rf {} +
	find . -type d -name ".pytest_cache" -prune -exec rm -rf {} +
	find . -type d -name ".mypy_cache" -prune -exec rm -rf {} +
