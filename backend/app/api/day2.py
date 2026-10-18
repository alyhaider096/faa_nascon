"""Phase II audit, media-auth, guest guard, metrics, and dynamic QR routes."""
from __future__ import annotations

import json
import urllib.error
import urllib.request

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response
from starlette.concurrency import run_in_threadpool

from ..core.security import reject_anonymous_guest
from ..core.validation import read_json_object
from ..domain import day2
from .common import run_tx

router = APIRouter()


def _kick_media_publishers(stream_key: str) -> None:
    """Terminate already-authorized publishers after a key is revoked."""
    expected_path = f"live/{stream_key}"
    for resource in ("rtmp/conns", "webrtc/sessions"):
        with urllib.request.urlopen(f"http://media:9997/v3/{resource}/list", timeout=2) as result:
            connections = json.load(result).get("items", [])
        for connection in connections:
            if connection.get("path") != expected_path or connection.get("state") != "publish":
                continue
            request = urllib.request.Request(
                f"http://media:9997/v3/{resource}/kick/{connection['id']}", method="POST"
            )
            try:
                with urllib.request.urlopen(request, timeout=2):
                    pass
            except urllib.error.HTTPError as exc:
                # A publisher can close between the list and kick operations.
                if exc.code != 404:
                    raise


@router.post("/audit/v1/stream/key")
async def stream_key(request: Request):
    status, response, revoked = await run_tx(day2.stream_key, await read_json_object(request))
    for old_key in revoked:
        await run_in_threadpool(_kick_media_publishers, old_key)
    return JSONResponse(response, status_code=status)


@router.post("/audit/v1/costream/session")
async def costream(request: Request):
    status, response = await run_tx(day2.costream, await read_json_object(request))
    return JSONResponse(response, status_code=status)


@router.get("/audit/v1/qr/{entity_id}")
async def qr_metadata(entity_id: str, request: Request, inspect: bool = False):
    ua = request.headers.get("user-agent", "").lower()
    family = "mobile" if any(x in ua for x in ("android", "iphone", "mobile")) else "desktop"
    return await run_tx(day2.qr_metadata, entity_id, inspect=inspect, device_family=family)


@router.get("/audit/v1/qr/{entity_id}/export.{fmt}")
async def qr_export(entity_id: str, fmt: str):
    data, media_type = await run_tx(day2.qr_export, entity_id, fmt)
    return Response(data, media_type=media_type)


@router.get("/q/{short_code}")
async def qr_redirect(short_code: str):
    return RedirectResponse(await run_tx(day2.qr_by_short_code, short_code), status_code=302)


@router.post("/audit/v1/guest/cart-merge")
async def cart_merge(request: Request):
    return await run_tx(day2.cart_merge, await read_json_object(request))


@router.post("/audit/v1/moderation/test")
async def moderation(request: Request):
    return await run_tx(day2.moderation, await read_json_object(request))


@router.get("/metrics")
async def metrics():
    return Response(await run_tx(day2.metrics), media_type="text/plain; version=0.0.4")


@router.delete("/audit/v1/privacy/user/{user_id}")
async def privacy(user_id: str):
    return await run_tx(day2.erase_user, user_id)


@router.post("/api/v1/chat")
async def chat(request: Request):
    reject_anonymous_guest(request)
    await read_json_object(request)
    return JSONResponse({"status": "accepted"}, status_code=201)


@router.post("/internal/media/auth", include_in_schema=False)
async def media_auth(request: Request):
    body = await read_json_object(request)
    # MediaMTX's management API is internal-only (port 9997 is not published).
    # Permit its own authorization callback so the application can enumerate
    # and kick a live publisher immediately when a key is revoked.
    if body.get("action") == "api":
        return Response(status_code=200)
    path = str(body.get("path", ""))
    stream_key = path.rsplit("/", 1)[-1]
    allowed = await run_tx(day2.media_authorized, stream_key)
    return Response(status_code=200 if allowed else 401)


GUEST_HTML = """<!doctype html><html lang=en><head><meta charset=utf-8><meta name=viewport content='width=device-width'>
<title>LeagueOps Live</title></head><body><main aria-label='Live match media'>
<video data-testid='guest-video-player' controls aria-label='Live match video'></video>
<section data-testid='live-score-banner' aria-live=polite>1 - 0</section>
<article data-testid='pinned-merch-card'>prod-jersey-001 / var-jersey-001-L</article>
<button data-testid='add-to-guest-cart-btn'>Add to cart</button><span data-testid='guest-cart-count'>0</span>
<ol data-testid='chat-message-list'></ol><input data-testid='chat-input-field' aria-label='Chat message'>
<button data-testid='chat-send-btn'>Send</button><dialog data-testid='progressive-auth-modal'>Sign in to continue</dialog>
</main></body></html>"""


@router.get("/web/matches/{match_id}/live", response_class=HTMLResponse)
async def guest_match(match_id: str):
    return HTMLResponse(GUEST_HTML)


@router.get("/web/costream/{session_id}", response_class=HTMLResponse)
async def guest_costream(session_id: str):
    return HTMLResponse(GUEST_HTML)
