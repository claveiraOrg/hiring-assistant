# AI Hiring Assistant

Resume intelligence and passive candidate matching platform. Upload a job description and CVs; get an AI-ranked shortlist in ≤30 s.

## Architecture

| Layer | Choice |
|---|---|
| Backend API | Python 3.12 / FastAPI |
| Frontend | Next.js 14 (TypeScript, App Router) |
| Task queue | Redis + RQ |
| Database | PostgreSQL 16 + pgvector |
| File storage | Cloudflare R2 |
| Backend hosting | Railway |
| Frontend hosting | Vercel |
| Auth | Clerk |

Full technical design: [CLAA-3 plan doc](https://paperclip.ing/CLAA/issues/CLAA-3#document-plan)

## Prerequisites

- Python 3.12+
- Node.js 20+
- Docker and Docker Compose
- `make`

## Getting started (local dev)

### 1. Clone and configure

```bash
git clone <repo-url>
cd hiring-assistant
cp .env.example .env
# Fill in API keys in .env (Anthropic, OpenAI, Clerk, R2)
```

### 2. Start infrastructure

```bash
make dev-db
# Starts Postgres 16 + pgvector on :5432 and Redis on :6379
```

### 3. Set up the backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
cd ..
make migrate                # Runs alembic upgrade head
```

### 4. Set up the frontend

```bash
cd frontend
npm install
cd ..
```

### 5. Start everything

```bash
# All services in one command (requires tmux or separate terminals):
make dev-backend   # FastAPI on http://localhost:8000
make dev-frontend  # Next.js on http://localhost:3000
make dev-worker    # RQ worker (extraction, scoring, pairwise, fingerprint, deletion queues)
```

Or run all in parallel (Unix only):

```bash
make dev
```

### 6. Verify

- Backend health: http://localhost:8000/health
- API docs (dev only): http://localhost:8000/docs
- Frontend: http://localhost:3000

## Common tasks

```bash
make migrate                    # Apply pending migrations
make migrate-create name="..."  # Create a new migration
make test                       # Run all tests
make lint                       # Lint (ruff + mypy + eslint)
make fmt                        # Auto-format (ruff + prettier)
```

## Environment variables

See `.env.example` for all variables. Required for local dev:

| Variable | Purpose |
|---|---|
| `DATABASE_URL` | PostgreSQL connection string |
| `REDIS_URL` | Redis connection string |
| `ANTHROPIC_API_KEY` | LLM calls (scoring, extraction) |
| `OPENAI_API_KEY` | text-embedding-3-small embeddings |
| `CLERK_SECRET_KEY` | Backend auth validation |
| `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY` | Frontend auth |
| `R2_*` | Cloudflare R2 file storage |
| `SECRET_KEY` | JWT signing (min 32 chars) |

Observability vars (Sentry, Langfuse) are optional for local dev.

## Repo structure

```
.
├── backend/                  # Python / FastAPI
│   ├── app/
│   │   ├── api/v1/           # Route handlers
│   │   ├── core/             # Config, logging
│   │   ├── db/               # SQLAlchemy session
│   │   ├── models/           # ORM models (all tables from technical design)
│   │   ├── schemas/          # Pydantic request/response schemas
│   │   ├── services/         # Business logic
│   │   └── workers/          # RQ worker jobs
│   ├── migrations/           # Alembic migrations
│   ├── tests/
│   ├── Dockerfile
│   └── pyproject.toml
├── frontend/                 # Next.js 14
│   └── src/app/              # App Router pages and layouts
├── .github/workflows/
│   └── ci.yml                # Lint + test + build on every PR
├── docker-compose.yml        # Postgres + Redis for local dev
├── .env.example              # All required env vars with descriptions
├── Makefile                  # Dev shortcuts
└── README.md
```

## CI

GitHub Actions runs on every PR and push to `main`:

- **Backend**: ruff lint, ruff format check, mypy, pytest with real Postgres + Redis
- **Frontend**: ESLint, TypeScript check, Jest, Next.js build

## Staging deployment

- **Backend**: push to `main` → Railway auto-deploys from `backend/` directory
- **Frontend**: push to `main` → Vercel auto-deploys from `frontend/` directory
- Preview environments: Vercel creates a preview URL for every PR automatically

Railway and Vercel projects must be linked to this repo (one-time setup by infra owner).

## Adding a new migration

```bash
# After changing a model file:
make migrate-create name="add_something_to_candidates"
# Review the generated file in backend/migrations/versions/
make migrate
```

## Worker queues

| Queue | Jobs |
|---|---|
| `extraction` | CV text extraction, synonym normalization, embedding |
| `scoring` | Candidate scoring (Sonnet), penalty table post-processing |
| `pairwise` | Pairwise ranking (Haiku) after all scoring completes |
| `fingerprint` | Recruiter fingerprint updates (async, eventual consistency) |
| `deletion` | GDPR hard-delete jobs (24h SLA) |
