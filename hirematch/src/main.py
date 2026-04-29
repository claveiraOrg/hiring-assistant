from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.v1.candidates import router as candidates_router
from src.api.v1.jobs import router as jobs_router
from src.api.v1.matches import router as matches_router
from src.core.config import settings
from src.core.db import engine

log = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("hirematch.startup")
    yield
    await engine.dispose()
    log.info("hirematch.shutdown")


app = FastAPI(title="hirematch", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

app.include_router(candidates_router)
app.include_router(jobs_router)
app.include_router(matches_router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "hirematch"}
