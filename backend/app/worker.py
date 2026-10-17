"""Queue worker: relays committed outbox rows to the Redis Stream, and keeps running if Redis blips.

Run:  python -m app.worker
Rows are claimed with FOR UPDATE SKIP LOCKED inside a transaction; reset's TRUNCATE waits for that
transaction, so a reset can never be followed by a stale publish of pre-reset events.
"""
from __future__ import annotations

import logging
import signal
import time

import psycopg
from psycopg.rows import dict_row

from .core import queue
from .core.config import load_settings
from .core.db import wait_for_db

log = logging.getLogger("nascon.worker")
_running = True


def _stop(*_):
    global _running
    _running = False


def relay_once(conn: psycopg.Connection, r) -> int:
    """Publish one batch of unpublished outbox rows; returns how many were relayed."""
    with conn.transaction():
        rows = conn.execute(
            "SELECT id, topic, payload FROM outbox WHERE published_at IS NULL"
            " ORDER BY id LIMIT 100 FOR UPDATE SKIP LOCKED").fetchall()
        for row in rows:
            queue.publish(r, row["topic"], row["payload"], row["id"])
            conn.execute("UPDATE outbox SET published_at=now() WHERE id=%s", (row["id"],))
    return len(rows)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
    signal.signal(signal.SIGTERM, _stop)
    signal.signal(signal.SIGINT, _stop)
    settings = load_settings()               # fails clearly if DAY1_SALT is missing
    wait_for_db(settings.database_url)
    r = queue.client(settings.redis_url)
    log.info("worker started")
    conn: psycopg.Connection | None = None
    while _running:
        try:
            if conn is None or conn.closed:
                conn = psycopg.connect(settings.database_url, row_factory=dict_row)
            n = relay_once(conn, r)
            time.sleep(0.05 if n else 0.5)
        except Exception:  # noqa: BLE001 - keep the worker alive; retry with backoff
            log.exception("worker iteration failed; retrying")
            try:
                if conn is not None:
                    conn.close()
            except Exception:  # noqa: BLE001
                pass
            conn = None
            time.sleep(2.0)


if __name__ == "__main__":
    main()
