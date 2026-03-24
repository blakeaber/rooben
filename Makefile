.PHONY: dev dev-api dev-dash up down build logs install api dash test test-all lint fmt db db-reset db-shell clean doctor

# ── Development (Docker) ───────────────────────────────────────────────────────
dev: ## Start API + dashboard + postgres (dev mode)
	docker compose -f docker-compose.yml -f docker-compose.dev.yml up --build

dev-api: ## Start only API + postgres (dev mode)
	docker compose -f docker-compose.yml -f docker-compose.dev.yml up --build api postgres

dev-dash: ## Start only dashboard (assumes API already running)
	docker compose -f docker-compose.yml -f docker-compose.dev.yml up dashboard

# ── Docker (production-like) ───────────────────────────────────────────────────
up: ## Production docker-compose up
	docker compose up --build -d

down: ## Stop all containers
	docker compose down

build: ## Build Docker image
	docker compose build

logs: ## Tail logs
	docker compose logs -f

# ── Local (no Docker) ─────────────────────────────────────────────────────────
install: ## Install Python + Node dependencies locally
	pip install -e ".[dev]"
	cd dashboard && npm install

api: ## Start API locally with hot-reload (requires local postgres)
	uvicorn rooben.dashboard.app:create_app --factory --host 0.0.0.0 --port 8420 --reload

dash: ## Start dashboard locally on port 3000
	cd dashboard && npx next dev --port 3000

# ── Testing ────────────────────────────────────────────────────────────────────
test: ## Run tests (skip e2e)
	pytest -x -q --ignore=tests/validate_live_e2e.py

test-all: ## Run all tests including e2e
	pytest -x -q

lint: ## Check linting
	ruff check src/ tests/
	ruff format --check src/ tests/

fmt: ## Auto-format code
	ruff format src/ tests/

# ── Database ───────────────────────────────────────────────────────────────────
db: ## Start just postgres
	docker compose up -d postgres

db-reset: ## Drop and recreate database
	docker compose down -v postgres
	docker compose up -d postgres

db-shell: ## Open psql shell
	docker compose exec postgres psql -U rooben -d rooben

# ── Utilities ──────────────────────────────────────────────────────────────────
clean: ## Remove build artifacts
	rm -rf build/ dist/ *.egg-info __pycache__ .pytest_cache .ruff_cache
	find src tests -name '__pycache__' -exec rm -rf {} + 2>/dev/null || true
	cd dashboard && rm -rf .next node_modules out

doctor: ## Run rooben doctor
	rooben doctor

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-15s\033[0m %s\n", $$1, $$2}'

.DEFAULT_GOAL := help
