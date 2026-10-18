"""Queue worker: relays committed outbox rows to the Redis Stream, and keeps running if Redis blips.

Run:  python -m app.worker
Rows are claimed with FOR UPDATE SKIP LOCKED inside a transaction; reset's TRUNCATE waits for that
transaction, so a reset can never be followed by a stale publish of pre-reset events.
"""
from __future__ import annotations

import hashlib
import json
import logging
import signal
import time
import urllib.error
import urllib.request
from pathlib import Path

import psycopg
from psycopg.rows import dict_row

from .core import object_store, queue
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


def active_media_paths() -> set[str] | None:
    """Return paths still being published; unknown state is treated conservatively."""
    try:
        with urllib.request.urlopen("http://media:9997/v3/paths/list", timeout=2) as response:
            items = json.load(response).get("items", [])
        return {item["name"] for item in items if item.get("ready") and item.get("name")}
    except (OSError, ValueError, urllib.error.URLError):
        return None


def index_recordings_once(conn: psycopg.Connection, store, bucket: str, recordings_dir: str,
                          active_paths: set[str]) -> int:
    """Upload completed MediaMTX recordings and atomically publish their DB index."""
    root = Path(recordings_dir)
    if not root.is_dir():
        return 0
    if not store.bucket_exists(bucket):
        store.make_bucket(bucket)
    indexed = 0
    for path in sorted(root.rglob("*.mp4")):
        size = path.stat().st_size
        if size <= 0:
            continue
        source_path = path.relative_to(root).as_posix()
        with conn.transaction():
            exists = conn.execute(
                "SELECT 1 FROM day2_vod_assets WHERE source_path=%s", (source_path,)
            ).fetchone()
        if exists:
            continue
        stream_path = path.parent.relative_to(root).as_posix()
        if stream_path in active_paths:
            continue
        object_key = f"recordings/{source_path}"
        result = store.fput_object(bucket, object_key, str(path), content_type="video/mp4")
        vod_id = "vod_" + hashlib.sha256(source_path.encode("utf-8")).hexdigest()[:24]
        with conn.transaction():
            match = (conn.execute(
                "SELECT match_id FROM day2_match_state WHERE status IN ('in_progress','completed') "
                "ORDER BY match_id LIMIT 1"
            ).fetchone() if stream_path.startswith("live/") else None)
            match_id = match["match_id"] if match else None
            inserted = conn.execute(
                "INSERT INTO day2_vod_assets(vod_id,source_path,object_key,stream_path,match_id,size_bytes,etag) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s) ON CONFLICT(source_path) DO NOTHING",
                (vod_id, source_path, object_key, stream_path, match_id, size, result.etag),
            ).rowcount
        indexed += inserted
    return indexed


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
    signal.signal(signal.SIGTERM, _stop)
    signal.signal(signal.SIGINT, _stop)
    settings = load_settings()               # fails clearly if DAY1_SALT is missing
    wait_for_db(settings.database_url)
    r = queue.client(settings.redis_url)
    store = object_store.client(settings)
    log.info("worker started")
    conn: psycopg.Connection | None = None
    next_vod_scan = 0.0
    while _running:
        try:
            if conn is None or conn.closed:
                conn = psycopg.connect(settings.database_url, row_factory=dict_row)
            n = relay_once(conn, r)
            now = time.monotonic()
            if now >= next_vod_scan:
                active_paths = active_media_paths()
                uploaded = (index_recordings_once(
                    conn, store, settings.minio_bucket, settings.recordings_dir, active_paths
                ) if active_paths is not None else 0)
                if uploaded:
                    log.info("indexed %s completed VOD recording(s)", uploaded)
                next_vod_scan = now + 2.0
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
