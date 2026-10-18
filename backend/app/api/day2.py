"""Phase II audit, media-auth, guest guard, metrics, and dynamic QR routes."""
from __future__ import annotations

import json
import urllib.error
import urllib.request

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response
from starlette.concurrency import run_in_threadpool

from ..core import realtime
from ..core.errors import DomainError
from ..core.security import authenticate, forbidden, reject_anonymous_guest
from ..core.validation import read_json_object
from ..domain import day2
from .common import run_tx

router = APIRouter()


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
    return Response(await run_tx(day2.metrics), media_type="text/plain; version=0.0.4")


@router.delete("/audit/v1/privacy/user/{user_id}")
async def privacy(user_id: str):
    return await run_tx(day2.erase_user, user_id)


@router.get("/api/v1/public/matches/{match_id}")
async def public_match(match_id: str):
    return await run_tx(day2.public_match, match_id)


@router.get("/api/v1/public/costream/{session_id}")
async def public_costream(session_id: str):
    return await run_tx(day2.public_costream, session_id)


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
