# Variables
APP_NAME ?= financial-event-api
APP_MODULE ?= app.main:app
HOST ?= 0.0.0.0
PORT ?= 8000
BASE_URL ?= http://localhost:8080
CLIENT_ID ?= bank-a
CLIENT_SECRET ?= change-me-secret
ACCOUNT_NO ?= ACC-001

# Python
PYTHON ?= .venv/bin/python
PIP ?= .venv/bin/pip
UVICORN ?= .venv/bin/uvicorn
BLACK ?= .venv/bin/black
ISORT ?= .venv/bin/isort
FLAKE8 ?= .venv/bin/flake8
RUFF ?= .venv/bin/ruff

# Docker
DOCKER ?= docker
DOCKER_COMPOSE ?= docker compose
DOCKER_COMPOSE_PERF ?= $(DOCKER_COMPOSE) -f docker-compose.yml -f docker-compose.perf.yml
K6 ?= k6

# Paths
BACKEND_DIR ?= backend
TEST_DIR ?= backend/tests
FORMAT_PATHS ?= backend/app backend/tests/unit/test_phase1_app.py
LINT_PATHS ?= backend/app backend/tests/unit/test_phase1_app.py
QUALITY_PATHS ?= backend/app backend/tests

.PHONY: help
help: ## Show this help message
	@echo "Usage:"
	@grep -E '^[a-zA-Z0-9_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  %-24s %s\n", $$1, $$2}'
	@echo ""
	@echo "Quick workflow:"
	@echo "  make local-check       # Check local tools and app structure"
	@echo "  make dev               # Run FastAPI locally with reload"
	@echo "  make check             # Run format-check, lint, and tests"
	@echo "  make final-check       # Format, lint, compile, and test before PR"
	@echo "  make local-bg          # Run Docker Compose stack in background"
	@echo "  make k6-smoke          # Run Phase 9 k6 smoke test"

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

.PHONY: local-rebuild
local-rebuild: docker-check ## Rebuild and recreate local API/Nginx services
	$(DOCKER_COMPOSE) up -d --build --force-recreate api-blue nginx

.PHONY: local-perf-bg
local-perf-bg: docker-check ## Start Docker Compose stack with Phase 9 perf Nginx profile
	$(DOCKER_COMPOSE_PERF) up --build -d

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
format: ## Format backend code and tests
	$(ISORT) --profile black -p app $(QUALITY_PATHS)
	$(BLACK) $(QUALITY_PATHS)
	$(RUFF) format $(BACKEND_DIR)

.PHONY: format-check
format-check: ## Check backend formatting
	$(ISORT) --profile black -p app --check-only $(QUALITY_PATHS)
	$(BLACK) --check $(QUALITY_PATHS)
	$(RUFF) format --check $(BACKEND_DIR)

.PHONY: lint
lint: ## Run lint checks for backend code and tests
	$(FLAKE8) --max-line-length=88 --extend-ignore=E203,W503 $(QUALITY_PATHS)
	$(RUFF) check $(BACKEND_DIR)

.PHONY: ruff-format
ruff-format: ## Format backend with Ruff
	$(RUFF) format $(BACKEND_DIR)

.PHONY: ruff-check
ruff-check: ## Check backend with Ruff
	$(RUFF) check $(BACKEND_DIR)

.PHONY: compile
compile: ## Compile backend Python files
	cd $(BACKEND_DIR) && ../$(PYTHON) -m compileall app tests

.PHONY: check
check: format-check lint test ## Run format-check, lint, and tests

.PHONY: final-check
final-check: format lint compile test ## Format, lint, compile, and test before PR

# k6 performance tests
.PHONY: k6-smoke
k6-smoke: ## Run Phase 9 k6 smoke test
	@BASE_URL=$(BASE_URL) CLIENT_ID=$(CLIENT_ID) CLIENT_SECRET=$(CLIENT_SECRET) ACCOUNT_NO=$(ACCOUNT_NO) $(K6) run tests/k6/smoke-test.js

.PHONY: k6-normal
k6-normal: ## Run Phase 9 k6 normal load test
	@BASE_URL=$(BASE_URL) CLIENT_ID=$(CLIENT_ID) CLIENT_SECRET=$(CLIENT_SECRET) ACCOUNT_NO=$(ACCOUNT_NO) $(K6) run tests/k6/normal-load.js

.PHONY: k6-peak
k6-peak: ## Run Phase 9 k6 peak load test
	@BASE_URL=$(BASE_URL) CLIENT_ID=$(CLIENT_ID) CLIENT_SECRET=$(CLIENT_SECRET) ACCOUNT_NO=$(ACCOUNT_NO) $(K6) run tests/k6/peak-load.js

.PHONY: k6-duplicate
k6-duplicate: ## Run Phase 9 k6 duplicate storm test
	@BASE_URL=$(BASE_URL) CLIENT_ID=$(CLIENT_ID) CLIENT_SECRET=$(CLIENT_SECRET) ACCOUNT_NO=$(ACCOUNT_NO) $(K6) run tests/k6/duplicate-storm.js

.PHONY: k6-redis-down
k6-redis-down: ## Run Phase 9 k6 Redis-down scenario after pausing Redis separately
	@echo "Expected procedure: docker compose pause redis && make k6-redis-down && docker compose unpause redis"
	@BASE_URL=$(BASE_URL) CLIENT_ID=$(CLIENT_ID) CLIENT_SECRET=$(CLIENT_SECRET) ACCOUNT_NO=$(ACCOUNT_NO) $(K6) run tests/k6/redis-down-test.js

.PHONY: k6-redis-down-check
k6-redis-down-check: ## Pause Redis, run redis-down k6 scenario, then unpause Redis
	@set -e; \
	$(DOCKER_COMPOSE) pause redis; \
	trap '$(DOCKER_COMPOSE) unpause redis' EXIT; \
	$(MAKE) k6-redis-down

.PHONY: k6-verify
k6-verify: ## Run post-k6 PostgreSQL consistency verification SQL
	@$(DOCKER_COMPOSE) exec -T postgres psql -U postgres -d financial_events < tests/k6/sql/verify-consistency.sql

.PHONY: k6-all
k6-all: k6-smoke k6-normal k6-peak k6-duplicate ## Run Phase 9 k6 tests except Redis-down

.PHONY: perf-check
perf-check: k6-smoke k6-duplicate k6-verify ## Run quick Phase 9 performance sanity checks

.PHONY: phase9-check
phase9-check: perf-check ## Alias for Phase 9 performance sanity checks

.PHONY: phase9-full
phase9-full: k6-smoke k6-normal k6-peak k6-duplicate k6-redis-down-check k6-verify ## Run all Phase 9 k6 scenarios and verification

.PHONY: perf-cache-off
perf-cache-off: ## Run duplicate storm with Redis lock on and idempotency cache off
	@IDEMPOTENCY_CACHE_ENABLED=false REDIS_LOCK_ENABLED=true $(DOCKER_COMPOSE_PERF) up -d --build --force-recreate api-blue nginx
	@$(MAKE) k6-duplicate
	@$(MAKE) k6-verify

.PHONY: perf-cache-on
perf-cache-on: ## Run duplicate storm with Redis lock and idempotency cache on
	@IDEMPOTENCY_CACHE_ENABLED=true REDIS_LOCK_ENABLED=true $(DOCKER_COMPOSE_PERF) up -d --build --force-recreate api-blue nginx
	@$(MAKE) k6-duplicate
	@$(MAKE) k6-verify

.PHONY: perf-lock-off
perf-lock-off: ## Run duplicate storm with Redis lock off and idempotency cache on
	@REDIS_LOCK_ENABLED=false IDEMPOTENCY_CACHE_ENABLED=true $(DOCKER_COMPOSE_PERF) up -d --build --force-recreate api-blue nginx
	@$(MAKE) k6-duplicate
	@$(MAKE) k6-verify

.PHONY: perf-lock-on
perf-lock-on: ## Run duplicate storm with Redis lock and idempotency cache on
	@REDIS_LOCK_ENABLED=true IDEMPOTENCY_CACHE_ENABLED=true $(DOCKER_COMPOSE_PERF) up -d --build --force-recreate api-blue nginx
	@$(MAKE) k6-duplicate
	@$(MAKE) k6-verify

.PHONY: perf-db-pool-5
perf-db-pool-5: ## Run peak load with DB pool size 5
	@DB_POOL_SIZE=5 DB_MAX_OVERFLOW=0 $(DOCKER_COMPOSE_PERF) up -d --build --force-recreate api-blue nginx
	@$(MAKE) k6-peak
	@$(MAKE) k6-verify

.PHONY: perf-db-pool-10
perf-db-pool-10: ## Run peak load with DB pool size 10
	@DB_POOL_SIZE=10 DB_MAX_OVERFLOW=5 $(DOCKER_COMPOSE_PERF) up -d --build --force-recreate api-blue nginx
	@$(MAKE) k6-peak
	@$(MAKE) k6-verify

.PHONY: perf-db-pool-20
perf-db-pool-20: ## Run peak load with DB pool size 20
	@DB_POOL_SIZE=20 DB_MAX_OVERFLOW=10 $(DOCKER_COMPOSE_PERF) up -d --build --force-recreate api-blue nginx
	@$(MAKE) k6-peak
	@$(MAKE) k6-verify

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
