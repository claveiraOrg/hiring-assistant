.PHONY: up down restart lint test migration clean

# Infrastructure
up:
	docker compose up -d
	@echo "Waiting for services..."
	@sleep 3
	@echo "PostgreSQL: localhost:5432"
	@echo "Redis:      localhost:6379"
	@echo "MinIO API:  localhost:9000"
	@echo "MinIO UI:   localhost:9001"

down:
	docker compose down

restart: down up

# Development
lint:
	ruff check src/ services/ orchestrator/ tests/
	ruff format --check src/ services/ orchestrator/ tests/

format:
	ruff format src/ services/ orchestrator/ tests/

test:
	pytest -v --cov=src --cov=services --cov=orchestrator tests/

test-quick:
	pytest -v --no-header -q tests/

typecheck:
	mypy src/ services/ orchestrator/

# Database
migrate:
	@echo "Run migration scripts from scripts/migrate.py"

# Cleanup
clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	rm -rf .pytest_cache .ruff_cache

# Build Docker images for agents
build-agents:
	docker compose -f docker-compose.agents.yml build
