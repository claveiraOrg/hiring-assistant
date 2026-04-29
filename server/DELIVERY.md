# GDPR-Compliant AI Hiring Platform — Delivery Report

**Project:** `/home/chamy/claveira/paperclip/server/hermes-hiring/`
**Tests:** 175/175 passing
**Status:** Complete

## Built Components

| Component | Tests | Description |
|-----------|-------|-------------|
| Profile Intelligence Agent | 14 | LLM CV extraction, confidence scoring, embedding gen |
| Job Intelligence Agent | 16 | LLM JD extraction, 2-layer ambiguity detection |
| Matching Agent | 43 | Skills 40%/Exp 25%/Domain 15%/Salary 10%/Location 10% |
| GDPR Compliance Agent | 23 | Consent, minimization (4 roles), audit, cascade deletion |
| Feedback Learning Agent | 21 | Recruiter/candidate tracking, Bayesian weight adjustment |
| Hermes Orchestrator | 20 | Matching flow <10s, ingestion flow <5s, anti-leakage router |
| Observability | 27 | OTel tracing, Prometheus metrics, JSON logging, 9 alerts |

## Architecture

Multi-agent distributed system with Hermes deterministic orchestrator.
PostgreSQL 16 + pgvector for storage, MinIO for objects, Redis for cache.
All agents stateless, independently deployable, schema-validated, versioned.

## Run Tests
```bash
cd /home/chamy/claveira/paperclip/server/hermes-hiring
PYTHONPATH=. python3 -m pytest services/ orchestrator/ observability/
```

## Deploy
```bash
cd /home/chamy/claveira/paperclip/server/hermes-hiring
docker compose up -d
python scripts/migrate.py
```
