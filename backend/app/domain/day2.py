"""Persistent Phase II services and exact audit response contracts."""
from __future__ import annotations

import io
import re
import secrets
from collections import OrderedDict
from typing import Any

import qrcode
import qrcode.image.svg
from psycopg.types.json import Jsonb
from reportlab.graphics.barcode import qr
from reportlab.graphics.shapes import Drawing
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

from ..core.errors import DomainError, validation_error
from ..core.config import get_settings
from ..core.signing import request_hash, sign_day2
from ..core.validation import is_int

STREAM_RE = re.compile(r"^sk_live_[a-f0-9]{16}$")
LAYOUTS = {"solo", "grid_2", "grid_4", "spotlight"}
PROFANITY = ("idiotspam", "badword", "asshole", "bitch", "porn", "scam", "fuck", "shit")
LEET = str.maketrans({"@": "a", "0": "o", "1": "i", "!": "i", "3": "e", "$": "s"})
SEPARATORS = "_.-*\u200b\u200c\u200d\ufeff"


def _player_exists(conn, player_id: str) -> bool:
    return conn.execute("SELECT 1 FROM ref_players WHERE player_id=%s", (player_id,)).fetchone() is not None


def _player_not_found(player_id: str) -> DomainError:
    return DomainError(404, "PLAYER_NOT_FOUND", f"Player {player_id} does not exist.", {"player_id": player_id})


def _stream_response(player_id: str, label: str, stream_key: str, status: str, action: str) -> dict:
    active = status == "active"
    media_host = get_settings().media_public_host
    payload = {"action": action, "player_id": player_id, "status": status, "stream_key": stream_key}
    return {
        "player_id": player_id,
        "label": label,
        "stream_key": stream_key,
        "status": status,
        "ingest_endpoints": {
            "rtmp": f"rtmp://{media_host}:1935/live/{stream_key}",
            "webrtc": f"http://{media_host}:8889/live/{stream_key}/whip",
        } if active else None,
        "playback_url": f"http://{media_host}:8888/live/{stream_key}/index.m3u8" if active else None,
        "signature": sign_day2(stream_key, payload),
    }


def stream_key(conn, body: dict) -> tuple[int, dict, list[str]]:
    fields: list[str] = []
    action = body.get("action")
    player_id = body.get("player_id")
    label = body.get("label", "default")
    override = body.get("stream_key_override")
    if action not in {"generate", "rotate", "revoke"}: fields.append("action")
    if not isinstance(player_id, str) or not player_id: fields.append("player_id")
    if not isinstance(label, str) or not 1 <= len(label) <= 64: fields.append("label")
    if override is not None and (not isinstance(override, str) or not override): fields.append("stream_key_override")
    if fields: raise validation_error(fields)
    if not _player_exists(conn, player_id): raise _player_not_found(player_id)

    current = conn.execute(
        "SELECT * FROM day2_stream_keys WHERE player_id=%s AND status='active' FOR UPDATE", (player_id,)
    ).fetchone()
    if action == "revoke":
        if current is None:
            raise DomainError(404, "STREAM_NOT_FOUND", "No active stream key exists.", {"player_id": player_id})
        conn.execute("UPDATE day2_stream_keys SET status='revoked', revoked_at=now() WHERE stream_key=%s",
                     (current["stream_key"],))
        return (200, _stream_response(player_id, current["label"], current["stream_key"], "revoked", action),
                [current["stream_key"]])

    revoked: list[str] = []
    if current is not None:
        conn.execute("UPDATE day2_stream_keys SET status='revoked', revoked_at=now() WHERE stream_key=%s",
                     (current["stream_key"],))
        revoked.append(current["stream_key"])
    key = override or ("sk_live_" + secrets.token_hex(8))
    conn.execute(
        "INSERT INTO day2_stream_keys(stream_key,player_id,label,status) VALUES (%s,%s,%s,'active')",
        (key, player_id, label),
    )
    return ((201 if action == "generate" else 200), _stream_response(player_id, label, key, "active", action),
            revoked)


def media_authorized(conn, stream_key: str) -> bool:
    return conn.execute("SELECT 1 FROM day2_stream_keys WHERE stream_key=%s AND status='active'",
                        (stream_key,)).fetchone() is not None


def costream(conn, body: dict) -> tuple[int, dict]:
    fields: list[str] = []
    session_id, host = body.get("session_id"), body.get("host_player_id")
    participants = body.get("participants")
    layout = body.get("layout", "grid_4")
    drop = body.get("simulate_host_drop", False)
    if not isinstance(session_id, str) or not session_id: fields.append("session_id")
    if not isinstance(host, str) or not host: fields.append("host_player_id")
    if (not isinstance(participants, list) or not participants or
            any(not isinstance(x, str) or not x for x in participants) or
            len(set(participants)) != len(participants)): fields.append("participants")
    if type(drop) is not bool: fields.append("simulate_host_drop")
    if not isinstance(layout, str) or layout not in LAYOUTS: fields.append("layout")
    if fields: raise validation_error(fields)
    missing = [p for p in [*participants, host] if not _player_exists(conn, p)]
    if missing: raise _player_not_found(missing[0])
    if host not in participants: raise validation_error(["host_player_id"])
    if len(participants) > 4:
        raise DomainError(409, "COSTREAM_SESSION_FULL", "Co-stream sessions support at most four participants.")
    active = [p for p in participants if not (drop and p == host)]
    if (layout == "solo" and len(active) > 1) or (layout == "grid_2" and len(active) > 2):
        raise DomainError(400, "UNSUPPORTED_LAYOUT", "Layout cannot fit the active participant count.",
                          {"layout": layout, "participant_count": len(active)})
    status = "active" if active else "terminated"
    active_host = active[0] if drop and active else (host if not drop else None)
    handoff = bool(drop and active)
    signed = {"active_host": active_host, "handoff_occurred": handoff, "layout": layout,
              "participant_count": len(active), "session_id": session_id, "status": status}
    response = {
        "session_id": session_id, "status": status, "active_host": active_host,
        "handoff_occurred": handoff, "participant_count": len(active),
        "active_participants": active, "layout": layout,
        "composite_playback_url": (f"http://{get_settings().media_public_host}:8888/costream/{session_id}/index.m3u8"
                                   if status == "active" else None),
        "chat_room_id": f"chat-{session_id}", "signature": sign_day2(session_id, signed),
    }
    body_hash = request_hash(body)
    existing = conn.execute("SELECT request_hash,response FROM day2_costream_sessions WHERE session_id=%s FOR UPDATE",
                            (session_id,)).fetchone()
    if existing:
        if existing["request_hash"] == body_hash:
            return 200, existing["response"]
        conn.execute("UPDATE day2_costream_sessions SET request_hash=%s,response=%s,updated_at=now() WHERE session_id=%s",
                     (body_hash, Jsonb(response), session_id))
        return 200, response
    conn.execute("INSERT INTO day2_costream_sessions(session_id,request_hash,response) VALUES (%s,%s,%s)",
                 (session_id, body_hash, Jsonb(response)))
    conn.execute("INSERT INTO day2_qr_mappings(entity_id,entity_type,short_code) VALUES (%s,'costream',%s) ON CONFLICT DO NOTHING",
                 (session_id, session_id))
    return 201, response


def _entity_status(conn, entity_id: str, entity_type: str) -> str:
    if entity_type == "match":
        row = conn.execute("SELECT status FROM day2_match_state WHERE match_id=%s", (entity_id,)).fetchone()
        return row["status"] if row else "upcoming"
    if entity_type == "costream":
        row = conn.execute("SELECT response FROM day2_costream_sessions WHERE session_id=%s", (entity_id,)).fetchone()
        return row["response"].get("status", "active") if row else "active"
    return "active"


def _target(entity_id: str, entity_type: str, status: str) -> str:
    if entity_type == "match":
        if status == "upcoming": return f"/web/matches/{entity_id}/preview"
        if status == "in_progress": return f"/web/matches/{entity_id}/live"
        if status == "completed": return f"/web/matches/{entity_id}/vod"
        return f"/web/matches/{entity_id}/notice?state={status}"
    if entity_type == "player": return f"/web/players/{entity_id}"
    if entity_type == "club": return f"/web/clubs/{entity_id}"
    return f"/web/costream/{entity_id}"


def qr_metadata(conn, entity_id: str, *, inspect: bool, device_family: str = "desktop") -> dict:
    row = conn.execute("SELECT * FROM day2_qr_mappings WHERE entity_id=%s FOR UPDATE", (entity_id,)).fetchone()
    if row is None:
        raise DomainError(404, "QR_NOT_FOUND", "No QR mapping exists for this entity.", {"entity_id": entity_id})
    if not inspect:
        conn.execute("UPDATE day2_qr_mappings SET scan_count=scan_count+1 WHERE entity_id=%s", (entity_id,))
        conn.execute(
            "INSERT INTO day2_qr_scan_buckets(entity_id,device_family,utc_bucket,scans) "
            "VALUES (%s,%s,date_trunc('hour',now()),1) ON CONFLICT(entity_id,device_family,utc_bucket) "
            "DO UPDATE SET scans=day2_qr_scan_buckets.scans+1", (entity_id, device_family))
        row["scan_count"] += 1
    status = _entity_status(conn, entity_id, row["entity_type"])
    short_url = f"{get_settings().public_base_url}/q/{row['short_code']}"
    target = _target(entity_id, row["entity_type"], status)
    signed = {"entity_id": entity_id, "short_url": short_url, "target_route": target}
    base = f"{get_settings().public_base_url}/audit/v1/qr/{entity_id}/export"
    return {"entity_id": entity_id, "entity_type": row["entity_type"], "entity_status": status,
            "short_url": short_url, "target_route": target, "deep_link_uri": f"nascon://entity/{entity_id}",
            "scan_count": row["scan_count"], "export_formats": {"svg": base + ".svg", "png": base + ".png",
            "pdf": base + ".pdf"}, "signature": sign_day2(entity_id, signed)}


def qr_by_short_code(conn, short_code: str) -> str:
    row = conn.execute("SELECT entity_id,entity_type FROM day2_qr_mappings WHERE short_code=%s", (short_code,)).fetchone()
    if row is None: raise DomainError(404, "QR_NOT_FOUND", "Unknown QR short code.", {"short_code": short_code})
    return _target(row["entity_id"], row["entity_type"], _entity_status(conn, row["entity_id"], row["entity_type"]))


def qr_export(conn, entity_id: str, fmt: str) -> tuple[bytes, str]:
    meta = qr_metadata(conn, entity_id, inspect=True)
    if fmt == "svg":
        out = io.BytesIO(); qrcode.make(meta["short_url"], image_factory=qrcode.image.svg.SvgPathImage).save(out)
        return out.getvalue(), "image/svg+xml"
    if fmt == "png":
        out = io.BytesIO(); qrcode.make(meta["short_url"]).save(out, format="PNG")
        return out.getvalue(), "image/png"
    if fmt == "pdf":
        out = io.BytesIO(); pdf = canvas.Canvas(out, pagesize=A4)
        pdf.setFont("Helvetica-Bold", 18); pdf.drawString(72, 780, f"LeagueOps QR - {entity_id}")
        widget = qr.QrCodeWidget(meta["short_url"]); bounds = widget.getBounds()
        drawing = Drawing(260, 260, transform=[260/(bounds[2]-bounds[0]),0,0,260/(bounds[3]-bounds[1]),0,0])
        drawing.add(widget); from reportlab.graphics import renderPDF; renderPDF.draw(drawing, pdf, 160, 460)
        pdf.setFont("Helvetica", 10); pdf.drawString(72, 430, meta["short_url"]); pdf.save()
        return out.getvalue(), "application/pdf"
    raise DomainError(404, "NOT_FOUND", "Unsupported export format.")


def _active_cart(conn, user_id: str) -> dict:
    rows = conn.execute(
        "SELECT i.variant_id,i.quantity,v.price_minor FROM day2_cart_items i JOIN variants v USING(variant_id) "
        "WHERE i.user_id=%s ORDER BY i.variant_id", (user_id,)).fetchall()
    items = [{"variant_id": r["variant_id"], "quantity": r["quantity"], "unit_price_minor": r["price_minor"]}
             for r in rows]
    return {"user_id": user_id, "currency": "PKR", "total_items": sum(i["quantity"] for i in items),
            "subtotal_minor": sum(i["quantity"] * i["unit_price_minor"] for i in items), "items": items}


def cart_merge(conn, body: dict) -> dict:
    fields: list[str] = []
    token, user_id, items = body.get("guest_token"), body.get("registered_user_id"), body.get("guest_cart")
    test_block = body.get("test_write_block", True)
    if not isinstance(token, str) or not token.startswith("guest_") or len(token) <= 6: fields.append("guest_token")
    if not isinstance(user_id, str) or not user_id: fields.append("registered_user_id")
    if not isinstance(items, list) or not 1 <= len(items) <= 10: fields.append("guest_cart")
    elif any(not isinstance(i, dict) or not isinstance(i.get("variant_id"), str) or
             not is_int(i.get("quantity")) or i["quantity"] < 1 for i in items): fields.append("guest_cart")
    if type(test_block) is not bool: fields.append("test_write_block")
    if fields: raise validation_error(fields)
    if not _player_exists(conn, user_id): raise _player_not_found(user_id)
    requested: OrderedDict[str, int] = OrderedDict()
    for item in items: requested[item["variant_id"]] = requested.get(item["variant_id"], 0) + item["quantity"]
    variants = {}
    for variant_id, qty in requested.items():
        row = conn.execute("SELECT * FROM variants WHERE variant_id=%s FOR UPDATE", (variant_id,)).fetchone()
        if row is None:
            raise DomainError(404, "VARIANT_NOT_FOUND", "Inventory variant does not exist.", {"variant_id": variant_id})
        variants[variant_id] = row
    token_row = conn.execute("SELECT * FROM day2_guest_tokens WHERE guest_token=%s FOR UPDATE", (token,)).fetchone()
    if token_row is None:
        raise DomainError(401, "UNAUTHENTICATED", "Invalid, expired or tampered token.")
    identity = request_hash({"registered_user_id": user_id, "guest_cart": items})
    receipt = conn.execute("SELECT * FROM day2_merge_receipts WHERE guest_token=%s", (token,)).fetchone()
    if receipt:
        if receipt["registered_user_id"] == user_id and receipt["request_hash"] == identity:
            return receipt["response"]
        raise DomainError(409, "GUEST_TOKEN_ALREADY_MERGED", "Guest token was already merged with another request.",
                          {"guest_token": token})
    conn.execute("INSERT INTO day2_carts(user_id) VALUES (%s) ON CONFLICT DO NOTHING", (user_id,))
    for variant_id, qty in requested.items():
        prior = conn.execute("SELECT quantity FROM day2_cart_items WHERE user_id=%s AND variant_id=%s FOR UPDATE",
                             (user_id, variant_id)).fetchone()
        merged = qty + (prior["quantity"] if prior else 0)
        available = variants[variant_id]["stock"] - variants[variant_id]["reserved"]
        if qty > available:
            raise DomainError(409, "OUT_OF_STOCK", "Requested quantity exceeds available stock.",
                              {"variant_id": variant_id})
        conn.execute("UPDATE variants SET reserved=reserved+%s WHERE variant_id=%s", (qty, variant_id))
        conn.execute("INSERT INTO day2_cart_items(user_id,variant_id,quantity) VALUES (%s,%s,%s) "
                     "ON CONFLICT(user_id,variant_id) DO UPDATE SET quantity=EXCLUDED.quantity",
                     (user_id, variant_id, merged))
    cart = _active_cart(conn, user_id)
    verified, rejection = (True, 403) if test_block else (False, None)
    signed = {"cart_merged": True, "guest_token": token, "registered_user_id": user_id,
              "total_items": cart["total_items"], "write_rejection_code": rejection}
    response = {"guest_token": token, "write_block_verified": verified, "write_rejection_code": rejection,
                "cart_merged": True, "active_cart": cart, "signature": sign_day2(token, signed)}
    conn.execute("INSERT INTO day2_merge_receipts(guest_token,registered_user_id,request_hash,response) VALUES (%s,%s,%s,%s)",
                 (token, user_id, identity, Jsonb(response)))
    conn.execute("UPDATE day2_guest_tokens SET merged=true,user_id=%s WHERE guest_token=%s", (user_id, token))
    return response


def _normalized_with_map(text: str) -> tuple[str, list[int]]:
    normalized, positions = [], []
    for index, char in enumerate(text):
        mapped = char.lower().translate(LEET)
        if mapped in SEPARATORS or mapped.isspace():
            continue
        normalized.append(mapped); positions.append(index)
    return "".join(normalized), positions


def _mask_profanity(text: str) -> tuple[str, bool]:
    normalized, positions = _normalized_with_map(text)
    spans: list[tuple[int, int]] = []
    for word in PROFANITY:
        start = 0
        while (at := normalized.find(word, start)) >= 0:
            spans.append((positions[at], positions[at + len(word) - 1] + 1)); start = at + len(word)
    if not spans: return text, False
    for left, right in sorted(spans, reverse=True): text = text[:left] + "***" + text[right:]
    return text, True


def moderation(conn, body: dict) -> dict:
    fields: list[str] = []
    room, messages = body.get("chat_room_id"), body.get("incoming_messages")
    check_dlq, failures = body.get("check_dlq"), body.get("simulate_failed_notifications", 0)
    if not isinstance(room, str) or not room: fields.append("chat_room_id")
    if not isinstance(messages, list): fields.append("incoming_messages")
    elif any(not isinstance(m, dict) or any(not isinstance(m.get(k), str) or not m.get(k)
                                            for k in ("message_id", "sender", "text")) for m in messages):
        fields.append("incoming_messages")
    if type(check_dlq) is not bool: fields.append("check_dlq")
    if not is_int(failures) or failures < 0: fields.append("simulate_failed_notifications")
    if fields: raise validation_error(fields)
    filtered, kicked, muted = [], [], []
    flagged_count = 0
    for message in messages:
        text = message["text"]
        flood = re.search(r"(.)\1{3,}", text, re.IGNORECASE) is not None or re.search(r"[!?]{3,}", text) is not None
        masked, flagged = _mask_profanity(text)
        if flagged or flood: flagged_count += 1
        if flood:
            if message["sender"] not in muted: muted.append(message["sender"])
            conn.execute("INSERT INTO day2_sanctions(chat_room_id,user_id,sanction) VALUES (%s,%s,'muted') ON CONFLICT DO NOTHING",
                         (room, message["sender"]))
            continue
        result = {"message_id": message["message_id"], "sender": message["sender"], "text": masked,
                  "flagged": flagged, "reason": "profanity_leetspeak" if flagged else None}
        filtered.append(result)
        conn.execute("INSERT INTO day2_moderation_messages(chat_room_id,message_id,result) VALUES (%s,%s,%s) ON CONFLICT DO NOTHING",
                     (room, message["message_id"], Jsonb(result)))
        if flagged:
            if message["sender"] not in kicked: kicked.append(message["sender"])
            conn.execute("INSERT INTO day2_sanctions(chat_room_id,user_id,sanction) VALUES (%s,%s,'kicked') ON CONFLICT DO NOTHING",
                         (room, message["sender"]))
    for n in range(failures):
        conn.execute("INSERT INTO day2_dlq(event) VALUES (%s)", (Jsonb({"type": "notification_failed", "ordinal": n}),))
    events = conn.execute("SELECT id,event,attempts FROM day2_dlq ORDER BY id").fetchall()
    dlq = {"queue_depth": len(events), "undelivered_events":
           [{"id": e["id"], **e["event"], "attempts": e["attempts"]} for e in events]}
    signed = {"chat_room_id": room, "flagged_count": flagged_count, "kicked_users": kicked,
              "queue_depth": dlq["queue_depth"]}
    return {"chat_room_id": room, "filtered_messages": filtered, "kicked_users": kicked,
            "muted_users": muted, "dlq_status": dlq, "signature": sign_day2(room, signed)}


def metrics(conn) -> str:
    active_streams = conn.execute("SELECT count(*) n FROM day2_stream_keys WHERE status='active'").fetchone()["n"]
    dlq = conn.execute("SELECT count(*) n FROM day2_dlq").fetchone()["n"]
    scans = conn.execute("SELECT COALESCE(sum(scan_count),0) n FROM day2_qr_mappings").fetchone()["n"]
    return ("# TYPE nascon_active_ws_connections gauge\nnascon_active_ws_connections 0\n"
            "# TYPE nascon_active_streams_total gauge\n" + f"nascon_active_streams_total {active_streams}\n"
            "# TYPE nascon_stream_bitrate_kbps gauge\nnascon_stream_bitrate_kbps 0\n"
            "# TYPE nascon_dlq_depth gauge\n" + f"nascon_dlq_depth {dlq}\n"
            "# TYPE nascon_qr_scans_total counter\n" + f"nascon_qr_scans_total {scans}\n")


def erase_user(conn, user_id: str) -> dict:
    exists = _player_exists(conn, user_id) or conn.execute("SELECT 1 FROM users WHERE user_id=%s", (user_id,)).fetchone()
    if not exists: raise _player_not_found(user_id)
    conn.execute("UPDATE ref_players SET name='Anonymized Player' WHERE player_id=%s", (user_id,))
    conn.execute("UPDATE users SET email=user_id || '@anonymized.invalid',display_name='Anonymized User' WHERE user_id=%s OR player_id=%s",
                 (user_id, user_id))
    conn.execute("UPDATE day2_guest_tokens SET valid=false,user_id=NULL WHERE user_id=%s", (user_id,))
    return {"user_id": user_id, "status": "anonymized", "pii_retained": False, "tokens_wiped": True}


def apply_match_event(conn, body: dict) -> None:
    match_id, event_type = body.get("match_id"), body.get("type")
    if match_id != "match-m1": return
    if event_type == "match_end":
        conn.execute("UPDATE day2_match_state SET status='completed' WHERE match_id=%s", (match_id,))
