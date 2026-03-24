"""Apply init.sql schema idempotently to the database.

Usage (standalone):
    DATABASE_URL=postgres://... python scripts/ensure_schema.py

Usage (as module):
    from scripts.ensure_schema import ensure_schema
    await ensure_schema(connection)
"""

from __future__ import annotations

import asyncio
import os
from pathlib import Path


INIT_SQL = Path(__file__).parent / "init.sql"


def read_init_sql() -> str:
    """Read the init.sql file and return its contents."""
    return INIT_SQL.read_text()


async def ensure_schema(conn) -> None:
    """Execute init.sql against the given asyncpg connection or pool.

    All statements use IF NOT EXISTS / ADD COLUMN IF NOT EXISTS,
    so this is safe to run repeatedly.
    """
    sql = read_init_sql()
    await conn.execute(sql)


async def _main() -> None:
    """Standalone entry point — reads DATABASE_URL from environment."""
    import asyncpg  # noqa: F811

    dsn = os.environ.get("DATABASE_URL")
    if not dsn:
        raise SystemExit("DATABASE_URL environment variable is required")

    conn = await asyncpg.connect(dsn)
    try:
        await ensure_schema(conn)
        print("Schema applied successfully.")
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(_main())
