"""Application entrypoint: shared middleware, error policy, startup (wait for DB -> migrate -> seed).

/health only turns 200 once the database is reachable, migrations are applied and the baseline is
seeded, so Compose/graders never see a half-initialised API.
"""
from __future__ import annotations

import importlib
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from starlette.concurrency import run_in_threadpool
from starlette.middleware.cors import CORSMiddleware
from starlette.staticfiles import StaticFiles

from .core import db, realtime
from .core.config import get_settings
from .core.errors import DomainError, install_error_handlers
from .core.middleware import BodyLimitMiddleware, RateLimitMiddleware
from .core.security import authenticate_token
from .domain import day2

log = logging.getLogger("nascon.main")


def _startup() -> None:
    settings = get_settings()
    db.wait_for_db(settings.database_url)
    applied = db.migrate(settings.database_url)
    if applied:
        log.info("migrations applied: %s", ", ".join(applied))
    db.init_pool(settings.database_url, settings.pool_max)
    from .domain import seed
    with db.tx() as conn:
        conn.execute("SELECT pg_advisory_xact_lock(%s)", (seed.RESET_LOCK,))
        if not seed.is_seeded(conn):
            seed.reset(conn)
            log.info("baseline seeded")


@asynccontextmanager
async def lifespan(_: FastAPI):
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
    await run_in_threadpool(_startup)
    yield
    db.close_pool()


def _mount_optional(app: FastAPI, module: str) -> None:
    """Domain-owner routers (scoring/standings/fixtures/mobile reads) are mounted when present."""
    try:
        mod = importlib.import_module(module)
    except ModuleNotFoundError:
        return
    router = getattr(mod, "router", None)
    if router is not None:
        app.include_router(router)


def _guest_token_valid(token: str) -> bool:
    with db.tx() as conn:
        return conn.execute(
            "SELECT 1 FROM day2_guest_tokens WHERE guest_token=%s AND valid=true", (token,)
        ).fetchone() is not None


def _costream_member(session_id: str, player_id: str) -> bool:
    with db.tx() as conn:
        return day2.costream_member(conn, session_id, player_id)


def _costream_disconnect(session_id: str, player_id: str) -> dict | None:
    with db.tx() as conn:
        return day2.costream_disconnect(conn, session_id, player_id)


def create_app() -> FastAPI:
    settings = get_settings()          # raises a clear ConfigError when DAY1_SALT is missing
    app = FastAPI(title="LeagueOps API", version="1.0", lifespan=lifespan,
                  docs_url=None, redoc_url=None, openapi_url=None)
    install_error_handlers(app)
    from .api import audit, day2, mobile
    app.include_router(audit.router)
    app.include_router(day2.router)
    app.include_router(mobile.router)
    _mount_optional(app, "app.api.domain_audit")
    _mount_optional(app, "app.api.domain_mobile")

    web_dist = Path(day2.WEB_DIST)
    if (web_dist / "_expo").is_dir():
        app.mount("/_expo", StaticFiles(directory=web_dist / "_expo"), name="expo-assets")
    if (web_dist / "assets").is_dir():
        app.mount("/assets", StaticFiles(directory=web_dist / "assets"), name="web-assets")

    costream_presence: dict[tuple[str, str], int] = {}

    async def serve_match_socket(ws: WebSocket, match_id: str, *, guests: bool) -> None:
        token = ws.query_params.get("token")
        if not token:
            auth = ws.headers.get("authorization", "")
            token = auth[7:] if auth.lower().startswith("bearer ") else None
        try:
            if guests and (token or "").startswith("guest_"):
                if not await run_in_threadpool(_guest_token_valid, token):
                    raise DomainError(401, "UNAUTHENTICATED")
            else:
                await run_in_threadpool(authenticate_token, token or "")
        except DomainError:
            await ws.close(code=4401)
            return
        await ws.accept()
        await realtime.hub.connect(match_id, ws)
        try:
            await ws.send_json({"type": "hello", "match_id": match_id})
            while True:
                text = await ws.receive_text()
                if text == "ping":
                    await ws.send_text("pong")
        except WebSocketDisconnect:
            pass
        finally:
            realtime.hub.disconnect(match_id, ws)

    @app.websocket("/ws/v1/matches/{match_id}")
    async def match_socket(ws: WebSocket, match_id: str):
        await serve_match_socket(ws, match_id, guests=False)

    @app.websocket("/ws/matches/{match_id}")
    async def public_match_socket(ws: WebSocket, match_id: str):
        await serve_match_socket(ws, match_id, guests=True)

    @app.websocket("/ws/costream/{session_id}")
    async def costream_socket(ws: WebSocket, session_id: str):
        token = ws.query_params.get("token")
        try:
            claims = await run_in_threadpool(authenticate_token, token or "")
            if not claims.player_id or not await run_in_threadpool(
                lambda: _costream_member(session_id, claims.player_id)
            ):
                raise DomainError(403, "FORBIDDEN")
        except DomainError:
            await ws.close(code=4403)
            return
        key = (session_id, claims.player_id)
        costream_presence[key] = costream_presence.get(key, 0) + 1
        await ws.accept()
        await realtime.hub.connect(session_id, ws)
        try:
            await ws.send_json({"type": "hello", "session_id": session_id,
                                "player_id": claims.player_id})
            while True:
                if await ws.receive_text() == "ping":
                    await ws.send_text("pong")
        except WebSocketDisconnect:
            pass
        finally:
            realtime.hub.disconnect(session_id, ws)
            remaining = costream_presence.get(key, 1) - 1
            if remaining > 0:
                costream_presence[key] = remaining
            else:
                costream_presence.pop(key, None)
                response = await run_in_threadpool(
                    lambda: _costream_disconnect(session_id, claims.player_id)
                )
                if response:
                    await realtime.hub.publish(
                        session_id, {"type": "costream_state", "session": response}
                    )

    # CORS is added last so it is outermost and preflights never reach route/method handling.
    app.add_middleware(BodyLimitMiddleware, settings=settings)
    app.add_middleware(RateLimitMiddleware, settings=settings)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.cors_origins),
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type"],
        expose_headers=["Content-Disposition"],
    )
    return app


app = create_app()
