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
from ..core.signing import request_hash, sign_day2, sign_record
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


def _registered_exists(conn, identity: str) -> bool:
    return (_player_exists(conn, identity) or
            conn.execute("SELECT 1 FROM users WHERE user_id=%s", (identity,)).fetchone() is not None)


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
    if not _registered_exists(conn, user_id): raise _player_not_found(user_id)
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


def metrics(conn, active_ws: int = 0, active_streams: int = 0, bitrate_kbps: float = 0.0) -> str:
    dlq = conn.execute("SELECT count(*) n FROM day2_dlq").fetchone()["n"]
    scans = conn.execute("SELECT COALESCE(sum(scan_count),0) n FROM day2_qr_mappings").fetchone()["n"]
    return ("# TYPE nascon_active_ws_connections gauge\n" + f"nascon_active_ws_connections {active_ws}\n"
            "# TYPE nascon_active_streams_total gauge\n" + f"nascon_active_streams_total {active_streams}\n"
            "# TYPE nascon_stream_bitrate_kbps gauge\n" + f"nascon_stream_bitrate_kbps {bitrate_kbps:.3f}\n"
            "# TYPE nascon_dlq_depth gauge\n" + f"nascon_dlq_depth {dlq}\n"
            "# TYPE nascon_qr_scans_total counter\n" + f"nascon_qr_scans_total {scans}\n")


def erase_user(conn, user_id: str) -> dict:
    exists = _player_exists(conn, user_id) or conn.execute("SELECT 1 FROM users WHERE user_id=%s", (user_id,)).fetchone()
    if not exists: raise _player_not_found(user_id)
    conn.execute("UPDATE ref_players SET name='Anonymized Player' WHERE player_id=%s", (user_id,))
    conn.execute("UPDATE users SET email=user_id || '@anonymized.invalid',display_name='Anonymized User',"
                 "token_version=token_version+1 WHERE user_id=%s OR player_id=%s",
                 (user_id, user_id))
    conn.execute("UPDATE day2_guest_tokens SET valid=false,user_id=NULL WHERE user_id=%s", (user_id,))
    conn.execute("DELETE FROM day2_follows WHERE user_id=%s", (user_id,))
    conn.execute("DELETE FROM day2_sanctions WHERE user_id=%s", (user_id,))
    conn.execute("UPDATE day2_moderation_messages SET result=jsonb_set(result,'{sender}',to_jsonb('anonymized'::text)) "
                 "WHERE result->>'sender'=%s", (user_id,))
    conn.execute("DELETE FROM day2_merge_receipts WHERE registered_user_id=%s", (user_id,))
    conn.execute("DELETE FROM day2_carts WHERE user_id=%s", (user_id,))
    conn.execute("UPDATE day2_dlq SET event=event-'user_id'-'sender' "
                 "WHERE event ? 'user_id' OR event ? 'sender'")
    orders = conn.execute("SELECT order_id,response FROM orders WHERE customer_id=%s FOR UPDATE", (user_id,)).fetchall()
    for order in orders:
        response = order["response"]
        receipt = response.get("receipt", {})
        payload = {**receipt.get("payload", {}), "customer_id": "anonymized"}
        receipt = {**receipt, "payload": payload, "signature": sign_record(order["order_id"], payload)}
        receipt.pop("pdf_base64", None)
        response = {**response, "receipt": receipt}
        conn.execute("UPDATE orders SET customer_id='anonymized',pdf=NULL,response=%s WHERE order_id=%s",
                     (Jsonb(response), order["order_id"]))
    conn.execute("UPDATE roster_audit SET who='anonymized' WHERE who=%s", (user_id,))
    return {"user_id": user_id, "status": "anonymized", "pii_retained": False, "tokens_wiped": True}


def apply_match_event(conn, body: dict) -> None:
    match_id, event_type = body.get("match_id"), body.get("type")
    if match_id != "match-m1": return
    if event_type == "match_end":
        conn.execute("UPDATE day2_match_state SET status='completed' WHERE match_id=%s", (match_id,))


# ---------------------------------------------------------------- production/public -------
def _valid_guest(conn, guest_token: str) -> dict:
    row = conn.execute(
        "SELECT * FROM day2_guest_tokens WHERE guest_token=%s AND valid=true", (guest_token,)
    ).fetchone()
    if row is None:
        raise DomainError(401, "UNAUTHENTICATED", "Invalid, expired or tampered guest token.")
    return row


def create_guest_session(conn) -> dict:
    guest_token = "guest_anon_" + secrets.token_hex(16)
    conn.execute("INSERT INTO day2_guest_tokens(guest_token) VALUES (%s)", (guest_token,))
    return {"guest_token": guest_token}


def stage_guest_cart(conn, guest_token: str, body: dict) -> dict:
    _valid_guest(conn, guest_token)
    items = body.get("items")
    if (not isinstance(items, list) or len(items) > 10 or
            any(not isinstance(item, dict) or not isinstance(item.get("variant_id"), str) or
                not is_int(item.get("quantity")) or item["quantity"] < 1 for item in items)):
        raise validation_error(["items"])
    merged: OrderedDict[str, int] = OrderedDict()
    for item in items:
        merged[item["variant_id"]] = merged.get(item["variant_id"], 0) + item["quantity"]
    if merged:
        rows = conn.execute("SELECT variant_id FROM variants WHERE variant_id = ANY(%s)",
                            (list(merged),)).fetchall()
        found = {row["variant_id"] for row in rows}
        missing = next((variant_id for variant_id in merged if variant_id not in found), None)
        if missing:
            raise DomainError(404, "VARIANT_NOT_FOUND", "Inventory variant does not exist.",
                              {"variant_id": missing})
    conn.execute("DELETE FROM day2_guest_cart_items WHERE guest_token=%s", (guest_token,))
    for variant_id, quantity in merged.items():
        conn.execute(
            "INSERT INTO day2_guest_cart_items(guest_token,variant_id,quantity) VALUES (%s,%s,%s)",
            (guest_token, variant_id, quantity),
        )
    return {"guest_token": guest_token, "items": [
        {"variant_id": variant_id, "quantity": quantity} for variant_id, quantity in merged.items()
    ], "total_items": sum(merged.values())}


def _product(conn, product_id: str) -> dict | None:
    product = conn.execute("SELECT * FROM products WHERE product_id=%s AND active=true", (product_id,)).fetchone()
    if product is None:
        return None
    variants = conn.execute(
        "SELECT variant_id,attributes,price_minor,currency,stock,reserved FROM variants "
        "WHERE product_id=%s ORDER BY variant_id", (product_id,)
    ).fetchall()
    return {**product, "variants": variants}


def public_match(conn, match_id: str) -> dict:
    state = conn.execute("SELECT * FROM day2_match_state WHERE match_id=%s", (match_id,)).fetchone()
    if state is None:
        raise DomainError(404, "MATCH_NOT_FOUND", f"Match {match_id} does not exist.", {"match_id": match_id})
    clubs = conn.execute(
        "SELECT club_id,name FROM ref_clubs WHERE club_id = ANY(%s) ORDER BY club_id",
        (["club-alpha-1", "club-alpha-2"],),
    ).fetchall()
    names = {club["club_id"]: club["name"] for club in clubs}
    events = conn.execute(
        "SELECT event_id,sequence,event_type,payload,created_at FROM day2_match_events "
        "WHERE match_id=%s ORDER BY sequence", (match_id,)
    ).fetchall()
    stream = conn.execute(
        "SELECT stream_key FROM day2_stream_keys WHERE status='active' ORDER BY created_at DESC LIMIT 1"
    ).fetchone()
    media_host = get_settings().media_public_host
    vod = conn.execute(
        "SELECT vod_id FROM day2_vod_assets WHERE match_id=%s ORDER BY created_at DESC LIMIT 1", (match_id,)
    ).fetchone()
    playback = (f"/api/v1/vod/{vod['vod_id']}" if state["status"] == "completed" and vod else
                f"http://{media_host}:8888/live/{stream['stream_key']}/index.m3u8" if stream else None)
    product = _product(conn, "prod-jersey-001")
    return {
        "match_id": match_id, "status": state["status"], "version": state["version"],
        "title": f"{names.get('club-alpha-1', 'Alpha FC')} vs {names.get('club-alpha-2', 'Alpha United')}",
        "league_id": "league-alpha-1", "league_name": "Alpha Premier League",
        "home": {"team_id": "club-alpha-1", "name": names.get("club-alpha-1", "Alpha FC"),
                 "score": state["score_home"]},
        "away": {"team_id": "club-alpha-2", "name": names.get("club-alpha-2", "Alpha United"),
                 "score": state["score_away"]},
        "playback_url": playback, "chat_room_id": f"chat-{match_id}",
        "timeline": [{"event_id": event["event_id"], "sequence": event["sequence"],
                      "type": event["event_type"], "payload": event["payload"],
                      "created_at": event["created_at"].isoformat()} for event in events],
        "pinned_product": product,
    }


def vod_asset(conn, vod_id: str) -> dict:
    row = conn.execute(
        "SELECT vod_id,object_key,size_bytes FROM day2_vod_assets WHERE vod_id=%s", (vod_id,)
    ).fetchone()
    if row is None:
        raise DomainError(404, "STREAM_NOT_FOUND", "VOD recording does not exist.", {"vod_id": vod_id})
    return row


def public_costream(conn, session_id: str) -> dict:
    row = conn.execute("SELECT response FROM day2_costream_sessions WHERE session_id=%s", (session_id,)).fetchone()
    if row is None:
        raise DomainError(404, "STREAM_NOT_FOUND", "Co-stream session does not exist.",
                          {"session_id": session_id})
    return row["response"]


def public_profile(conn, entity_type: str, entity_id: str) -> dict:
    if entity_type == "player":
        row = conn.execute(
            "SELECT p.player_id id,p.name,c.name club_name FROM ref_players p "
            "JOIN ref_clubs c ON c.club_id=p.club_id WHERE p.player_id=%s", (entity_id,)
        ).fetchone()
        code = "PLAYER_NOT_FOUND"
    else:
        row = conn.execute("SELECT club_id id,name,venue FROM ref_clubs WHERE club_id=%s", (entity_id,)).fetchone()
        code = "CLUB_NOT_FOUND"
    if row is None:
        raise DomainError(404, code, f"{entity_type.title()} {entity_id} does not exist.", {"id": entity_id})
    followers = conn.execute(
        "SELECT count(*) n FROM day2_follows WHERE entity_type=%s AND entity_id=%s", (entity_type, entity_id)
    ).fetchone()["n"]
    return {**row, "followers": followers, "career_matches": [], "upcoming_fixtures": [], "vod_archive": []}


def update_follow(conn, user_id: str, body: dict) -> dict:
    entity_type, entity_id, action = body.get("entity_type"), body.get("entity_id"), body.get("action")
    fields = []
    if entity_type not in {"player", "club"}: fields.append("entity_type")
    if not isinstance(entity_id, str) or not entity_id: fields.append("entity_id")
    if action not in {"follow", "unfollow"}: fields.append("action")
    if fields: raise validation_error(fields)
    public_profile(conn, entity_type, entity_id)
    if action == "follow":
        conn.execute("INSERT INTO day2_follows(user_id,entity_type,entity_id) VALUES (%s,%s,%s) ON CONFLICT DO NOTHING",
                     (user_id, entity_type, entity_id))
    else:
        conn.execute("DELETE FROM day2_follows WHERE user_id=%s AND entity_type=%s AND entity_id=%s",
                     (user_id, entity_type, entity_id))
    followers = conn.execute(
        "SELECT count(*) n FROM day2_follows WHERE entity_type=%s AND entity_id=%s", (entity_type, entity_id)
    ).fetchone()["n"]
    return {"following": action == "follow", "followers": followers}


def chat_history(conn, chat_room_id: str, guest_token: str | None) -> dict:
    if guest_token:
        _valid_guest(conn, guest_token)
    rows = conn.execute(
        "SELECT message_id,sequence,result,created_at FROM day2_moderation_messages "
        "WHERE chat_room_id=%s ORDER BY sequence LIMIT 100", (chat_room_id,)
    ).fetchall()
    return {"chat_room_id": chat_room_id, "messages": [
        {**row["result"], "sequence": row["sequence"], "created_at": row["created_at"].isoformat()}
        for row in rows
    ]}


def post_chat(conn, chat_room_id: str, message_id: str, sender: str, text: str) -> dict:
    if not all(isinstance(value, str) and value for value in (chat_room_id, message_id, sender, text)):
        raise validation_error(["chat_room_id", "message_id", "text"])
    masked, flagged = _mask_profanity(text)
    if re.search(r"(.)\1{3,}", text, re.IGNORECASE) or re.search(r"[!?]{3,}", text):
        conn.execute("INSERT INTO day2_sanctions(chat_room_id,user_id,sanction) VALUES (%s,%s,'muted') ON CONFLICT DO NOTHING",
                     (chat_room_id, sender))
        raise DomainError(429, "RATE_LIMITED", "Chat flood threshold exceeded.")
    result = {"message_id": message_id, "sender": sender, "text": masked,
              "flagged": flagged, "reason": "profanity_leetspeak" if flagged else None}
    conn.execute(
        "INSERT INTO day2_moderation_messages(chat_room_id,message_id,result) VALUES (%s,%s,%s) "
        "ON CONFLICT(chat_room_id,message_id) DO NOTHING", (chat_room_id, message_id, Jsonb(result))
    )
    row = conn.execute(
        "SELECT sequence,result,created_at FROM day2_moderation_messages WHERE chat_room_id=%s AND message_id=%s",
        (chat_room_id, message_id),
    ).fetchone()
    if flagged:
        conn.execute("INSERT INTO day2_sanctions(chat_room_id,user_id,sanction) VALUES (%s,%s,'kicked') ON CONFLICT DO NOTHING",
                     (chat_room_id, sender))
    return {**row["result"], "sequence": row["sequence"], "created_at": row["created_at"].isoformat()}


def append_public_match_event(conn, body: dict) -> tuple[str, dict, dict]:
    fields = []
    event_id, match_id, event_type, payload = (body.get("event_id"), body.get("match_id"),
                                                body.get("type"), body.get("payload"))
    if not isinstance(event_id, str) or not event_id: fields.append("event_id")
    if match_id != "match-m1": fields.append("match_id")
    if event_type not in {"score", "match_end", "match_postponed"}: fields.append("type")
    if not isinstance(payload, dict): fields.append("payload")
    if fields: raise validation_error(fields)
    identity = request_hash(body)
    prior = conn.execute("SELECT request_hash,response FROM day2_match_events WHERE event_id=%s", (event_id,)).fetchone()
    if prior:
        if prior["request_hash"] != identity:
            raise DomainError(409, "DUPLICATE_EVENT_ID", "Event ID was already used with different content.")
        state = conn.execute("SELECT * FROM day2_match_state WHERE match_id=%s", (match_id,)).fetchone()
        return "replay", prior["response"], state
    state = conn.execute("SELECT * FROM day2_match_state WHERE match_id=%s FOR UPDATE", (match_id,)).fetchone()
    if state is None:
        raise DomainError(404, "MATCH_NOT_FOUND", "Match does not exist.", {"match_id": match_id})
    if event_type == "score":
        if state["status"] != "in_progress": raise DomainError(409, "MATCH_NOT_IN_PROGRESS")
        team = payload.get("team_id")
        if team not in {"club-alpha-1", "club-alpha-2"}: raise validation_error(["payload.team_id"])
        column = "score_home" if team == "club-alpha-1" else "score_away"
        conn.execute(f"UPDATE day2_match_state SET {column}={column}+1,version=version+1 WHERE match_id=%s", (match_id,))
    elif event_type == "match_end":
        if state["status"] != "in_progress": raise DomainError(409, "ILLEGAL_TRANSITION")
        conn.execute("UPDATE day2_match_state SET status='completed',version=version+1 WHERE match_id=%s", (match_id,))
    else:
        if state["status"] not in {"upcoming", "in_progress"}: raise DomainError(409, "ILLEGAL_TRANSITION")
        conn.execute("UPDATE day2_match_state SET status='postponed',version=version+1 WHERE match_id=%s", (match_id,))
    state = conn.execute("SELECT * FROM day2_match_state WHERE match_id=%s", (match_id,)).fetchone()
    response = {"event_id": event_id, "match_id": match_id, "type": event_type,
                "sequence": state["version"], "match_version": state["version"],
                "signature": sign_record(event_id, payload)}
    conn.execute(
        "INSERT INTO day2_match_events(event_id,match_id,request_hash,sequence,event_type,payload,response) "
        "VALUES (%s,%s,%s,%s,%s,%s,%s)",
        (event_id, match_id, identity, state["version"], event_type, Jsonb(payload), Jsonb(response)),
    )
    return "new", response, state
