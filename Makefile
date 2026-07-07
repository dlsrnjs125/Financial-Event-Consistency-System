# Variables
APP_NAME ?= financial-event-api
APP_MODULE ?= app.main:app
HOST ?= 0.0.0.0
PORT ?= 8000
BASE_URL ?= http://localhost:8080
INTERNAL_BASE_URL ?= http://localhost:8081
GREEN_URL ?= http://localhost:8001
CLIENT_ID ?= bank-a
CLIENT_SECRET ?= change-me-secret
ACCOUNT_NO ?= ACC-001
DUMP_FILE ?=

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
DOCKER_COMPOSE_MONITORING ?= $(DOCKER_COMPOSE) -f docker-compose.yml -f docker-compose.monitoring.yml
K6 ?= k6
PROMTOOL_IMAGE ?= prom/prometheus:v2.54.1

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
	@echo "  make format            # Auto-format backend code and tests"
	@echo "  make final-check       # Non-mutating final validation before PR"
	@echo "  make ci-local          # Run the fast local equivalent of Phase 11 CI gates"
	@echo "  make local-bg          # Run Docker Compose stack in background"
	@echo "  make deploy-status     # Show Phase 12 Blue-Green deployment status"
	@echo "  make deploy-blue-green # Run Phase 12 Green verification and traffic switch"
	@echo "  make ops1-up           # Run Ops Phase 1 monitoring stack with exporters"
	@echo "  make ops1-check        # Verify Prometheus targets, metrics, and dashboards"
	@echo "  make ops2-demo         # Run Ops Phase 2 Blue-Green switch and rollback demo"
	@echo "  make ops4-demo         # Run Ops Phase 4 PostgreSQL backup/restore DR drill"
	@echo "  make ops5-demo         # Run Ops Phase 5 failure recovery runbook drill"
	@echo "  make ops6-demo         # Run Ops Phase 6 alerting/runbook verification"
	@echo "  make ops7-demo         # Run Ops Phase 7 incident timeline/postmortem drill"
	@echo "  make ph1-db-down-drill # Run PH1 PostgreSQL-down write-suspend drill"
	@echo "  make ph2-incident-artifact # Create PH2 sanitized incident artifact"
	@echo "  make ph3-incident-analyze # Analyze latest PH2 incident artifact"
	@echo "  make ph4-recovery-case-from-latest # Create PH4 recovery case from latest PH3 analysis"
	@echo "  make ph5-reconciliation-run # Run PH5 stale detector and reconciliation"
	@echo "  make ph6-ai-context-demo # Generate and validate PH6 AI-safe context"
	@echo "  make k6-smoke          # Run Phase 9 k6 smoke test"
	@echo "  make phase9-check      # Run quick Phase 9 consistency gate"
	@echo "  make security-log-check # Scan logger calls for sensitive raw fields"

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
	@echo "  Nginx int.:  http://localhost:8081"
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

.PHONY: fix
fix: format ## Auto-format backend code and tests

.PHONY: final-check
final-check: format-check lint compile test security-log-check ## Non-mutating final validation before PR

.PHONY: ci-local
ci-local: format-check lint test-unit security-log-check compile ## Run fast local Phase 11 CI gate equivalent
	@echo "Local CI gates passed."
	@echo "Consistency, migration, and Docker build gates run in GitHub Actions with service containers."

.PHONY: ci-local-full
ci-local-full: format-check lint test security-log-check compile ## Run local full pytest gate without migration/Docker build
	@echo "Local full pytest gates passed."
	@echo "Migration and Docker build gates run in GitHub Actions with PostgreSQL service containers."

.PHONY: migration-smoke
migration-smoke: ## Verify migrated PostgreSQL consistency constraints
	PYTHONPATH=$(BACKEND_DIR) $(PYTHON) scripts/check_migration_constraints.py

.PHONY: scripts-check
scripts-check: ## Check shell script syntax
	bash -n scripts/deployment-lib.sh
	bash -n scripts/check_active_upstream.sh
	bash -n scripts/deploy-blue-green.sh
	bash -n scripts/deploy_green.sh
	bash -n scripts/rollback.sh
	bash -n scripts/rollback_to_blue.sh
	bash -n scripts/switch_traffic.sh
	bash -n scripts/deployment-status.sh
	bash -n scripts/deployment-smoke.sh
	bash -n scripts/check_nginx_access_control.sh
	bash -n scripts/postgres_backup.sh
	bash -n scripts/postgres_restore_drill.sh
	bash -n scripts/postgres_dr_drill.sh
	bash -n scripts/ops5_failure_recovery_drill.sh
	bash -n scripts/ops6_alert_rule_validation.sh
	bash -n scripts/ops7_incident_timeline_drill.sh
	bash -n scripts/ph1_db_down_drill.sh
	PYTHONPYCACHEPREFIX=/tmp/financial-event-pycache python3 -m py_compile scripts/ph2_incident_artifact.py
	PYTHONPYCACHEPREFIX=/tmp/financial-event-pycache python3 -m py_compile scripts/ph3_incident_analyzer.py
	PYTHONPYCACHEPREFIX=/tmp/financial-event-pycache python3 -m py_compile scripts/ph4_recovery_case.py
	PYTHONPYCACHEPREFIX=/tmp/financial-event-pycache python3 -m py_compile scripts/ph5_reconciliation.py
	PYTHONPYCACHEPREFIX=/tmp/financial-event-pycache python3 -m py_compile scripts/ph6_ai_context.py
	bash -n scripts/monitoring/check-prometheus-targets.sh
	bash -n scripts/monitoring/check-required-metrics.sh
	bash -n scripts/monitoring/check-grafana-dashboards.sh
	bash -n scripts/monitoring/write-compose-status-report.sh
	test -x scripts/check_active_upstream.sh
	test -x scripts/deploy-blue-green.sh
	test -x scripts/deploy_green.sh
	test -x scripts/rollback.sh
	test -x scripts/rollback_to_blue.sh
	test -x scripts/switch_traffic.sh
	test -x scripts/deployment-status.sh
	test -x scripts/deployment-smoke.sh
	test -x scripts/check_nginx_access_control.sh
	test -x scripts/postgres_backup.sh
	test -x scripts/postgres_restore_drill.sh
	test -x scripts/postgres_dr_drill.sh
	test -x scripts/ops5_failure_recovery_drill.sh
	test -x scripts/ops6_alert_rule_validation.sh
	test -x scripts/ops7_incident_timeline_drill.sh
	test -x scripts/ph1_db_down_drill.sh
	test -x scripts/ph2_incident_artifact.py
	test -x scripts/ph3_incident_analyzer.py
	test -x scripts/ph4_recovery_case.py
	test -x scripts/ph5_reconciliation.py
	test -x scripts/ph6_ai_context.py
	test -x scripts/write_suspend_state.py

.PHONY: security-log-check
security-log-check: ## Scan backend app logs for direct sensitive-field logging
	@echo "Scanning structured logs for sensitive raw fields..."
	@if rg -n "logger\\.(info|warning|error|exception)\\([^\\n]*(account_no|raw_body|signature|secret|idempotency_key|password|token)" backend/app; then \
		echo "Sensitive raw field logging pattern found. Use masked fields/log_event helpers instead."; \
		exit 1; \
	fi
	@if rg -n -U "log_event\\([^)]*(idempotency_key=|account_no=|signature=|secret=|raw_body=|password=|token=)" backend/app; then \
		echo "Sensitive raw structured log field pattern found. Use masked fields instead."; \
		exit 1; \
	fi
	@echo "No raw sensitive structured log fields found."

# Ops Phase 1 Infra Metrics Extension
.PHONY: ops1-up
ops1-up: docker-check ## Start app stack with Ops Phase 1 monitoring exporters
	$(DOCKER_COMPOSE_MONITORING) up --build -d
	@echo ""
	@echo "Ops Phase 1 service URLs:"
	@echo "  API blue:       http://localhost:8000"
	@echo "  Nginx:          http://localhost:8080"
	@echo "  Prometheus:     http://localhost:9090"
	@echo "  Grafana:        http://localhost:3000"
	@echo "  node-exporter:  http://127.0.0.1:9100/metrics"
	@echo "  cAdvisor:       http://127.0.0.1:8082/metrics"
	@echo "  postgres exp.:  internal Docker network only"
	@echo "  redis exp.:     internal Docker network only"
	@echo ""
	@echo "Verify: make ops1-check"

.PHONY: ops1-down
ops1-down: docker-check ## Stop app and Ops Phase 1 monitoring stack
	$(DOCKER_COMPOSE_MONITORING) down

.PHONY: ops1-logs
ops1-logs: docker-check ## Follow Ops Phase 1 monitoring service logs
	$(DOCKER_COMPOSE_MONITORING) logs -f prometheus grafana node-exporter cadvisor postgres-exporter redis-exporter

.PHONY: metrics-check
metrics-check: ## Verify Prometheus required targets and write evidence report
	./scripts/monitoring/check-prometheus-targets.sh

.PHONY: required-metrics-check
required-metrics-check: ## Verify required metrics are queryable and write evidence report
	./scripts/monitoring/check-required-metrics.sh

.PHONY: grafana-check
grafana-check: ## Verify Grafana provisioning files and dashboard JSON
	./scripts/monitoring/check-grafana-dashboards.sh

.PHONY: prometheus-config-check
prometheus-config-check: docker-check ## Verify Prometheus config and alert rule syntax with promtool
	$(DOCKER) run --rm --entrypoint promtool \
		-v "$(PWD)/infra/monitoring/prometheus/prometheus.yml:/etc/prometheus/prometheus.yml:ro" \
		-v "$(PWD)/infra/prometheus/rules/financial_event_alerts.yml:/etc/prometheus/alert-rules.yml:ro" \
		$(PROMTOOL_IMAGE) check config /etc/prometheus/prometheus.yml

.PHONY: ops1-compose-status
ops1-compose-status: docker-check ## Write Docker Compose status evidence report
	DOCKER_COMPOSE_MONITORING='$(DOCKER_COMPOSE_MONITORING)' ./scripts/monitoring/write-compose-status-report.sh

.PHONY: ops1-check
ops1-check: prometheus-config-check metrics-check required-metrics-check grafana-check ops1-compose-status ## Run Ops Phase 1 monitoring verification
	@echo "Ops Phase 1 monitoring checks passed."

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
k6-redis-down: ## Run Redis-down experiment; consistency should pass, availability may fail and is Phase 10 follow-up
	@echo "Expected procedure: docker compose pause redis && make k6-redis-down && docker compose unpause redis"
	@BASE_URL=$(BASE_URL) CLIENT_ID=$(CLIENT_ID) CLIENT_SECRET=$(CLIENT_SECRET) ACCOUNT_NO=$(ACCOUNT_NO) $(K6) run tests/k6/redis-down-test.js

.PHONY: k6-redis-down-duplicate-storm
k6-redis-down-duplicate-storm: ## Run Phase 10 Redis-down duplicate storm scenario
	@BASE_URL=$(BASE_URL) CLIENT_ID=$(CLIENT_ID) CLIENT_SECRET=$(CLIENT_SECRET) ACCOUNT_NO=$(ACCOUNT_NO) $(K6) run tests/k6/redis_down_duplicate_storm.js

.PHONY: k6-redis-down-check
k6-redis-down-check: ## Pause Redis for failure experiment; 5xx availability issues are recorded, not hidden
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
phase9-check: k6-smoke k6-duplicate k6-verify ## Run quick Phase 9 gate: smoke, duplicate storm, PostgreSQL consistency

.PHONY: phase9-full
phase9-full: phase9-check phase9-measure ## Run Phase 9 gate and normal/peak measurement, excluding Redis-down failure experiment

.PHONY: phase9-measure
phase9-measure: k6-normal k6-peak ## Run Phase 9 normal/peak measurement scenarios

.PHONY: phase9-failure-experiment
phase9-failure-experiment: k6-redis-down-check k6-verify ## Run Redis-down experiment; consistency gate should pass, availability may be below target

# Phase 10 failure reproduction helpers
.PHONY: failure-redis-down
failure-redis-down: docker-check ## Stop Redis container and show Compose status
	$(DOCKER_COMPOSE) stop redis
	$(DOCKER_COMPOSE) ps
	@echo "Redis is stopped. Run: make k6-redis-down-duplicate-storm"

.PHONY: failure-redis-up
failure-redis-up: docker-check ## Start Redis container and print readiness checks
	$(DOCKER_COMPOSE) start redis
	$(DOCKER_COMPOSE) ps redis
	@echo "Readiness check: curl -i $(BASE_URL)/ready"
	@echo "Redis ping: docker compose exec redis redis-cli ping"

.PHONY: failure-redis-logs
failure-redis-logs: ## Follow Redis container logs
	$(DOCKER_COMPOSE) logs -f redis

.PHONY: failure-api-restart
failure-api-restart: docker-check ## Restart API container and print health checks
	$(DOCKER_COMPOSE) restart api-blue
	$(DOCKER_COMPOSE) ps api-blue
	@echo "Health check: curl -i $(BASE_URL)/health"
	@echo "Readiness check: curl -i $(BASE_URL)/ready"

.PHONY: failure-db-down
failure-db-down: docker-check ## Stop PostgreSQL container without deleting data
	$(DOCKER_COMPOSE) stop postgres
	$(DOCKER_COMPOSE) ps
	@echo "DB is stopped. Readiness should fail: curl -i $(BASE_URL)/ready"

.PHONY: failure-db-up
failure-db-up: docker-check ## Start PostgreSQL container and print readiness checks
	$(DOCKER_COMPOSE) start postgres
	$(DOCKER_COMPOSE) ps postgres
	@echo "Readiness check: curl -i $(BASE_URL)/ready"

.PHONY: failure-status
failure-status: ## Show Docker Compose service status
	$(DOCKER_COMPOSE) ps

.PHONY: phase10-redis-down-check
phase10-redis-down-check: docker-check ## Run Phase 10 Redis-down duplicate storm consistency gate
	@set -e; \
	$(DOCKER_COMPOSE) stop redis; \
	$(DOCKER_COMPOSE) ps; \
	trap '$(DOCKER_COMPOSE) start redis >/dev/null; $(DOCKER_COMPOSE) ps redis; echo "Readiness check: curl -i $(BASE_URL)/ready"' EXIT; \
	$(MAKE) k6-redis-down-duplicate-storm; \
	$(MAKE) k6-verify

# Production Hardening Phase 1 Write Suspend / PostgreSQL Down
.PHONY: ph1-write-suspend-status
ph1-write-suspend-status: ## Show current PH1 write-suspend state
	@WRITE_SUSPEND_STATE_FILE=$${WRITE_SUSPEND_STATE_FILE:-reports/runtime/write-suspend-state.json} \
		python3 scripts/write_suspend_state.py status

.PHONY: ph1-write-suspend-resume
ph1-write-suspend-resume: ## Operator resume for PH1 write suspension
	@WRITE_SUSPEND_STATE_FILE=$${WRITE_SUSPEND_STATE_FILE:-reports/runtime/write-suspend-state.json} \
		python3 scripts/write_suspend_state.py disable --reason operator_resume

.PHONY: ph1-db-down-drill
ph1-db-down-drill: docker-check ## Run PH1 PostgreSQL-down write-suspend drill
	@BASE_URL=$(BASE_URL) READY_BASE_URL=$(INTERNAL_BASE_URL) CLIENT_ID=$(CLIENT_ID) CLIENT_SECRET=$(CLIENT_SECRET) ACCOUNT_NO=$(ACCOUNT_NO) ./scripts/ph1_db_down_drill.sh

.PHONY: ops9-db-down-drill
ops9-db-down-drill: ph1-db-down-drill ## Alias for PH1 PostgreSQL-down write-suspend drill

# Production Hardening Phase 2 Incident Artifact / Sanitized Report
.PHONY: ph2-incident-artifact
ph2-incident-artifact: ## Create PH2 out-of-band incident artifact bundle
	@python3 scripts/ph2_incident_artifact.py create --scenario POSTGRES_DOWN --source manual

.PHONY: ph2-incident-artifact-validate
ph2-incident-artifact-validate: ## Validate the latest PH2 incident artifact bundle
	@python3 scripts/ph2_incident_artifact.py validate --latest

.PHONY: ph2-db-down-incident-artifact
ph2-db-down-incident-artifact: docker-check ## Run PH1 drill, then create and validate PH2 incident artifact
	@set -e; \
	RUN_ID=$${RUN_ID:-ph2-db-down-$$(date -u +%Y%m%dT%H%M%SZ)}; \
	REPORT_DIR=$${REPORT_DIR:-reports/production-hardening/ph1-write-suspend/$$RUN_ID}; \
	RUN_ID=$$RUN_ID REPORT_DIR=$$REPORT_DIR BASE_URL=$(BASE_URL) READY_BASE_URL=$(INTERNAL_BASE_URL) CLIENT_ID=$(CLIENT_ID) CLIENT_SECRET=$(CLIENT_SECRET) ACCOUNT_NO=$(ACCOUNT_NO) ./scripts/ph1_db_down_drill.sh; \
	python3 scripts/ph2_incident_artifact.py create --scenario POSTGRES_DOWN --run-id $$RUN_ID --source ph1_drill --ph1-report-dir $$REPORT_DIR; \
	python3 scripts/ph2_incident_artifact.py validate --latest

.PHONY: ops10-incident-artifact
ops10-incident-artifact: ph2-incident-artifact ## Alias for PH2 out-of-band incident artifact bundle

# Production Hardening Phase 3 Incident Analyzer MVP
.PHONY: ph3-incident-analyze
ph3-incident-analyze: ## Analyze the latest PH2 incident artifact
	@python3 scripts/ph3_incident_analyzer.py analyze --latest

.PHONY: ph3-incident-analyze-validate
ph3-incident-analyze-validate: ## Validate latest PH3 incident analyzer output
	@python3 scripts/ph3_incident_analyzer.py validate --latest

.PHONY: ph3-db-down-incident-analysis
ph3-db-down-incident-analysis: docker-check ## Run PH2 DB-down artifact flow, then analyze and validate it
	@$(MAKE) ph2-db-down-incident-artifact
	@python3 scripts/ph3_incident_analyzer.py analyze --latest
	@python3 scripts/ph3_incident_analyzer.py validate --latest

.PHONY: ops11-incident-analyze
ops11-incident-analyze: ph3-incident-analyze ## Alias for PH3 rule-based incident analyzer MVP

# Production Hardening Phase 4 Recovery Case / Quarantine
.PHONY: ph4-recovery-case-from-latest
ph4-recovery-case-from-latest: ## Create a PH4 recovery case from the latest PH3 analysis
	@python3 scripts/ph4_recovery_case.py create-from-analysis --latest

.PHONY: ph4-recovery-cases
ph4-recovery-cases: ## List PH4 recovery cases
	@python3 scripts/ph4_recovery_case.py list-cases

.PHONY: ph4-quarantines
ph4-quarantines: ## List PH4 quarantine records
	@python3 scripts/ph4_recovery_case.py list-quarantines

.PHONY: ops12-recovery-case
ops12-recovery-case: ph4-recovery-case-from-latest ## Alias for PH4 recovery case creation

# Production Hardening Phase 5 Stale Processing / Reconciliation
.PHONY: ph5-detect-stale-processing
ph5-detect-stale-processing: ## Detect stale PROCESSING idempotency records
	@python3 scripts/ph5_reconciliation.py detect-stale --threshold-minutes 5

.PHONY: ph5-reconcile
ph5-reconcile: ## Run PH5 count-only reconciliation
	@python3 scripts/ph5_reconciliation.py reconcile --threshold-minutes 5

.PHONY: ph5-reconciliation-run
ph5-reconciliation-run: ## Run PH5 stale detector, reconciliation, report, and validate
	@python3 scripts/ph5_reconciliation.py run --threshold-minutes 5

.PHONY: ph5-reconciliation-validate
ph5-reconciliation-validate: ## Validate latest PH5 reconciliation artifact
	@python3 scripts/ph5_reconciliation.py validate --latest

.PHONY: ops13-reconciliation
ops13-reconciliation: ph5-reconciliation-run ## Alias for PH5 reconciliation run

# Production Hardening Phase 6 AI-safe Context
.PHONY: ph6-ai-context-demo
ph6-ai-context-demo: ## Generate and validate PH6 AI-safe context demo artifact
	@python3 scripts/ph6_ai_context.py demo

.PHONY: ph6-ai-context-validate
ph6-ai-context-validate: ## Validate curated PH6 AI-safe context sample
	@python3 scripts/ph6_ai_context.py validate --input reports/ai-context/sample-ai-context.json

.PHONY: ph6-ai-context-sanitize-latest
ph6-ai-context-sanitize-latest: ## Sanitize latest PH2 incident artifact into PH6 AI-safe context
	@python3 scripts/ph6_ai_context.py sanitize-latest --source incidents

.PHONY: ph6-ai-context-sanitize-latest-recovery-case
ph6-ai-context-sanitize-latest-recovery-case: ## Sanitize latest PH4 recovery case evidence into PH6 AI-safe context
	@python3 scripts/ph6_ai_context.py sanitize-latest --source recovery-cases

.PHONY: ph6-ai-context-recovery
ph6-ai-context-recovery: ph6-ai-context-sanitize-latest-recovery-case ## Alias for PH6 recovery case AI-safe context

.PHONY: ops14-ai-context
ops14-ai-context: ph6-ai-context-demo ## Alias for PH6 AI-safe context demo

# Phase 12 Blue-Green deployment and rollback simulation
.PHONY: deploy-status
deploy-status: docker-check ## Show active upstream and Blue/Green service status
	@BASE_URL=$(BASE_URL) INTERNAL_BASE_URL=$(INTERNAL_BASE_URL) ./scripts/deployment-status.sh

.PHONY: deploy-green
deploy-green: docker-check ## Start and verify Green without switching traffic
	@BASE_URL=$(BASE_URL) INTERNAL_BASE_URL=$(INTERNAL_BASE_URL) GREEN_URL=http://localhost:8001 ./scripts/deploy-blue-green.sh start-green
	@BASE_URL=http://localhost:8001 ./scripts/deployment-smoke.sh

.PHONY: deploy-switch-green
deploy-switch-green: docker-check ## Switch Nginx upstream to Green after config validation
	@BASE_URL=$(BASE_URL) INTERNAL_BASE_URL=$(INTERNAL_BASE_URL) GREEN_URL=http://localhost:8001 ./scripts/deploy-blue-green.sh switch-green

.PHONY: deploy-blue-green
deploy-blue-green: docker-check ## Run Green verification, switch Nginx to Green, and post-switch smoke
	@BASE_URL=$(BASE_URL) INTERNAL_BASE_URL=$(INTERNAL_BASE_URL) GREEN_URL=http://localhost:8001 ./scripts/deploy-blue-green.sh deploy

.PHONY: deploy-rollback
deploy-rollback: docker-check ## Roll Nginx upstream back to Blue and verify
	@BASE_URL=$(BASE_URL) INTERNAL_BASE_URL=$(INTERNAL_BASE_URL) ./scripts/rollback.sh "$${ROLLBACK_REASON:-manual rollback}"

.PHONY: deploy-smoke
deploy-smoke: ## Run lightweight deployment smoke test through BASE_URL
	@BASE_URL=$(BASE_URL) READY_BASE_URL=$(INTERNAL_BASE_URL) CLIENT_ID=$(CLIENT_ID) CLIENT_SECRET=$(CLIENT_SECRET) ACCOUNT_NO=$(ACCOUNT_NO) ./scripts/deployment-smoke.sh

.PHONY: deploy-verify
deploy-verify: k6-verify ## Run post-deployment PostgreSQL consistency verification

.PHONY: phase12-check
phase12-check: docker-check ## Run Phase 12 Blue-Green switch, rollback, smoke, and consistency checks
	@$(MAKE) local-bg
	@$(MAKE) deploy-status
	@$(MAKE) deploy-green
	@$(MAKE) deploy-smoke
	@$(MAKE) deploy-switch-green
	@$(MAKE) deploy-smoke
	@$(MAKE) deploy-rollback
	@$(MAKE) deploy-smoke
	@$(MAKE) deploy-verify

.PHONY: phase12-rollback-check
phase12-rollback-check: docker-check ## Verify rollback from Green to Blue without destructive actions
	@$(MAKE) local-bg
	@$(MAKE) deploy-green
	@$(MAKE) deploy-switch-green
	@ROLLBACK_REASON="phase12 rollback check" $(MAKE) deploy-rollback
	@$(MAKE) deploy-smoke

# Ops Phase 2 Blue-Green deployment and rollback simulation
.PHONY: ops2-start-blue
ops2-start-blue: docker-check ## Start Blue, Nginx, PostgreSQL, and Redis for Ops Phase 2
	@cp infra/nginx/conf.d/upstream-active.conf.blue infra/nginx/conf.d/upstream-active.conf
	@printf 'blue\n' > infra/nginx/.active-color
	$(DOCKER_COMPOSE) up -d --build postgres redis api-blue
	$(DOCKER_COMPOSE) up -d --force-recreate nginx
	@echo "Blue/Nginx stack is starting. Verify with: make ops2-check-blue"

.PHONY: ops2-start-green
ops2-start-green: docker-check ops2-ensure-blue-running ops2-deploy-green-only ## Start and verify Green service without switching traffic

.PHONY: ops2-ensure-blue-running
ops2-ensure-blue-running:
	@$(DOCKER_COMPOSE) ps --status running --services | grep -q '^nginx$$' || \
		(echo "Blue/Nginx is not running. Run: make ops2-start-blue"; exit 1)
	@$(DOCKER_COMPOSE) ps --status running --services | grep -q '^api-blue$$' || \
		(echo "api-blue is not running. Run: make ops2-start-blue"; exit 1)

.PHONY: ops2-deploy-green-only
ops2-deploy-green-only:
	@STOP_GREEN_ON_FAILURE=true BASE_URL=$(BASE_URL) INTERNAL_BASE_URL=$(INTERNAL_BASE_URL) GREEN_URL=$(GREEN_URL) ./scripts/deploy_green.sh

.PHONY: ops2-check-blue
ops2-check-blue: ## Check public Nginx /health and internal Nginx /ready
	@set -e; \
	for url in "$(BASE_URL)/health" "$(INTERNAL_BASE_URL)/ready"; do \
		echo "Waiting for $$url"; \
		i=0; \
		until curl -fsS "$$url" >/dev/null 2>&1; do \
			i=$$((i + 1)); \
			if [ "$$i" -ge 30 ]; then \
				echo "$$url did not become ready"; \
				exit 1; \
			fi; \
			sleep 2; \
		done; \
	done
	@echo "Nginx public health and internal readiness checks passed."

.PHONY: ops2-check-green
ops2-check-green: ## Check Green direct /health and /ready
	@set -e; \
	for endpoint in health ready; do \
		echo "Waiting for $(GREEN_URL)/$$endpoint"; \
		i=0; \
		until curl -fsS "$(GREEN_URL)/$$endpoint" >/dev/null; do \
			i=$$((i + 1)); \
			if [ "$$i" -ge 30 ]; then \
				echo "$(GREEN_URL)/$$endpoint did not become ready"; \
				exit 1; \
			fi; \
			sleep 2; \
		done; \
	done
	@echo "Green health/ready checks passed: $(GREEN_URL)"

.PHONY: ops2-check-routed-blue
ops2-check-routed-blue: docker-check ops2-check-blue ## Verify Nginx is configured and routed to Blue
	@./scripts/check_active_upstream.sh blue

.PHONY: ops2-check-routed-green
ops2-check-routed-green: docker-check ops2-check-blue ## Verify Nginx is configured and routed to Green
	@./scripts/check_active_upstream.sh green

.PHONY: ops2-switch-green
ops2-switch-green: docker-check ## Switch Nginx upstream to Green after config validation
	@./scripts/switch_traffic.sh green

.PHONY: ops2-switch-blue
ops2-switch-blue: docker-check ## Switch Nginx upstream to Blue after config validation
	@./scripts/switch_traffic.sh blue

.PHONY: ops2-rollback
ops2-rollback: docker-check ## Roll Nginx upstream back to Blue and verify health/readiness
	@BASE_URL=$(BASE_URL) INTERNAL_BASE_URL=$(INTERNAL_BASE_URL) ./scripts/rollback_to_blue.sh

.PHONY: ops2-smoke-green
ops2-smoke-green: ## Run lightweight smoke test directly against Green
	@BASE_URL=$(GREEN_URL) CLIENT_ID=$(CLIENT_ID) CLIENT_SECRET=$(CLIENT_SECRET) ACCOUNT_NO=$(ACCOUNT_NO) ./scripts/deployment-smoke.sh

.PHONY: ops2-smoke-routed
ops2-smoke-routed: ## Run lightweight smoke test through Nginx BASE_URL
	@BASE_URL=$(BASE_URL) READY_BASE_URL=$(INTERNAL_BASE_URL) CLIENT_ID=$(CLIENT_ID) CLIENT_SECRET=$(CLIENT_SECRET) ACCOUNT_NO=$(ACCOUNT_NO) ./scripts/deployment-smoke.sh

.PHONY: ops2-status
ops2-status: docker-check ## Show Blue/Green/Nginx Docker Compose status
	$(DOCKER_COMPOSE) --profile green-deployment ps nginx api-blue api-green postgres redis
	@BASE_URL=$(BASE_URL) INTERNAL_BASE_URL=$(INTERNAL_BASE_URL) ./scripts/deployment-status.sh

.PHONY: ops2-logs
ops2-logs: docker-check ## Follow Ops Phase 2 Nginx and API logs
	$(DOCKER_COMPOSE) --profile green-deployment logs -f nginx api-blue api-green

.PHONY: ops2-cleanup
ops2-cleanup: docker-check ## Roll back to Blue and stop Green without deleting volumes
	@if $(DOCKER_COMPOSE) ps --status running --services | grep -q '^nginx$$'; then \
		BASE_URL=$(BASE_URL) INTERNAL_BASE_URL=$(INTERNAL_BASE_URL) ./scripts/rollback_to_blue.sh --stop-green; \
	else \
		echo "Nginx is not running; resetting active upstream files to Blue and stopping Green if present."; \
		cp infra/nginx/conf.d/upstream-active.conf.blue infra/nginx/conf.d/upstream-active.conf; \
		printf 'blue\n' > infra/nginx/.active-color; \
		$(DOCKER_COMPOSE) --profile green-deployment stop api-green || true; \
	fi

.PHONY: ops2-demo
ops2-demo: docker-check ## Run Blue start, Green verification, switch, rollback, and checks
	@$(MAKE) ops2-start-blue
	@$(MAKE) ops2-check-routed-blue
	@$(MAKE) ops2-deploy-green-only
	@$(MAKE) ops2-check-green
	@$(MAKE) ops2-smoke-green
	@$(MAKE) ops2-switch-green
	@$(MAKE) ops2-check-routed-green
	@$(MAKE) ops2-smoke-routed
	@$(MAKE) ops2-rollback
	@$(MAKE) ops2-check-routed-blue

.PHONY: ops2-verify
ops2-verify: deploy-verify ## Run PostgreSQL consistency verification after Ops Phase 2 traffic switch

.PHONY: ops2-demo-full
ops2-demo-full: ops2-demo ops2-verify ## Run Ops Phase 2 demo and PostgreSQL consistency verification

# Ops Phase 3 Nginx Access Control
.PHONY: ops3-up
ops3-up: docker-check ## Start Blue/Nginx/PostgreSQL/Redis stack for Ops Phase 3
	@cp infra/nginx/conf.d/upstream-active.conf.blue infra/nginx/conf.d/upstream-active.conf
	@printf 'blue\n' > infra/nginx/.active-color
	$(DOCKER_COMPOSE) up -d --build postgres redis api-blue prometheus
	$(DOCKER_COMPOSE) up -d --force-recreate nginx
	@echo "Public Nginx:   $(BASE_URL)"
	@echo "Internal Nginx: $(INTERNAL_BASE_URL)"

.PHONY: ops3-nginx-test
ops3-nginx-test: docker-check ## Validate Nginx config inside the running container
	$(DOCKER_COMPOSE) exec -T nginx nginx -t

.PHONY: ops3-check-public
ops3-check-public: ## Verify public 8080 allowlist and sensitive endpoint blocking
	@set -e; \
	health=$$(curl -sS -o /dev/null -w '%{http_code}' "$(BASE_URL)/health"); \
	ready=$$(curl -sS -o /dev/null -w '%{http_code}' "$(BASE_URL)/ready"); \
	metrics=$$(curl -sS -o /dev/null -w '%{http_code}' "$(BASE_URL)/metrics"); \
	docs=$$(curl -sS -o /dev/null -w '%{http_code}' "$(BASE_URL)/docs"); \
	redoc=$$(curl -sS -o /dev/null -w '%{http_code}' "$(BASE_URL)/redoc"); \
	openapi=$$(curl -sS -o /dev/null -w '%{http_code}' "$(BASE_URL)/openapi.json"); \
	unknown=$$(curl -sS -o /dev/null -w '%{http_code}' "$(BASE_URL)/unknown"); \
	account_api=$$(curl -sS -o /dev/null -w '%{http_code}' "$(BASE_URL)/api/v1/accounts/ACC-001/balance"); \
	transaction_get=$$(curl -sS -o /dev/null -w '%{http_code}' "$(BASE_URL)/api/v1/transaction-events"); \
	echo "public /health=$$health /ready=$$ready /metrics=$$metrics /docs=$$docs /redoc=$$redoc /openapi.json=$$openapi /unknown=$$unknown account-api=$$account_api GET-transaction=$$transaction_get"; \
	test "$$health" = "200"; \
	case "$$ready" in 403|404) ;; *) exit 1 ;; esac; \
	case "$$metrics" in 403|404) ;; *) exit 1 ;; esac; \
	case "$$docs" in 403|404) ;; *) exit 1 ;; esac; \
	case "$$redoc" in 403|404) ;; *) exit 1 ;; esac; \
	case "$$openapi" in 403|404) ;; *) exit 1 ;; esac; \
	test "$$unknown" = "404"; \
	case "$$account_api" in 403|404) ;; *) exit 1 ;; esac; \
	case "$$transaction_get" in 403|404|405) ;; *) exit 1 ;; esac

.PHONY: ops3-check-internal
ops3-check-internal: ## Verify internal 8081 allows /health, /ready, and /metrics
	@set -e; \
	for endpoint in health ready metrics; do \
		status=$$(curl -sS -o /dev/null -w '%{http_code}' "$(INTERNAL_BASE_URL)/$$endpoint"); \
		echo "internal /$$endpoint=$$status"; \
		test "$$status" = "200"; \
	done

.PHONY: ops3-check-access
ops3-check-access: ## Run full Nginx public/internal access control verification
	@PUBLIC_BASE_URL=$(BASE_URL) INTERNAL_BASE_URL=$(INTERNAL_BASE_URL) ./scripts/check_nginx_access_control.sh

.PHONY: ops3-smoke-public
ops3-smoke-public: ## Run transaction smoke through public 8080 while readiness uses internal 8081
	@BASE_URL=$(BASE_URL) READY_BASE_URL=$(INTERNAL_BASE_URL) CLIENT_ID=$(CLIENT_ID) CLIENT_SECRET=$(CLIENT_SECRET) ACCOUNT_NO=$(ACCOUNT_NO) ./scripts/deployment-smoke.sh

.PHONY: ops3-status
ops3-status: docker-check ## Show Ops Phase 3 Docker Compose service status
	$(DOCKER_COMPOSE) ps

.PHONY: ops3-logs
ops3-logs: docker-check ## Follow Ops Phase 3 Nginx logs
	$(DOCKER_COMPOSE) logs -f nginx

.PHONY: ops3-demo
ops3-demo: docker-check ## Run Ops Phase 3 stack, Nginx config test, access check, and public smoke
	@$(MAKE) ops3-up
	@$(MAKE) ops3-nginx-test
	@$(MAKE) ops3-check-access
	@$(MAKE) ops3-smoke-public

# Ops Phase 4 PostgreSQL Backup / Restore DR Drill
.PHONY: ops4-up
ops4-up: docker-check ## Start PostgreSQL, Redis, Blue API, Nginx, and restore PostgreSQL for Ops Phase 4
	@cp infra/nginx/conf.d/upstream-active.conf.blue infra/nginx/conf.d/upstream-active.conf
	@printf 'blue\n' > infra/nginx/.active-color
	$(DOCKER_COMPOSE) up -d --build postgres redis api-blue postgres-restore
	$(DOCKER_COMPOSE) up -d --force-recreate nginx
	@echo "Ops Phase 4 stack is running."
	@echo "Source DB:  postgres/financial_events"
	@echo "Restore DB: postgres-restore/financial_events_restore"

.PHONY: ops4-backup
ops4-backup: docker-check ## Create a PostgreSQL custom-format dump and SHA256 checksum
	@./scripts/postgres_backup.sh

.PHONY: ops4-restore
ops4-restore: docker-check ## Restore DUMP_FILE or latest dump into postgres-restore and write DR report
	@set -e; \
	dump_file="$(DUMP_FILE)"; \
	if [ -z "$$dump_file" ]; then \
		dump_file=$$(ls -t backups/postgres/*.dump 2>/dev/null | head -n 1 || true); \
	fi; \
	if [ -z "$$dump_file" ]; then \
		echo "No dump file found. Run make ops4-backup or pass DUMP_FILE=backups/postgres/xxx.dump"; \
		exit 1; \
	fi; \
	./scripts/postgres_restore_drill.sh "$$dump_file"

.PHONY: ops4-check
ops4-check: docker-check ## Run restore DB consistency SQL against postgres-restore
	@$(DOCKER_COMPOSE) exec -T postgres-restore psql -U appuser -d financial_events_restore -v ON_ERROR_STOP=1 -f - < scripts/sql/dr_consistency_check.sql

.PHONY: ops4-check-app
ops4-check-app: docker-check ## Wait for Ops Phase 4 public health and internal readiness
	@set -e; \
	for url in "$(BASE_URL)/health" "$(INTERNAL_BASE_URL)/ready"; do \
		echo "Waiting for $$url"; \
		i=0; \
		until curl -fsS "$$url" >/dev/null 2>&1; do \
			i=$$((i + 1)); \
			if [ "$$i" -ge 30 ]; then \
				echo "$$url did not become ready"; \
				exit 1; \
			fi; \
			sleep 2; \
		done; \
	done
	@$(MAKE) ops3-check-public
	@echo "Ops Phase 4 app readiness checks passed."

.PHONY: ops4-drill
ops4-drill: docker-check ## Run backup, checksum verification, restore, consistency SQL, and report generation
	@./scripts/postgres_dr_drill.sh

.PHONY: ops4-status
ops4-status: docker-check ## Show Ops Phase 4 Docker Compose service status
	$(DOCKER_COMPOSE) ps postgres redis api-blue nginx postgres-restore

.PHONY: ops4-logs
ops4-logs: docker-check ## Follow PostgreSQL source and restore logs
	$(DOCKER_COMPOSE) logs -f postgres postgres-restore

.PHONY: ops4-cleanup
ops4-cleanup: docker-check ## Stop restore DB only; never delete source PostgreSQL data or volumes
	$(DOCKER_COMPOSE) stop postgres-restore
	$(DOCKER_COMPOSE) rm -f postgres-restore
	@echo "Stopped postgres-restore only. Source postgres volume was not touched."

.PHONY: ops4-demo
ops4-demo: docker-check ## Run Ops Phase 4 stack, public smoke, full DR drill, and print report
	@$(MAKE) ops4-up
	@$(MAKE) ops4-check-app
	@$(MAKE) ops3-smoke-public
	@$(MAKE) ops4-drill
	@cat reports/dr/ops4-postgres-restore-drill.md

# Ops Phase 5 Failure Recovery Runbook Drill
.PHONY: ops5-up
ops5-up: docker-check ## Start PostgreSQL, Redis, Blue API, and Nginx for Ops Phase 5
	@cp infra/nginx/conf.d/upstream-active.conf.blue infra/nginx/conf.d/upstream-active.conf
	@printf 'blue\n' > infra/nginx/.active-color
	$(DOCKER_COMPOSE) up -d --build postgres redis api-blue
	$(DOCKER_COMPOSE) up -d --force-recreate nginx
	@echo "Ops Phase 5 stack is running."
	@echo "Public Nginx:   $(BASE_URL)"
	@echo "Internal ready: $(INTERNAL_BASE_URL)"

.PHONY: ops5-check
ops5-check: docker-check ## Run Ops Phase 5 preflight health/readiness/dependency checks
	@SCENARIO=check BASE_URL=$(BASE_URL) READY_BASE_URL=$(INTERNAL_BASE_URL) ./scripts/ops5_failure_recovery_drill.sh

.PHONY: ops5-redis-drill
ops5-redis-drill: docker-check ## Run Redis failure recovery drill only
	@SCENARIO=redis BASE_URL=$(BASE_URL) READY_BASE_URL=$(INTERNAL_BASE_URL) CLIENT_ID=$(CLIENT_ID) CLIENT_SECRET=$(CLIENT_SECRET) ACCOUNT_NO=$(ACCOUNT_NO) ./scripts/ops5_failure_recovery_drill.sh

.PHONY: ops5-api-drill
ops5-api-drill: docker-check ## Run API failure recovery drill only
	@SCENARIO=api BASE_URL=$(BASE_URL) READY_BASE_URL=$(INTERNAL_BASE_URL) CLIENT_ID=$(CLIENT_ID) CLIENT_SECRET=$(CLIENT_SECRET) ACCOUNT_NO=$(ACCOUNT_NO) ./scripts/ops5_failure_recovery_drill.sh

.PHONY: ops5-db-drill
ops5-db-drill: docker-check ## Run PostgreSQL failure detection/recovery drill only
	@SCENARIO=db BASE_URL=$(BASE_URL) READY_BASE_URL=$(INTERNAL_BASE_URL) CLIENT_ID=$(CLIENT_ID) CLIENT_SECRET=$(CLIENT_SECRET) ACCOUNT_NO=$(ACCOUNT_NO) ./scripts/ops5_failure_recovery_drill.sh

.PHONY: ops5-drill
ops5-drill: docker-check ## Run full Ops Phase 5 failure recovery runbook drill
	@SCENARIO=all BASE_URL=$(BASE_URL) READY_BASE_URL=$(INTERNAL_BASE_URL) CLIENT_ID=$(CLIENT_ID) CLIENT_SECRET=$(CLIENT_SECRET) ACCOUNT_NO=$(ACCOUNT_NO) ./scripts/ops5_failure_recovery_drill.sh

.PHONY: ops5-demo
ops5-demo: docker-check ## Start stack, precheck, run full Ops Phase 5 drill, and print report
	@$(MAKE) ops5-up
	@$(MAKE) ops5-check
	@$(MAKE) ops5-drill
	@cat reports/ops/ops5-failure-recovery-drill.md

# Ops Phase 6 Alerting & Incident Response Runbook
.PHONY: ops6-up
ops6-up: docker-check ## Start app and monitoring stack for Ops Phase 6 alert validation
	$(DOCKER_COMPOSE_MONITORING) up --build -d
	@echo "Ops Phase 6 monitoring stack is running."
	@echo "Prometheus: http://localhost:9090"
	@echo "Grafana:    http://localhost:3000"

.PHONY: ops6-check
ops6-check: docker-check ## Check Ops Phase 6 API, Prometheus, and Grafana readiness
	@set -e; \
	for url in "$(BASE_URL)/health" "$(INTERNAL_BASE_URL)/ready" "http://localhost:9090/-/ready" "http://localhost:3000/api/health"; do \
		echo "Waiting for $$url"; \
		i=0; \
		until curl -fsS "$$url" >/dev/null 2>&1; do \
			i=$$((i + 1)); \
			if [ "$$i" -ge 30 ]; then \
				echo "$$url did not become ready"; \
				exit 1; \
			fi; \
			sleep 2; \
		done; \
	done
	@echo "Ops Phase 6 readiness checks passed."

.PHONY: ops6-alert-rules
ops6-alert-rules: docker-check ## Validate Ops Phase 6 Prometheus alert rule syntax
	@PROMTOOL_IMAGE=$(PROMTOOL_IMAGE) PROMETHEUS_API_CHECK=false ./scripts/ops6_alert_rule_validation.sh

.PHONY: ops6-drill
ops6-drill: docker-check ## Validate alert rules and Prometheus rule loading, then write Ops6 report
	@PROMTOOL_IMAGE=$(PROMTOOL_IMAGE) PROMETHEUS_API_CHECK=true ./scripts/ops6_alert_rule_validation.sh

.PHONY: ops6-demo
ops6-demo: docker-check ## Start stack, validate alert rules, check rule loading, and print report
	@$(MAKE) ops6-up
	@$(MAKE) ops6-check
	@$(MAKE) ops6-drill
	@cat reports/ops/ops6-alerting-incident-runbook.md

# Ops Phase 7 Incident Timeline & Postmortem Drill
.PHONY: ops7-up
ops7-up: docker-check ## Start app stack for Ops Phase 7 incident drill
	@cp infra/nginx/conf.d/upstream-active.conf.blue infra/nginx/conf.d/upstream-active.conf
	@printf 'blue\n' > infra/nginx/.active-color
	$(DOCKER_COMPOSE) up -d --build postgres redis api-blue
	$(DOCKER_COMPOSE) up -d --force-recreate nginx
	@echo "Ops Phase 7 stack is running."
	@echo "Public Nginx:   $(BASE_URL)"
	@echo "Internal ready: $(INTERNAL_BASE_URL)"

.PHONY: ops7-check
ops7-check: docker-check ## Run Ops Phase 7 preflight health/readiness/dependency checks
	@MODE=check BASE_URL=$(BASE_URL) READY_BASE_URL=$(INTERNAL_BASE_URL) ./scripts/ops7_incident_timeline_drill.sh

.PHONY: ops7-drill
ops7-drill: docker-check ## Run Ops Phase 7 incident timeline and postmortem drill
	@BASE_URL=$(BASE_URL) READY_BASE_URL=$(INTERNAL_BASE_URL) CLIENT_ID=$(CLIENT_ID) CLIENT_SECRET=$(CLIENT_SECRET) ACCOUNT_NO=$(ACCOUNT_NO) ./scripts/ops7_incident_timeline_drill.sh

.PHONY: ops7-report
ops7-report: ## Print Ops Phase 7 incident timeline report
	@cat reports/ops/ops7-incident-timeline-postmortem.md

.PHONY: ops7-demo
ops7-demo: docker-check ## Start stack, run incident drill, and print postmortem report
	@$(MAKE) ops7-up
	@$(MAKE) ops7-check
	@$(MAKE) ops7-drill
	@$(MAKE) ops7-report

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
