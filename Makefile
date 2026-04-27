.PHONY: help dev dev-db dev-backend dev-frontend dev-worker migrate test lint fmt clean

help:
	@echo "Usage: make <target>"
	@echo ""
	@echo "  dev           Start all services (db, backend, frontend, worker)"
	@echo "  dev-db        Start Postgres + Redis only"
	@echo "  dev-backend   Start FastAPI dev server"
	@echo "  dev-frontend  Start Next.js dev server"
	@echo "  dev-worker    Start RQ worker"
	@echo "  migrate       Run database migrations"
	@echo "  test          Run all tests"
	@echo "  lint          Run linters (ruff + mypy + eslint)"
	@echo "  fmt           Auto-format code (ruff + prettier)"
	@echo "  clean         Remove compiled artifacts"

dev-db:
	docker compose up -d db redis

dev-backend:
	cd backend && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

dev-frontend:
	cd frontend && npm run dev

dev-worker:
	cd backend && rq worker --url $$REDIS_URL extraction scoring pairwise fingerprint deletion

dev: dev-db
	@echo "Starting backend, frontend, and worker in parallel..."
	@trap 'kill 0' INT; \
	  make dev-backend & \
	  make dev-frontend & \
	  make dev-worker & \
	  wait

migrate:
	cd backend && alembic upgrade head

migrate-create:
	cd backend && alembic revision --autogenerate -m "$(name)"

test:
	cd backend && pytest --cov=app --cov-report=term-missing
	cd frontend && npm test -- --passWithNoTests

lint:
	cd backend && ruff check . && mypy app
	cd frontend && npm run lint

fmt:
	cd backend && ruff format . && ruff check --fix .
	cd frontend && npm run format

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .mypy_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .ruff_cache -exec rm -rf {} + 2>/dev/null || true
	rm -rf frontend/.next
