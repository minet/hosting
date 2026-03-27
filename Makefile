# ── hosting.minet.net ─────────────────────────────────────────────
.DEFAULT_GOAL := help

# ── Docker Compose ────────────────────────────────────────────────
up:              ## Start all services (detached)
	docker compose up -d --build

down:            ## Stop all services
	docker compose down

logs:            ## Tail logs (all services)
	docker compose logs -f

logs-back:       ## Tail backend logs only
	docker compose logs -f backend

logs-front:      ## Tail frontend logs only
	docker compose logs -f frontend

restart:         ## Restart all services
	docker compose restart

ps:              ## Show running services
	docker compose ps

# ── Backend ───────────────────────────────────────────────────────
back-shell:      ## Open a shell in the backend container
	docker compose exec backend bash

back-lint:       ## Lint backend with ruff
	cd backend && ruff check .

back-format:     ## Format backend with ruff
	cd backend && ruff format .

# ── Frontend ──────────────────────────────────────────────────────
front-dev:       ## Run frontend dev server locally (no Docker)
	cd frontend && npm run dev

front-build:     ## Build frontend for production
	cd frontend && npm run build

front-lint:      ## Lint frontend with eslint
	cd frontend && npm run lint

# ── Database ──────────────────────────────────────────────────────
db-shell:        ## Open psql in the postgres container
	docker compose exec postgres psql -U $${POSTGRES_USER:-app} -d $${POSTGRES_DB:-hosting}

db-migrate:      ## Run alembic migrations inside backend container
	docker compose exec backend alembic upgrade head

db-revision:     ## Create a new alembic revision (usage: make db-revision MSG="description")
	docker compose exec backend alembic revision --autogenerate -m "$(MSG)"

# ── Code generation ───────────────────────────────────────────────
api-types:       ## Export OpenAPI schema and generate frontend TS types
	cd backend && python scripts/export_openapi.py
	cd frontend && npm run generate-api-types

# ── Utilities ─────────────────────────────────────────────────────
clean:           ## Remove stopped containers, dangling images and volumes
	docker compose down --remove-orphans -v
	docker image prune -f

env:             ## Copy .env.example to .env (won't overwrite)
	@cp -n .env.example .env 2>/dev/null && echo ".env created" || echo ".env already exists"

# ── Help ──────────────────────────────────────────────────────────
help:            ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*##' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*## "}; {printf "  \033[36m%-16s\033[0m %s\n", $$1, $$2}'

.PHONY: up down logs logs-back logs-front restart ps \
        back-shell back-lint back-format \
        front-dev front-build front-lint \
        db-shell db-migrate db-revision \
        api-types clean env help
