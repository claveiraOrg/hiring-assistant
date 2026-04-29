# Hermes Hiring Platform

GDPR-compliant AI hiring platform with multi-agent orchestration.

## Architecture

Multi-agent distributed intelligence system with Hermes as deterministic workflow orchestrator.

### Agents

- **Profile Intelligence** — CV → structured candidate profile + embeddings
- **Job Intelligence** — Job description → structured job intent + embeddings
- **Matching** — Batch candidate-job relevance scoring
- **GDPR Compliance** — Consent verification, data minimization, audit logging
- **Feedback Learning** (Phase 2) — Ranking weight adaptation from recruiter signals

### Performance SLAs

- CV ingestion: <5s
- Job → shortlist: <10s
- Candidate query: <2s (cached)

## Quick Start

```bash
# Start infrastructure
make up

# Install dependencies
pip install -e ".[dev]"

# Initialize database
python -c "import asyncio; from src.db.connection import init_db; asyncio.run(init_db())"

# Run the API
uvicorn src.main:app --reload --port 8080
```

## Infrastructure (Docker Compose)

- PostgreSQL 16 + pgvector (port 5432)
- Redis 7 (port 6379)
- MinIO S3 (ports 9000, 9001)
