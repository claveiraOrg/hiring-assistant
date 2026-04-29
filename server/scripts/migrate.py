#!/usr/bin/env python3
"""Create all tables in the database.

Usage: python scripts/migrate.py
"""

import asyncio
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.db.engine import engine
from src.db.models import Base


async def migrate():
    print("Creating all tables in hiring and audit schemas...")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("Done — all tables created.")
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(migrate())
