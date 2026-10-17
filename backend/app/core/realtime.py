"""Realtime fan-out for ws://<host>:8080/ws/v1/matches/{match_id}.

Single API process => an in-process hub is sufficient (mobile falls back to polling anyway).
Domain code publishes *after* its transaction committed (never for rolled-back changes).
"""
from __future__ import annotations

import json
import logging
from collections import defaultdict
from typing import Any

import anyio
from starlette.websockets import WebSocket

log = logging.getLogger("nascon.realtime")


class Hub:
    def __init__(self) -> None:
        self.clients: dict[str, set[WebSocket]] = defaultdict(set)

    async def connect(self, match_id: str, ws: WebSocket) -> None:
        self.clients[match_id].add(ws)

    def disconnect(self, match_id: str, ws: WebSocket) -> None:
        self.clients[match_id].discard(ws)
        if not self.clients[match_id]:
            self.clients.pop(match_id, None)

    async def publish(self, match_id: str, message: dict[str, Any]) -> None:
        text = json.dumps(message)
        for ws in list(self.clients.get(match_id, ())):
            try:
                await ws.send_text(text)
            except Exception:  # noqa: BLE001 - a dead socket must not break the publisher
                self.disconnect(match_id, ws)


hub = Hub()


def publish_from_thread(match_id: str, message: dict[str, Any]) -> None:
    """Call from a worker-thread route handler after commit. Best effort."""
    try:
        anyio.from_thread.run(hub.publish, match_id, message)
    except Exception:  # noqa: BLE001
        log.debug("realtime publish skipped", exc_info=True)
