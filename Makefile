.PHONY: dev dev-down test test-infra test-infra-down lint format typecheck migrate backend frontend install

# ─── Infrastructure ───────────────────────────────────────
dev:
	docker compose -f docker/docker-compose.yml up -d

dev-down:
	docker compose -f docker/docker-compose.yml down

test-infra:
	docker compose -f docker/docker-compose.test.yml up -d

test-infra-down:
	docker compose -f docker/docker-compose.test.yml down -v

# ─── Backend ──────────────────────────────────────────────
install:
	cd backend && uv sync --all-extras

backend:
	cd backend && uv run uvicorn lingshu.main:app --reload --port 8000

migrate:
	cd backend && uv run alembic upgrade head

migrate-new:
	cd backend && uv run alembic revision --autogenerate -m "$(msg)"

test:
	cd backend && uv run pytest --cov=lingshu --cov-report=term-missing

test-unit:
	cd backend && uv run pytest tests/unit -v

test-integration:
	cd backend && uv run pytest tests/integration -v

lint:
	cd backend && uv run ruff check .

format:
	cd backend && uv run ruff format .

typecheck:
	cd backend && uv run mypy .

# ─── Frontend ─────────────────────────────────────────────
frontend:
	cd frontend && pnpm dev

frontend-install:
	cd frontend && pnpm install

frontend-test:
	cd frontend && pnpm test

frontend-build:
	cd frontend && pnpm build

# ─── All ──────────────────────────────────────────────────
check: lint typecheck test
	@echo "All checks passed!"
