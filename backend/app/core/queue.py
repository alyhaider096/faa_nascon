"""Internal queue: Redis Streams fed from the PostgreSQL outbox (never Redis-only authority)."""
from __future__ import annotations

import json
import logging

import redis

log = logging.getLogger("nascon.queue")

STREAM = "nascon:domain-events"
KEY_PREFIX = "nascon:"


def client(url: str) -> redis.Redis:
    return redis.Redis.from_url(url, socket_timeout=3, socket_connect_timeout=3, decode_responses=True)


def publish(r: redis.Redis, topic: str, payload: dict, outbox_id: int) -> None:
    r.xadd(STREAM, {"topic": topic, "outbox_id": str(outbox_id), "payload": json.dumps(payload)},
           maxlen=10_000, approximate=True)


def clear_all(url: str) -> None:
    """Called after a reset commits: drop stale queue/cache keys. Best effort."""
    try:
        r = client(url)
        for key in r.scan_iter(match=KEY_PREFIX + "*", count=500):
            r.delete(key)
    except Exception:  # noqa: BLE001 - Redis hiccups must never fail a reset
        log.warning("could not clear redis keys after reset", exc_info=True)
