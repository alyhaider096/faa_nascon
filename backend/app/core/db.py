"""PostgreSQL access: connection pool, transactions and ordered SQL migrations."""
from __future__ import annotations

import logging
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

import psycopg
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

log = logging.getLogger("nascon.db")

MIGRATIONS_DIR = Path(__file__).resolve().parents[2] / "migrations"
MIGRATION_LOCK = 7001

_pool: ConnectionPool | None = None


def init_pool(url: str, max_size: int = 40) -> ConnectionPool:
    global _pool
    if _pool is not None:
        return _pool
    _pool = ConnectionPool(
        url, min_size=2, max_size=max_size, kwargs={"row_factory": dict_row},
        open=False, timeout=30,
    )
    _pool.open(wait=True, timeout=60)
    return _pool


def close_pool() -> None:
    global _pool
    if _pool is not None:
        _pool.close()
        _pool = None


def get_pool() -> ConnectionPool:
    if _pool is None:
        raise RuntimeError("database pool is not initialised")
    return _pool


@contextmanager
def tx() -> Iterator[psycopg.Connection]:
    """One transaction: commit on success, roll back on any exception."""
    with get_pool().connection() as conn:
        yield conn


def wait_for_db(url: str, seconds: float = 90.0) -> None:
    deadline = time.monotonic() + seconds
    last: Exception | None = None
    while time.monotonic() < deadline:
        try:
            with psycopg.connect(url, connect_timeout=3) as c:
                c.execute("SELECT 1")
            return
        except Exception as exc:  # noqa: BLE001 - startup retry loop
            last = exc
            time.sleep(1.0)
    raise RuntimeError(f"database not reachable after {seconds}s: {last}")


def migrate(url: str) -> list[str]:
    """Apply migrations/*.sql in filename order exactly once, under an advisory lock."""
    applied: list[str] = []
    with psycopg.connect(url, autocommit=True) as conn:
        conn.execute("SELECT pg_advisory_lock(%s)", (MIGRATION_LOCK,))
        try:
            conn.execute(
                "CREATE TABLE IF NOT EXISTS schema_migrations ("
                "name text PRIMARY KEY, applied_at timestamptz NOT NULL DEFAULT now())"
            )
            done = {r[0] for r in conn.execute("SELECT name FROM schema_migrations")}
            for path in sorted(MIGRATIONS_DIR.glob("*.sql")):
                if path.name in done:
                    continue
                with conn.transaction():
                    conn.execute(path.read_text(encoding="utf-8"))
                    conn.execute("INSERT INTO schema_migrations (name) VALUES (%s)", (path.name,))
                applied.append(path.name)
                log.info("applied migration %s", path.name)
        finally:
            conn.execute("SELECT pg_advisory_unlock(%s)", (MIGRATION_LOCK,))
    return applied
