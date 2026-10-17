"""Pure ASGI middleware: rolling per-IP rate limit for /api/v1/* and a streamed body-size cap."""
from __future__ import annotations

import json
import math
import time
from collections import defaultdict, deque

from .config import Settings

RATE_LIMITED_PREFIX = "/api/v1/"
DRAIN_CAP = 64 * 1024 * 1024  # stop reading an abusive upload after this many bytes


def _json_response(status: int, code: str, message: str, headers: list[tuple[bytes, bytes]] | None = None):
    body = json.dumps({"error": {"code": code, "message": message, "details": {}}}).encode("utf-8")
    head = [(b"content-type", b"application/json"), (b"content-length", str(len(body)).encode())]
    head += headers or []
    return (
        {"type": "http.response.start", "status": status, "headers": head},
        {"type": "http.response.body", "body": body},
    )


class RateLimitMiddleware:
    """100 requests / rolling 10 s per client IP on /api/v1/*. /audit/* and /health are exempt.

    Only admitted requests are counted, so a client that keeps hammering recovers as soon as its
    oldest admitted request leaves the window.
    """

    def __init__(self, app, settings: Settings):
        self.app = app
        self.limit = settings.rate_limit_requests
        self.window = settings.rate_limit_window_seconds
        self.hits: dict[str, deque[float]] = defaultdict(deque)

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or not scope["path"].startswith(RATE_LIMITED_PREFIX):
            return await self.app(scope, receive, send)
        client = scope.get("client") or ("unknown", 0)
        ip = client[0]
        now = time.monotonic()
        q = self.hits[ip]
        while q and now - q[0] >= self.window:
            q.popleft()
        if len(q) >= self.limit:
            retry_after = max(1, math.ceil(self.window - (now - q[0])))
            start, body = _json_response(
                429, "RATE_LIMITED", "Too many requests. Please slow down.",
                [(b"retry-after", str(retry_after).encode())],
            )
            await send(start)
            await send(body)
            return
        q.append(now)
        return await self.app(scope, receive, send)


class BodyLimitMiddleware:
    """Reject bodies over the cap with 413 before any parsing.

    The declared Content-Length is only a fast path; the body is also counted as it streams, so a
    chunked upload or a lying header cannot bypass the cap. Accepted bodies are replayed to the app.
    """

    def __init__(self, app, settings: Settings):
        self.app = app
        self.limit = settings.body_limit_bytes

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        declared = None
        for k, v in scope.get("headers", []):
            if k == b"content-length":
                try:
                    declared = int(v)
                except ValueError:
                    declared = None
        too_large = declared is not None and declared > self.limit
        chunks: list[bytes] = []
        total = 0
        more = True
        while more:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            chunk = message.get("body", b"")
            total += len(chunk)
            if not too_large and total > self.limit:
                too_large = True
            if too_large:
                chunks.clear()  # stop buffering; keep draining so the client sees the 413
                if total > DRAIN_CAP:
                    break
            else:
                chunks.append(chunk)
            more = message.get("more_body", False)
        if too_large:
            start, body = _json_response(413, "PAYLOAD_TOO_LARGE", "Request body exceeds 1 MB.")
            await send(start)
            await send(body)
            return
        data = b"".join(chunks)
        sent = False

        async def replay():
            nonlocal sent
            if not sent:
                sent = True
                return {"type": "http.request", "body": data, "more_body": False}
            return await receive()

        return await self.app(scope, replay, send)
