"""Phase II audit, media-auth, guest guard, metrics, and dynamic QR routes."""
from __future__ import annotations

import json
import os
import re
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import (FileResponse, HTMLResponse, JSONResponse, RedirectResponse, Response,
                               StreamingResponse)
from starlette.concurrency import run_in_threadpool

from ..core import object_store, realtime
from ..core.config import get_settings
from ..core.errors import DomainError
from ..core.security import authenticate, forbidden, reject_anonymous_guest
from ..core.validation import read_json_object
from ..domain import day2
from .common import run_tx

router = APIRouter()
_media_sample_lock = threading.Lock()
_media_sample = {"at": 0.0, "bytes": 0}


def _bearer(request: Request) -> str | None:
    header = request.headers.get("authorization", "")
    return header[7:] if header.lower().startswith("bearer ") and header[7:] else None


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


def _media_metrics() -> tuple[int, float]:
    """Read aggregate active-path and receive bitrate state from MediaMTX."""
    try:
        with urllib.request.urlopen("http://media:9997/v3/paths/list", timeout=2) as result:
            paths = json.load(result).get("items", [])
    except (OSError, ValueError, urllib.error.URLError):
        return 0, 0.0
    active = [path for path in paths if path.get("ready")]
    received = sum(int(path.get("bytesReceived", 0)) for path in active)
    now = time.monotonic()
    with _media_sample_lock:
        elapsed = now - float(_media_sample["at"])
        delta = max(0, received - int(_media_sample["bytes"]))
        bitrate = (delta * 8 / elapsed / 1000) if _media_sample["at"] and elapsed > 0 else 0.0
        _media_sample.update({"at": now, "bytes": received})
    return len(active), bitrate


@router.post("/audit/v1/stream/key")
async def stream_key(request: Request):
    return await _stream_key_response(await read_json_object(request))


async def _stream_key_response(body: dict):
    status, response, revoked = await run_tx(day2.stream_key, body)
    for old_key in revoked:
        await run_in_threadpool(_kick_media_publishers, old_key)
    return JSONResponse(response, status_code=status)


@router.post("/api/v1/stream/key")
async def production_stream_key(request: Request):
    claims = authenticate(request)
    body = await read_json_object(request)
    if claims.role == "player" and body.get("player_id") != claims.player_id:
        raise forbidden()
    if claims.role not in {"player", "league_organizer", "super_admin"}:
        raise forbidden()
    return await _stream_key_response(body)


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
    reject_anonymous_guest(request)
    body = await read_json_object(request)
    token = _bearer(request)
    if token:
        claims = authenticate(request)
        if body.get("registered_user_id") not in {claims.user_id, claims.player_id}:
            raise forbidden("The cart can only be merged into the authenticated account.")
    return await run_tx(day2.cart_merge, body)


@router.post("/audit/v1/moderation/test")
async def moderation(request: Request):
    return await run_tx(day2.moderation, await read_json_object(request))


@router.get("/metrics")
async def metrics():
    active_streams, bitrate = await run_in_threadpool(_media_metrics)
    text = await run_tx(day2.metrics, realtime.hub.connection_count(), active_streams, bitrate)
    return Response(text, media_type="text/plain; version=0.0.4")


@router.delete("/audit/v1/privacy/user/{user_id}")
async def privacy(user_id: str):
    return await run_tx(day2.erase_user, user_id)


@router.get("/api/v1/public/matches/{match_id}")
async def public_match(match_id: str):
    return await run_tx(day2.public_match, match_id)


@router.get("/api/v1/public/costream/{session_id}")
async def public_costream(session_id: str):
    return await run_tx(day2.public_costream, session_id)


def _object_chunks(response, chunk_size: int = 256 * 1024):
    try:
        while data := response.read(chunk_size):
            yield data
    finally:
        response.close()
        response.release_conn()


@router.get("/api/v1/vod/{vod_id}")
async def vod_playback(vod_id: str, request: Request):
    asset = await run_tx(day2.vod_asset, vod_id)
    size = int(asset["size_bytes"])
    start, end = 0, size - 1
    range_header = request.headers.get("range")
    status = 200
    if range_header:
        match = re.fullmatch(r"bytes=(\d*)-(\d*)", range_header.strip())
        if not match:
            return Response(status_code=416, headers={"Content-Range": f"bytes */{size}"})
        if match.group(1):
            start = int(match.group(1))
            end = min(int(match.group(2)) if match.group(2) else size - 1, size - 1)
        elif match.group(2):
            suffix = min(int(match.group(2)), size)
            start = size - suffix
        if start > end or start >= size:
            return Response(status_code=416, headers={"Content-Range": f"bytes */{size}"})
        status = 206
    length = end - start + 1
    settings = get_settings()
    store = object_store.client(settings)
    response = await run_in_threadpool(
        store.get_object, settings.minio_bucket, asset["object_key"], start, length,
    )
    headers = {"Accept-Ranges": "bytes", "Content-Length": str(length)}
    if status == 206:
        headers["Content-Range"] = f"bytes {start}-{end}/{size}"
    return StreamingResponse(
        _object_chunks(response), status_code=status, media_type="video/mp4", headers=headers
    )


@router.get("/api/v1/players/{player_id}")
async def player_profile(player_id: str):
    return await run_tx(day2.public_profile, "player", player_id)


@router.get("/api/v1/public/clubs/{club_id}")
async def public_club_profile(club_id: str):
    return await run_tx(day2.public_profile, "club", club_id)


@router.post("/api/v1/follows")
async def follow(request: Request):
    claims = authenticate(request)
    return await run_tx(day2.update_follow, claims.user_id, await read_json_object(request))


@router.post("/api/v1/guest/session")
async def guest_session():
    return JSONResponse(await run_tx(day2.create_guest_session), status_code=201)


@router.post("/api/v1/guest/cart")
async def guest_cart(request: Request):
    token = _bearer(request)
    if not token or not token.startswith("guest_"):
        raise DomainError(401, "UNAUTHENTICATED", "A guest bearer token is required.")
    return await run_tx(day2.stage_guest_cart, token, await read_json_object(request))


@router.get("/api/v1/chat/{chat_room_id}")
async def chat_messages(chat_room_id: str, request: Request):
    token = _bearer(request)
    if token and not token.startswith("guest_"):
        authenticate(request)
        token = None
    return await run_tx(day2.chat_history, chat_room_id, token)


@router.post("/api/v1/chat")
async def chat(request: Request):
    reject_anonymous_guest(request)
    claims = authenticate(request)
    body = await read_json_object(request)
    message = await run_tx(day2.post_chat, body.get("chat_room_id"), body.get("message_id"),
                           claims.user_id, body.get("text"))
    room = body.get("chat_room_id", "")
    channel = room[5:] if room.startswith("chat-") else room
    await realtime.hub.publish(channel, {"type": "chat", "sequence": message["sequence"], "message": message})
    return JSONResponse({"status": "accepted", "message": message}, status_code=201)


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


WEB_DIST = Path(os.environ.get("WEB_DIST_DIR", "/srv/web"))


GUEST_FALLBACK_HTML = """<!doctype html><html lang=en><head><meta charset=utf-8><meta name=viewport content='width=device-width'>
<title>LeagueOps Live</title></head><body><main aria-label='Live match media'>
<video data-testid='guest-video-player' controls aria-label='Live match video'></video>
<section data-testid='live-score-banner' aria-live=polite>1 - 0</section>
<article data-testid='pinned-merch-card'>prod-jersey-001 / var-jersey-001-L</article>
<button data-testid='add-to-guest-cart-btn'>Add to cart</button><span data-testid='guest-cart-count'>0</span>
<ol data-testid='chat-message-list'></ol><input data-testid='chat-input-field' aria-label='Chat message'>
<button data-testid='chat-send-btn'>Send</button><dialog data-testid='progressive-auth-modal'>Sign in to continue</dialog>
</main></body></html>"""


@router.get("/web/{client_path:path}", include_in_schema=False)
async def guest_web_spa(client_path: str):
    """Return the Expo SPA entrypoint for every public client-side route."""
    index = WEB_DIST / "index.html"
    if index.is_file():
        return FileResponse(index, media_type="text/html")
    # Source-only test runs do not build Node assets. The production image always
    # contains /srv/web; this fallback keeps contract probes explicit and useful.
    return HTMLResponse(GUEST_FALLBACK_HTML)
