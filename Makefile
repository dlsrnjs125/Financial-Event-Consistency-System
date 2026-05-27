# Variables
APP_NAME ?= financial-event-api
APP_MODULE ?= app.main:app
HOST ?= 0.0.0.0
PORT ?= 8000

# Python
PYTHON ?= .venv/bin/python
PIP ?= .venv/bin/pip
UVICORN ?= .venv/bin/uvicorn
BLACK ?= .venv/bin/black
ISORT ?= .venv/bin/isort
FLAKE8 ?= .venv/bin/flake8

# Docker
DOCKER ?= docker
DOCKER_COMPOSE ?= docker-compose

# Paths
BACKEND_DIR ?= backend
TEST_DIR ?= backend/tests
FORMAT_PATHS ?= backend/app backend/tests/unit/test_phase1_app.py
LINT_PATHS ?= backend/app backend/tests/unit/test_phase1_app.py

.PHONY: help
help: ## Show this help message
	@echo "Usage:"
	@grep -E '^[a-zA-Z0-9_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  %-24s %s\n", $$1, $$2}'
	@echo ""
	@echo "Quick workflow:"
	@echo "  make local-check       # Check local tools and app structure"
	@echo "  make dev               # Run FastAPI locally with reload"
	@echo "  make check             # Run format-check, lint, and tests"
	@echo "  make local-bg          # Run Docker Compose stack in background"

# Local development
.PHONY: local-check
local-check: ## Check local development prerequisites
	@echo "Checking local environment..."
	@$(PYTHON) --version
	@$(PYTHON) -c "import fastapi, sqlalchemy, redis, prometheus_client; print('Required backend packages found')"
	@test -f backend/app/main.py && echo "backend/app/main.py found"
	@test -f backend/requirements.txt && echo "backend/requirements.txt found"
	@test -f docker-compose.yml && echo "docker-compose.yml found"

.PHONY: install
install: ## Install backend dependencies into .venv
	$(PIP) install -r backend/requirements.txt

.PHONY: dev
dev: ## Run FastAPI development server with reload
	PYTHONPATH=$(BACKEND_DIR) $(UVICORN) $(APP_MODULE) --host $(HOST) --port $(PORT) --reload

.PHONY: run
run: ## Run FastAPI server without reload
	PYTHONPATH=$(BACKEND_DIR) $(UVICORN) $(APP_MODULE) --host $(HOST) --port $(PORT)

.PHONY: local-kill
local-kill: ## Stop local uvicorn process on PORT
	@pkill -f "uvicorn $(APP_MODULE)" 2>/dev/null || echo "No matching uvicorn process found"
	@lsof -ti:$(PORT) | xargs kill -9 2>/dev/null || echo "Port $(PORT) is free"

# Docker Compose
.PHONY: docker-check
docker-check: ## Check Docker daemon status
	@$(DOCKER) info >/dev/null 2>&1 || (echo "Docker is not running" && exit 1)
	@echo "Docker is running"

.PHONY: local
local: docker-check ## Start Docker Compose stack in foreground
	$(DOCKER_COMPOSE) up --build

.PHONY: local-bg
local-bg: docker-check ## Start Docker Compose stack in background
	$(DOCKER_COMPOSE) up --build -d
	@echo ""
	@echo "Service URLs:"
	@echo "  API blue:    http://localhost:8000"
	@echo "  API green:   http://localhost:8001"
	@echo "  Nginx:       http://localhost:8080"
	@echo "  Prometheus:  http://localhost:9090"
	@echo "  Grafana:     http://localhost:3000"
	@echo ""
	@echo "Check status: make local-status"
	@echo "Stop stack:   make local-stop"

.PHONY: local-stop
local-stop: ## Stop Docker Compose stack
	$(DOCKER_COMPOSE) down

.PHONY: local-restart
local-restart: ## Restart Docker Compose stack
	@$(MAKE) local-stop
	@$(MAKE) local-bg

.PHONY: local-status
local-status: ## Show Docker Compose service status
	$(DOCKER_COMPOSE) ps

.PHONY: local-logs
local-logs: ## Follow Docker Compose logs
	$(DOCKER_COMPOSE) logs -f

.PHONY: local-cleanup
local-cleanup: ## Stop Docker Compose stack and remove volumes
	$(DOCKER_COMPOSE) down -v

.PHONY: docker-up
docker-up: local-bg ## Alias for local-bg

.PHONY: docker-down
docker-down: local-stop ## Alias for local-stop

.PHONY: docker-restart
docker-restart: local-restart ## Alias for local-restart

.PHONY: docker-logs
docker-logs: local-logs ## Alias for local-logs

.PHONY: start
start: local-bg ## Alias for local-bg

.PHONY: stop
stop: local-stop ## Alias for local-stop

.PHONY: restart
restart: local-restart ## Alias for local-restart

# Testing and quality
.PHONY: test
test: ## Run all backend tests
	$(PYTHON) -m pytest

.PHONY: test-unit
test-unit: ## Run unit tests
	$(PYTHON) -m pytest backend/tests/unit -v

.PHONY: test-integration
test-integration: ## Run integration tests
	$(PYTHON) -m pytest backend/tests/integration -v

.PHONY: test-consistency
test-consistency: ## Run consistency tests
	$(PYTHON) -m pytest backend/tests/consistency -v

.PHONY: format
format: ## Format Phase 1 backend code
	$(ISORT) --profile black -p app $(FORMAT_PATHS)
	$(BLACK) $(FORMAT_PATHS)

.PHONY: format-check
format-check: ## Check Phase 1 backend formatting
	$(ISORT) --profile black -p app --check-only $(FORMAT_PATHS)
	$(BLACK) --check $(FORMAT_PATHS)

.PHONY: lint
lint: ## Run flake8 for Phase 1 backend code
	$(FLAKE8) --max-line-length=88 --extend-ignore=E203,W503 $(LINT_PATHS)

.PHONY: check
check: format-check lint test ## Run format-check, lint, and tests

# Health checks
.PHONY: health
health: ## Call /health
	curl -s http://localhost:$(PORT)/health
	@echo ""

.PHONY: ready
ready: ## Call /ready
	curl -s http://localhost:$(PORT)/ready
	@echo ""

.PHONY: metrics
metrics: ## Call /metrics
	curl -s http://localhost:$(PORT)/metrics

# Maintenance
.PHONY: clean
clean: ## Remove local Python cache directories
	find . -type d -name "__pycache__" -prune -exec rm -rf {} +
	find . -type d -name ".pytest_cache" -prune -exec rm -rf {} +
	find . -type d -name ".mypy_cache" -prune -exec rm -rf {} +
