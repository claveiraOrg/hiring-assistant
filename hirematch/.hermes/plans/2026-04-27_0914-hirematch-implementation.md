# HireMatch — GDPR-Compliant AI Hiring Platform Implementation Plan

> **For Hermes:** Execute this plan using subagent-driven-development.
>
> **Goal:** Build a production-grade, GDPR-compliant AI hiring platform with multi-agent orchestration that matches candidates to jobs in <10 seconds end-to-end.

## Architecture

Distributed multi-agent system with Hermes as deterministic orchestration engine. Five single-responsibility agents communicate through structured, schema-validated interfaces. PostgreSQL + pgvector for data + embeddings. Object storage (local filesystem) for raw CVs/documents.

## Tech Stack

- **Orchestration:** Python (Hermes-compatible), deterministic workflow engine
- **API:** FastAPI
- **Database:** PostgreSQL + pgvector extension
- **Object Storage:** Local filesystem (minio-compatible interface)
- **LLM:** OpenAI-compatible API (configurable provider)
- **Validation:** Pydantic v2
- **Embeddings:** sentence-transformers (all-MiniLM-L6-v2)
- **Observability:** structlog, Prometheus metrics, OpenTelemetry tracing
- **Testing:** pytest with coverage
- **Containerization:** Docker Compose

---

## Phases

### Phase 1: Foundation & Core Data Layer (Tasks 1-7)
### Phase 2: Agent System — Profile & Job (Tasks 8-16)
### Phase 3: Matching Engine & GDPR (Tasks 17-24)
### Phase 4: Orchestration Layer & API (Tasks 25-30)
### Phase 5: Observability & Production Readiness (Tasks 31-34)

---

## TASKS

## Phase 1: Foundation & Core Data Layer

### Task 1: Project scaffolding & dependency management

**Objective:** Set up pyproject.toml, requirements.txt, Docker Compose, and .env

**Files:**
- Create: `/home/chamy/claveira/hirematch/pyproject.toml`
- Create: `/home/chamy/claveira/hirematch/requirements.txt`
- Create: `/home/chamy/claveira/hirematch/docker-compose.yml`
- Create: `/home/chamy/claveira/hirematch/.env.example`
- Create: `/home/chamy/claveira/hirematch/Makefile`

**Implementation content:**

`pyproject.toml`:
```toml
[project]
name = "hirematch"
version = "0.1.0"
description = "GDPR-compliant AI hiring platform with multi-agent orchestration"
requires-python = ">=3.11"
dependencies = [
    "fastapi>=0.110.0",
    "uvicorn[standard]>=0.27.0",
    "pydantic>=2.5.0",
    "pydantic-settings>=2.1.0",
    "sqlalchemy[asyncio]>=2.0.25",
    "asyncpg>=0.29.0",
    "pgvector>=0.2.5",
    "sentence-transformers>=2.2.0",
    "structlog>=24.1.0",
    "opentelemetry-api>=1.22.0",
    "opentelemetry-sdk>=1.22.0",
    "opentelemetry-instrumentation-fastapi>=0.43b0",
    "prometheus-client>=0.19.0",
    "httpx>=0.27.0",
    "tenacity>=8.2.0",
    "python-multipart>=0.0.6",
    "aiofiles>=23.2.0",
    "alembic>=1.13.0",
    "cryptography>=42.0.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=7.4.0",
    "pytest-asyncio>=0.23.0",
    "pytest-cov>=4.1.0",
    "pytest-mock>=3.12.0",
    "httpx>=0.27.0",
    "coverage>=7.4.0",
    "ruff>=0.2.0",
    "mypy>=1.8.0",
]
```

`requirements.txt` — same as pyproject.toml dependencies.

`docker-compose.yml`:
```yaml
version: "3.8"
services:
  postgres:
    image: pgvector/pgvector:pg16
    environment:
      POSTGRES_DB: hirematch
      POSTGRES_USER: hirematch
      POSTGRES_PASSWORD: hirematch_dev
    ports:
      - "5432:5432"
    volumes:
      - pgdata:/var/lib/postgresql/data

  hirematch:
    build: .
    depends_on:
      - postgres
    env_file: .env
    ports:
      - "8000:8000"
    volumes:
      - ./data:/data
      - ./config:/app/config

volumes:
  pgdata:
```

`.env.example`:
```
DATABASE_URL=postgresql+asyncpg://hirematch:hirematch_dev@localhost:5432/hirematch
VECTOR_DIMENSION=384
OBJECT_STORE_PATH=./data/objects
LLM_API_KEY=
LLM_BASE_URL=https://api.openai.com/v1
LLM_MODEL=gpt-4o-mini
EMBEDDING_MODEL=all-MiniLM-L6-v2
LOG_LEVEL=INFO
OTEL_SERVICE_NAME=hirematch
```

`Makefile`:
```makefile
.PHONY: install dev test lint run migrate

install:
	pip install -r requirements.txt

dev:
	uvicorn src.api.main:app --reload --host 0.0.0.0 --port 8000

test:
	pytest tests/ -v --cov=src --cov-report=term

lint:
	ruff check src/ tests/
	mypy src/

run:
	uvicorn src.api.main:app --host 0.0.0.0 --port 8000

migrate:
	alembic upgrade head
```

**Verification:** `cd /home/chamy/claveira/hirematch && pip install -r requirements.txt` succeeds.

---

### Task 2: Pydantic schemas — Candidates

**Objective:** Define Candidate model with skills, experience, domains, career trajectory, and confidence scoring.

**Files:**
- Create: `/home/chamy/claveira/hirematch/src/models/__init__.py`
- Create: `/home/chamy/claveira/hirematch/src/models/candidate.py`

**Key types:**
- `Skill(name, level, years_experience)`
- `Experience(role, company, start_date, end_date, description, skills_used)`
- `Domain(name, relevance_score)`
- `CareerArc(positions[], growth_trajectory, domain_transitions)`
- `CandidateProfile(id, name, skills[], experience[], domains[], career_trajectory, embedding, confidence_score, consent_status)`
- `CVUploadResult(candidate_id, profile, confidence, processing_time_ms)`

All Pydantic v2 models with strict validation.

---

### Task 3: Pydantic schemas — Jobs & Matches

**Objective:** Define Job model, Match model, and scoring breakdown.

**Files:**
- Create: `/home/chamy/claveira/hirematch/src/models/job.py`
- Create: `/home/chamy/claveira/hirematch/src/models/match.py`

**Key types:**
- `JobDescription(required_skills[], preferred_skills[], seniority, constraints, salary_range, location, domain)`
- `JobPosting(id, title, description, structured_model, embedding, created_at)`
- `MatchResult(candidate_id, job_id, score, breakdown{skills, experience, domain, salary, location}, confidence, explanation)`
- `RankedShortlist(matches[], job_id, generated_at_ms, processing_time_ms)`

**Tip:** Use computed_fields for total_score.

---

### Task 4: Pydantic schemas — GDPR & Workflow

**Objective:** Define GDPR models and Hermes workflow state models.

**Files:**
- Create: `/home/chamy/claveira/hirematch/src/models/gdpr.py`
- Create: `/home/chamy/claveira/hirematch/src/hermes/workflow_state.py`

**Key types:**
- `ConsentRecord(candidate_id, granted, granted_at, revoked_at, scope)`
- `AccessLog(candidate_id, recruiter_id, agent_name, accessed_at, action, resource)`
- `DataVisibilityRule(agent_name, allowed_fields[], filter_expression)`
- `WorkflowState(workflow_id, step, status, agent_outputs, errors, started_at, completed_at)`
- `WorkflowStep(name, status, output_schema, error, retry_count)`

---

### Task 5: Database layer — PostgreSQL setup

**Objective:** SQLAlchemy async engine, Base, session factory, and migration scripts.

**Files:**
- Create: `/home/chamy/claveira/hirematch/src/db/__init__.py`
- Create: `/home/chamy/claveira/hirematch/src/db/postgres.py`
- Create: `/home/chamy/claveira/hirematch/src/db/models.py`
- Create: `/home/chamy/claveira/hirematch/scripts/init_db.sql`

**Key details:**
- Async SQLAlchemy with asyncpg driver
- Tables: candidates, job_postings, matches, consent_logs, access_logs, workflow_states
- pgvector column on candidates and job_postings for embeddings
- Proper indexes on foreign keys, timestamps, scoring columns
- `init_db.sql` creates the database and enables pgvector extension

**init_db.sql**:
```sql
CREATE EXTENSION IF NOT EXISTS vector;
CREATE TABLE IF NOT EXISTS candidates (
    id UUID PRIMARY KEY,
    profile JSONB NOT NULL,
    embedding vector(384),
    confidence_score FLOAT,
    consent_status VARCHAR(20) DEFAULT 'pending',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE TABLE IF NOT EXISTS job_postings (
    id UUID PRIMARY KEY,
    structured_model JSONB NOT NULL,
    embedding vector(384),
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE TABLE IF NOT EXISTS matches (
    id UUID PRIMARY KEY,
    candidate_id UUID REFERENCES candidates(id),
    job_id UUID REFERENCES job_postings(id),
    score FLOAT,
    breakdown JSONB,
    confidence FLOAT,
    explanation TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_matches_candidate ON matches(candidate_id);
CREATE INDEX idx_matches_job ON matches(job_id);
```

---

### Task 6: Vector store layer

**Objective:** Embedding service using sentence-transformers, pgvector similarity search.

**Files:**
- Create: `/home/chamy/claveira/hirematch/src/db/vector_store.py`
- Create: `/home/chamy/claveira/hirematch/src/db/embeddings.py`

**Key details:**
- `EmbeddingService.generate_embedding(text: str) -> list[float]` — lazy-loads sentence-transformers model
- `VectorStore.search_similar(embedding, top_k=20, threshold=0.5) -> list[CandidateProfile]`
- `VectorStore.store_candidate_embedding(candidate_id, embedding)`
- `VectorStore.store_job_embedding(job_id, embedding)`
- Uses raw SQL with pgvector for async operations
- Model: `all-MiniLM-L6-v2` (384 dimensions)

---

### Task 7: Object storage layer

**Objective:** Local filesystem object store for raw CVs, parsed documents, and debug outputs.

**Files:**
- Create: `/home/chamy/claveira/hirematch/src/db/object_store.py`

**Key details:**
- `ObjectStore.upload(key, data, content_type) -> str`
- `ObjectStore.download(key) -> bytes`
- `ObjectStore.delete(key)`
- `ObjectStore.list(prefix) -> list[str]`
- Base path configurable via `OBJECT_STORE_PATH` env var
- Subdirectories: `raw/`, `parsed/`, `debug/`

---

## Phase 2: Agent System

### Task 8: Base agent class & common patterns

**Objective:** Abstract base class for all agents with retry, schema validation, observability, and versioning.

**Files:**
- Create: `/home/chamy/claveira/hirematch/src/agents/__init__.py`
- Create: `/home/chamy/claveira/hirematch/src/agents/base.py`

**Key interface:**
```python
class AgentConfig(BaseSettings):
    version: str = "1.0.0"
    timeout_seconds: int = 30
    max_retries: int = 3
    llm_model: str = "gpt-4o-mini"
    llm_api_key: str = ""
    llm_base_url: str = "https://api.openai.com/v1"

class BaseAgent(ABC):
    config: AgentConfig
    agent_name: str  # Override in subclass

    @abstractmethod
    async def process(self, input_data: BaseModel) -> BaseModel:
        """Process input and return validated output."""

    async def _call_llm(self, system_prompt: str, user_content: str, response_model: Type[BaseModel]) -> BaseModel:
        """Call LLM with structured output parsing."""

    async def _safe_process(self, input_data: BaseModel) -> BaseModel:
        """Wrapper with retry, timeout, logging, and metric emission."""
```

---

### Task 9: Profile Intelligence Agent — CV parsing

**Objective:** Convert raw CV text → structured CandidateProfile with confidence scoring.

**Files:**
- Create: `/home/chamy/claveira/hirematch/src/agents/profile_intelligence/__init__.py`
- Create: `/home/chamy/claveira/hirematch/src/agents/profile_intelligence/agent.py`
- Create: `/home/chamy/claveira/hirematch/src/agents/profile_intelligence/prompts.py`

**Key details:**
- `ProfileIntelligenceAgent.process(cv_text: str) -> CandidateProfileWithConfidence`
- LLM prompts to extract: skills (+ levels + years), experience timeline, domains, career trajectory
- Confidence score per extracted field (0.0-1.0)
- If CV has ambiguity or inconsistency, flag in confidence
- After extraction → generate embedding of concatenated profile text
- Store raw CV in object store under `raw/`, parsed profile under `parsed/`
- Must complete in <5 seconds per CV (use fast LLM + timeout)

**Prompts:**
- System prompt: "You are a CV parsing expert. Extract structured information from the following CV text. Be precise. If information is missing, use null. Provide confidence scores for each extracted field."
- Output format: strict JSON matching CandidateProfileWithConfidence schema

---

### Task 10: Profile Intelligence Agent — storage after processing

**Objective:** After parsing CV, store the profile in DB and embedding in vector store.

**Files:**
- Modify: `/home/chamy/claveira/hirematch/src/agents/profile_intelligence/agent.py`

**Logic:**
```
1. Receive CV text + candidate_id
2. Call LLM to extract structured profile
3. Generate embedding from concatenated profile fields
4. Store profile in PostgreSQL
5. Store embedding in pgvector
6. Store raw CV in object store
7. Return CVUploadResult with confidence score and processing time
```

---

### Task 11: Job Intelligence Agent — JD parsing

**Objective:** Convert free-text job description → structured JobDescription with ambiguity detection.

**Files:**
- Create: `/home/chamy/claveira/hirematch/src/agents/job_intelligence/__init__.py`
- Create: `/home/chamy/claveira/hirematch/src/agents/job_intelligence/agent.py`
- Create: `/home/chamy/claveira/hirematch/src/agents/job_intelligence/prompts.py`

**Key details:**
- `JobIntelligenceAgent.process(job_description: str) -> JobDescriptionWithConfidence`
- Extracts: required_skills[], preferred_skills[], seniority, constraints, salary_range, location, domain
- Detects ambiguity: missing salary, vague requirements, conflicting constraints
- Returns ambiguity_warnings[] for things the recruiter should clarify
- Generates embedding from structured job model
- Stores job model + embedding in DB

---

### Task 12: Job Intelligence Agent — storage after processing

**Objective:** After parsing JD, store the structured model in DB and embedding in vector store.

**Files:**
- Modify: `/home/chamy/claveira/hirematch/src/agents/job_intelligence/agent.py`

**Logic:**
```
1. Receive job_description + job_id
2. Call LLM to extract structured job model
3. Generate embedding from concatenated job fields
4. Store job posting in PostgreSQL
5. Store embedding in pgvector
6. Return JobProcessingResult with ambiguity_warnings
```

---

## Phase 3: Matching Engine & GDPR

### Task 13: Matching Agent — scoring engine

**Objective:** Compute candidate-job relevance scores with weighted breakdown and confidence.

**Files:**
- Create: `/home/chamy/claveira/hirematch/src/agents/matching/__init__.py`
- Create: `/home/chamy/claveira/hirematch/src/agents/matching/agent.py`
- Create: `/home/chamy/claveira/hirematch/src/agents/matching/scorer.py`

**Scoring formula:**
- **Skills (40%):** Jaccard similarity on skill names, weighted by seniority match
- **Experience (25%):** Years match (overlap / max), trajectory alignment
- **Domain (15%):** Cosine similarity on domain vectors
- **Salary fit (10%):** Overlap of expected vs offered ranges, 0 if no overlap
- **Location fit (10%):** 1.0 if match, 0.5 if remote allowed, 0.0 if mismatch

**Confidence scoring:**
- Based on completeness of input data
- If skills or experience are missing confidence drops to 0.6
- If salary or location missing, confidence drops 0.1 each

**Key interfaces:**
```python
async def compute_match(candidate: CandidateProfile, job: JobDescription) -> MatchResult
async def batch_match(candidates: list[CandidateProfile], job: JobDescription) -> list[MatchResult]
```

---

### Task 14: Matching Agent — batch inference & explainability

**Objective:** Support batch scoring over candidate pools with per-match explanations.

**Files:**
- Modify: `/home/chamy/claveira/hirematch/src/agents/matching/agent.py`

**Logic:**
```
1. Receive job embedding
2. Query vector store for top 50 semantically similar candidates
3. For each candidate, compute full weighted score
4. Filter candidates with consent_status='granted'
5. Sort by total score descending
6. Return top 20 with breakdown, confidence, and explanation text
7. Explanation text: "Matched on {skills}. Top skill match: {skill} at {level}"
```

---

### Task 15: GDPR Compliance Agent — consent & access control

**Objective:** Enforce consent verification, data minimization filtering, and audit logging.

**Files:**
- Create: `/home/chamy/claveira/hirematch/src/agents/gdpr/__init__.py`
- Create: `/home/chamy/claveira/hirematch/src/agents/gdpr/agent.py`
- Create: `/home/chamy/claveira/hirematch/src/gdpr/consent.py`
- Create: `/home/chamy/claveira/hirematch/src/gdpr/audit_log.py`
- Create: `/home/chamy/claveira/hirematch/src/gdpr/data_minimization.py`

**Key logic:**
- `GDPRAgent.filter_candidates(candidates[], recruiter_role) -> list[CandidateProfile]`:
  1. Check consent for each candidate — remove unconsented
  2. Apply data minimization rules per recruiter role
  3. Log every access event (who, what, when, which candidates)
  4. Return filtered, minimized profiles
- `GDPRAgent.enforce_before_output(ranked_shortlist, recruiter_context) -> RankedShortlist`
  1. Verify all candidates in shortlist have valid consent
  2. Strip PII fields not allowed for this recruiter
  3. Log access for audit
  4. Return clean shortlist

**Data minimization rules:**
- "recruiter" role can see: skills, experience, domains, match score, explanation
- "hiring_manager" role can additionally see: salary info, location
- "admin" role can see everything
- Candidates always see only their own data

---

### Task 16: GDPR Compliance Agent — right to deletion

**Objective:** Implement full cascade deletion of candidate data across all stores.

**Files:**
- Modify: `/home/chamy/claveira/hirematch/src/agents/gdpr/agent.py`
- Create: `/home/chamy/claveira/hirematch/src/gdpr/deletion.py`

**Logic:**
```python
async def delete_candidate(candidate_id: UUID) -> DeletionResult:
    """Cascade deletion across:
    1. PostgreSQL (candidates, matches, consent_logs)
    2. pgvector embeddings
    3. Object store files (raw/parsed/debug)
    4. Audit logs (anonymize)
    """
    deletions = []
    # DB records
    deletions += await delete_db_records(candidate_id)
    # Embeddings
    deletions += await delete_embeddings(candidate_id)
    # Files
    deletions += await delete_stored_files(candidate_id)
    # Anonymize audit logs (keep audit trail but remove PII)
    deletions += await anonymize_audit_logs(candidate_id)
    return DeletionResult(deleted_count=len(deletions), details=deletions)
```

---

### Task 17: Feedback Learning Agent (Phase 2 scaffold)

**Objective:** Build scaffold for feedback agent that learns from recruiter interactions and candidate engagement to adjust ranking weights over time.

**Files:**
- Create: `/home/chamy/claveira/hirematch/src/agents/feedback_learning/__init__.py`
- Create: `/home/chamy/claveira/hirematch/src/agents/feedback_learning/agent.py`

**Key details:**
- `FeedbackEvent(recruiter_id, candidate_id, job_id, action, timestamp)` — action = "shortlisted" | "rejected" | "interviewed" | "hired"
- `CandidateEngagement(candidate_id, job_id, viewed, applied, timestamp)`
- `WeightAdjustment(skill_weight, experience_weight, domain_weight, salary_weight, location_weight)`
- Phase 2 implementation: collects events, stores in DB, provides weight suggestion API
- Phase 1: just the data model + storage, no ML training yet

---

## Phase 4: Orchestration & API

### Task 18: Hermes Orchestrator — workflow engine

**Objective:** Central orchestration engine that routes tasks, maintains state, handles retries and fallbacks.

**Files:**
- Create: `/home/chamy/claveira/hirematch/src/hermes/__init__.py`
- Create: `/home/chamy/claveira/hirematch/src/hermes/orchestrator.py`
- Create: `/home/chamy/claveira/hirematch/src/hermes/config.py`
- Create: `/home/chamy/claveira/hirematch/src/hermes/router.py`

**Key interfaces:**
```python
class HermesOrchestrator:
    """Deterministic workflow engine with LLM-powered agents as nodes."""

    agents: dict[str, BaseAgent]

    async def process_cv(self, cv_text: str) -> CVUploadResult:
        """Workflow: CV → Profile Intelligence → Embedding → Vector Store → DB"""
        ...

    async def process_job(self, job_description: str) -> JobProcessingResult:
        """Workflow: JD → Job Intelligence → Embedding → DB"""
        ...

    async def match_candidates(self, job_id: UUID, recruiter_context: RecruiterContext) -> RankedShortlist:
        """Workflow: Fetch candidates → Matching Agent (batch) → GDPR filter → Return"""
        ...

    async def delete_candidate(self, candidate_id: UUID) -> DeletionResult:
        """Workflow: GDPR deletion agent → cascade"""
        ...
```

**Important:** Hermes maintains workflow_state per invocation. On LLM failure, retries up to 3 times. On data inconsistency, falls back to partial match. GDPR enforcement happens BEFORE any output is returned to the caller. Hermes prevents direct data leakage between agents by passing only schema-validated outputs.

---

### Task 19: FastAPI application — routes & middleware

**Objective:** REST API with endpoints for CV upload, job creation, matching, deletion, and health.

**Files:**
- Create: `/home/chamy/claveira/hirematch/src/api/__init__.py`
- Create: `/home/chamy/claveira/hirematch/src/api/main.py` (FastAPI app)
- Create: `/home/chamy/claveira/hirematch/src/api/routes.py`
- Create: `/home/chamy/claveira/hirematch/src/api/middleware.py`

**Endpoints:**
```
POST /api/v1/candidates/upload     — Upload CV (multipart)
POST /api/v1/jobs                  — Create job from description
POST /api/v1/jobs/{job_id}/match   — Match candidates to job
DELETE /api/v1/candidates/{id}     — GDPR deletion
GET  /api/v1/candidates/{id}       — Get candidate profile
GET  /api/v1/jobs/{id}             — Get job posting
GET  /api/v1/matches/{job_id}      — Get ranked shortlist
GET  /health                       — Health check
GET  /metrics                      — Prometheus metrics
```

**Middleware:**
- Request ID injection
- Structured logging (structlog)
- Latency tracking
- GDPR compliance check on all data-accessing endpoints

---

### Task 20: API routes — implementation

**Objective:** Wire orchestrator to routes with proper error handling and response models.

**Files:**
- Create: `/home/chamy/claveira/hirematch/src/api/routes.py`

**Key logic:**
- All routes return structured Pydantic responses
- Error responses follow RFC 7807 (Problem Details)
- Timeout at 30 seconds per request
- GDPR enforcement wrapper on all data-accessing routes

---

## Phase 5: Observability & Production Readiness

### Task 21: Structured logging

**Objective:** structlog-based structured logging with correlation IDs.

**Files:**
- Create: `/home/chamy/claveira/hirematch/src/observability/__init__.py`
- Create: `/home/chamy/claveira/hirematch/src/observability/logging.py`

**Key details:**
- `setup_logging(service_name, level) -> None`
- Structured JSON output with timestamps, levels, correlation IDs
- Agent name, workflow ID, task ID in every log line
- Anonymize PII in logs (don't log raw CV content)

---

### Task 22: Metrics

**Objective:** Prometheus metrics for all critical paths.

**Files:**
- Create: `/home/chamy/claveira/hirematch/src/observability/metrics.py`

**Metrics:**
```
hirematch_cv_processing_seconds (histogram)
hirematch_job_processing_seconds (histogram)
hirematch_matching_seconds (histogram)
hirematch_match_success_rate (gauge)
hirematch_workflow_failures_total (counter)
hirematch_gdpr_violations_total (counter) — CRITICAL severity alert
hirematch_candidates_processed_total (counter)
hirematch_llm_calls_total (counter)
hirematch_llm_call_duration_seconds (histogram)
```

---

### Task 23: Distributed tracing (OpenTelemetry)

**Objective:** Trace every agent call through the workflow.

**Files:**
- Modify: `/home/chamy/claveira/hirematch/src/observability/tracing.py`
- Create: `/home/chamy/claveira/hirematch/src/observability/tracing.py`

**Key details:**
- Use OpenTelemetry with FastAPI instrumentation
- Create spans per: agent call, LLM call, embedding generation, DB query, GDPR filter
- Trace context propagation via HTTP headers

---

### Task 24: Failure handling & edge cases

**Objective:** Graceful handling of all specified failure modes.

**Files:**
- Create: `/home/chamy/claveira/hirematch/src/hermes/failures.py`

**Failure modes:**
1. **LLM failure/timeout:** Retry 3x with exponential backoff. If all fail, return partial result with `llm_unavailable=True` flag.
2. **Inconsistent CV data:** Confidence scores drop per field. Matching agent uses what's available.
3. **Missing job information:** Job processing returns ambiguity_warnings. Matching handles null fields gracefully (null field = weight redistributed to other factors).
4. **Empty candidate pools:** Return empty shortlist with `pool_empty=True` flag, not an error.
5. **GDPR denial scenarios:** If candidate revokes consent mid-workflow, filter immediately. Log the denial. Return filtered results without the candidate.

---

### Task 25: Tests — comprehensive test suite

**Objective:** 80%+ coverage across all components.

**Files:**
- Create: `/home/chamy/claveira/hirematch/tests/__init__.py`
- Create: `/home/chamy/claveira/hirematch/tests/conftest.py`
- Create: `/home/chamy/claveira/hirematch/tests/test_models.py`
- Create: `/home/chamy/claveira/hirematch/tests/test_profile_agent.py`
- Create: `/home/chamy/claveira/hirematch/tests/test_job_agent.py`
- Create: `/home/chamy/claveira/hirematch/tests/test_matching.py`
- Create: `/home/chamy/claveira/hirematch/tests/test_gdpr.py`
- Create: `/home/chamy/claveira/hirematch/tests/test_orchestrator.py`
- Create: `/home/chamy/claveira/hirematch/tests/test_api.py`

**Key tests:**
- Model validation (required fields, constraints)
- Scoring correctness (all weights sum to 100%, edge cases)
- GDPR filtering (consent, data minimization, audit logging)
- Orchestrator workflow state management
- API request/response serialization
- Failure modes (LLM failure, empty pool, missing data)

---

### Task 26: README & Documentation

**Objective:** Comprehensive README with architecture diagram, setup instructions, API docs.

**Files:**
- Create: `/home/chamy/claveira/hirematch/README.md`

**Content:** Architecture overview, system components, setup guide, API reference, GDPR compliance notes, development guide.

---

## Execution Order

1. Tasks 1-7: Foundation (parallelize where possible)
2. Tasks 8-12: Agent A & B (serial within each agent, can parallel between agents)
3. Tasks 13-17: Agent C, D, E (GDPR is critical path, do first)
4. Tasks 18-20: Orchestration + API (depends on agents)
5. Tasks 21-24: Observability (can parallel with Phase 4)
6. Tasks 25-26: Tests + Docs
