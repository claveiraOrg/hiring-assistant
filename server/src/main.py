from __future__ import annotations

import asyncio
import os
from contextlib import asynccontextmanager

import asyncpg
from fastapi import FastAPI

from src.config.settings import get_settings
from src.db.connection import close_db, init_db


async def wait_for_db(retries: int = 30) -> None:
    # asyncpg needs postgresql:// not postgresql+asyncpg://
    dsn = os.environ.get("DATABASE_URL", "").replace("postgresql+asyncpg://", "postgresql://")
    for attempt in range(retries):
        try:
            conn = await asyncpg.connect(dsn)
            await conn.close()
            return
        except Exception as e:
            if attempt == retries - 1:
                raise RuntimeError(f"DB not ready after {retries}s: {e}")
            await asyncio.sleep(1)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: wait for DB, init schema on startup, close on shutdown."""
    await wait_for_db()
    await init_db()
    yield
    await close_db()


def create_app() -> FastAPI:
    get_settings()
    app = FastAPI(
        title="Hermes Hiring Platform",
        version="0.1.0",
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
    )

    @app.get("/health")
    async def health():
        return {"status": "ok", "service": "hermes-hiring"}

    return app


app = create_app()
