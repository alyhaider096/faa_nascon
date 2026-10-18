"""Table-driven Day 2 contract, persistence, and error-precedence coverage."""
from __future__ import annotations

import io
import json
from uuid import uuid4


def _login(client, email: str) -> str:
    response = client.post("/api/v1/auth/login", json={"email": email, "password": "Nascon@26"})
    assert response.status_code == 200, response.text
    return response.json()["token"]


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_stream_key_lifecycle_media_auth_and_authorization(client, reset, monkeypatch):
    from app.api import day2 as api_day2

    monkeypatch.setattr(api_day2, "_kick_media_publishers", lambda _key: None)
    bad = client.post("/audit/v1/stream/key", json={"action": "bad", "player_id": ""})
    assert bad.status_code == 400 and bad.json()["error"]["code"] == "VALIDATION_ERROR"
    missing = client.post("/audit/v1/stream/key", json={"action": "generate", "player_id": "missing"})
    assert missing.status_code == 404 and missing.json()["error"]["code"] == "PLAYER_NOT_FOUND"

    first_key = "sk_live_1111111111111111"
    first = client.post("/audit/v1/stream/key", json={
        "action": "generate", "player_id": "player-alpha-1", "label": "desk",
        "stream_key_override": first_key,
    })
    assert first.status_code == 201 and first.json()["stream_key"] == first_key
    assert client.post("/internal/media/auth", json={"action": "publish", "path": f"live/{first_key}"}).status_code == 200
    assert client.post("/internal/media/auth", json={"action": "api", "path": ""}).status_code == 200

    second_key = "sk_live_2222222222222222"
    rotated = client.post("/audit/v1/stream/key", json={
        "action": "rotate", "player_id": "player-alpha-1", "stream_key_override": second_key,
    })
    assert rotated.status_code == 200
    assert client.post("/internal/media/auth", json={"action": "publish", "path": f"live/{first_key}"}).status_code == 401

    viewer = _login(client, "viewer@nascon.test")
    assert client.post("/api/v1/stream/key", headers=_auth(viewer), json={
        "action": "generate", "player_id": "player-alpha-1",
    }).status_code == 403
    player = _login(client, "player@nascon.test")
    assert client.post("/api/v1/stream/key", headers=_auth(player), json={
        "action": "generate", "player_id": "player-alpha-2",
    }).status_code == 403

    revoked = client.post("/audit/v1/stream/key", json={"action": "revoke", "player_id": "player-alpha-1"})
    assert revoked.status_code == 200 and revoked.json()["ingest_endpoints"] is None
    assert client.post("/audit/v1/stream/key", json={
        "action": "revoke", "player_id": "player-alpha-1",
    }).status_code == 404


def test_costream_contract_replay_layout_handoff_and_controls(client, reset):
    duplicate = client.post("/audit/v1/costream/session", json={
        "session_id": "bad-duplicate", "host_player_id": "player-alpha-1",
        "participants": ["player-alpha-1", "player-alpha-1"], "layout": "grid_2",
    })
    assert duplicate.status_code == 400
    missing = client.post("/audit/v1/costream/session", json={
        "session_id": "bad-missing", "host_player_id": "missing",
        "participants": ["missing"], "layout": "solo",
    })
    assert missing.status_code == 404
    unsupported = client.post("/audit/v1/costream/session", json={
        "session_id": "bad-layout", "host_player_id": "player-alpha-1",
        "participants": ["player-alpha-1", "player-alpha-2"], "layout": "solo",
    })
    assert unsupported.status_code == 400 and unsupported.json()["error"]["code"] == "UNSUPPORTED_LAYOUT"

    body = {
        "session_id": "cs-contract", "host_player_id": "player-alpha-1",
        "participants": ["player-alpha-1", "player-alpha-2"], "layout": "grid_2",
    }
    created = client.post("/audit/v1/costream/session", json=body)
    assert created.status_code == 201
    assert client.post("/audit/v1/costream/session", json=body).status_code == 200
    player = _auth(_login(client, "player@nascon.test"))
    viewer = _auth(_login(client, "viewer@nascon.test"))
    assert client.post("/api/v1/costream/sessions/cs-contract/actions", headers=viewer,
                       json={"action": "stop"}).status_code == 403
    assert client.post("/api/v1/costream/sessions/cs-contract/actions", headers=player,
                       json={"action": "set_layout", "layout": "solo"}).status_code == 400
    assert client.post("/api/v1/costream/sessions/cs-contract/actions", headers=player,
                       json={"action": "spotlight", "player_id": "player-alpha-2"}).json()["layout"] == "spotlight"
    kicked = client.post("/api/v1/costream/sessions/cs-contract/actions", headers=player,
                         json={"action": "kick", "player_id": "player-alpha-2"})
    assert kicked.status_code == 200 and kicked.json()["participant_count"] == 1
    stopped = client.post("/api/v1/costream/sessions/cs-contract/actions", headers=player,
                          json={"action": "stop"})
    assert stopped.status_code == 200 and stopped.json()["status"] == "terminated"

    handoff = client.post("/audit/v1/costream/session", json={**body, "session_id": "cs-drop",
                                                              "simulate_host_drop": True})
    assert handoff.status_code == 201 and handoff.json()["active_host"] == "player-alpha-2"
    assert client.get("/api/v1/public/costream/missing").status_code == 404


def test_qr_routes_exports_counters_and_errors(client, reset):
    before = client.get("/audit/v1/qr/match-m1?inspect=true").json()
    scanned = client.get("/audit/v1/qr/match-m1", headers={"User-Agent": "Android"}).json()
    assert scanned["scan_count"] == before["scan_count"] + 1
    for fmt, magic in (("svg", b"<"), ("png", b"\x89PNG"), ("pdf", b"%PDF")):
        response = client.get(f"/audit/v1/qr/match-m1/export.{fmt}")
        assert response.status_code == 200 and response.content.startswith(magic)
    assert client.get("/audit/v1/qr/match-m1/export.txt").status_code == 404
    assert client.get("/audit/v1/qr/missing").status_code == 404
    assert client.get("/q/missing", follow_redirects=False).status_code == 404
    redirect = client.get("/q/m1-live", follow_redirects=False)
    assert redirect.status_code == 302 and redirect.headers["location"].endswith("/web/matches/match-m1/live")


def test_guest_cart_merge_validation_atomicity_replay_and_conflict(client, reset):
    assert client.post("/api/v1/guest/cart", json={"items": []}).status_code == 401
    session = client.post("/api/v1/guest/session", json={}).json()["guest_token"]
    headers = _auth(session)
    assert client.post("/api/v1/guest/cart", headers=headers, json={"items": "bad"}).status_code == 400
    assert client.post("/api/v1/guest/cart", headers=headers, json={
        "items": [{"variant_id": "missing", "quantity": 1}],
    }).status_code == 404
    staged = client.post("/api/v1/guest/cart", headers=headers, json={
        "items": [
            {"variant_id": "var-jersey-001-L", "quantity": 1},
            {"variant_id": "var-jersey-001-L", "quantity": 1},
        ],
    })
    assert staged.status_code == 200 and staged.json()["total_items"] == 2

    member = _auth(_login(client, "viewer@nascon.test"))
    body = {"guest_token": session, "registered_user_id": "user-viewer", "guest_cart": [
        {"variant_id": "var-jersey-001-L", "quantity": 1},
        {"variant_id": "var-jersey-001-L", "quantity": 1},
    ], "test_write_block": False}
    merged = client.post("/audit/v1/guest/cart-merge", headers=member, json=body)
    assert merged.status_code == 200 and merged.json()["active_cart"]["total_items"] == 2
    assert merged.json()["write_block_verified"] is False
    assert client.post("/audit/v1/guest/cart-merge", headers=member, json=body).json() == merged.json()
    conflict = client.post("/audit/v1/guest/cart-merge", headers=member, json={
        **body, "guest_cart": [{"variant_id": "var-jersey-001-L", "quantity": 1}],
    })
    assert conflict.status_code == 409 and conflict.json()["error"]["code"] == "GUEST_TOKEN_ALREADY_MERGED"

    other = client.post("/api/v1/guest/session", json={}).json()["guest_token"]
    overstock = client.post("/audit/v1/guest/cart-merge", headers=member, json={
        "guest_token": other, "registered_user_id": "user-viewer",
        "guest_cart": [{"variant_id": "var-jersey-001-M", "quantity": 2}],
        "test_write_block": True,
    })
    assert overstock.status_code == 409 and overstock.json()["error"]["code"] == "OUT_OF_STOCK"


def test_moderation_dlq_chat_profiles_and_metrics(client, reset):
    invalid = client.post("/audit/v1/moderation/test", json={"chat_room_id": "", "incoming_messages": {}})
    assert invalid.status_code == 400
    result = client.post("/audit/v1/moderation/test", json={
        "chat_room_id": "chat-contract", "check_dlq": True, "simulate_failed_notifications": 2,
        "incoming_messages": [
            {"message_id": "clean", "sender": "one", "text": "hello"},
            {"message_id": "masked", "sender": "two", "text": "b@d.w0rd"},
            {"message_id": "flood", "sender": "three", "text": "AAAA"},
        ],
    })
    assert result.status_code == 200
    data = result.json()
    assert data["filtered_messages"][1]["text"] == "***"
    assert data["muted_users"] == ["three"] and data["dlq_status"]["queue_depth"] == 2
    persisted = client.post("/audit/v1/moderation/test", json={
        "chat_room_id": "chat-contract", "check_dlq": True, "incoming_messages": [],
    })
    assert persisted.json()["dlq_status"]["queue_depth"] == 2

    guest = client.post("/api/v1/guest/session", json={}).json()["guest_token"]
    assert client.get("/api/v1/chat/chat-contract", headers=_auth(guest)).status_code == 200
    assert client.get("/api/v1/chat/chat-contract", headers=_auth("bad-member-token")).status_code == 401
    member = _auth(_login(client, "viewer@nascon.test"))
    flood = client.post("/api/v1/chat", headers=member, json={
        "chat_room_id": "chat-contract", "message_id": "direct-flood", "text": "????",
    })
    assert flood.status_code == 429
    assert client.get("/api/v1/players/missing").status_code == 404
    assert client.get("/api/v1/public/clubs/club-alpha-1").status_code == 200
    assert client.post("/api/v1/follows", headers=member, json={
        "entity_type": "club", "entity_id": "club-alpha-1", "action": "unfollow",
    }).status_code == 200

    metrics = client.get("/metrics")
    assert metrics.status_code == 200 and "nascon_dlq_depth 2" in metrics.text
    assert client.delete("/audit/v1/privacy/user/missing").status_code == 404


def test_vod_range_errors_streaming_and_web_fallback(client, reset, monkeypatch):
    from app.api import day2 as api_day2
    from app.core.db import tx

    vod_id = f"vod-{uuid4().hex}"
    payload = b"0123456789"
    with tx() as conn:
        conn.execute(
            "INSERT INTO day2_vod_assets(vod_id,match_id,stream_path,object_key,source_path,size_bytes,etag) "
            "VALUES (%s,'match-m1','live/test',%s,%s,%s,'test-etag')",
            (vod_id, f"vod/{vod_id}.mp4", f"source/{vod_id}.mp4", len(payload)),
        )

    class ObjectResponse(io.BytesIO):
        def release_conn(self):
            return None

    class Store:
        def get_object(self, _bucket, _key, offset, length):
            return ObjectResponse(payload[offset:offset + length])

    monkeypatch.setattr(api_day2.object_store, "client", lambda _settings: Store())
    assert client.get("/api/v1/vod/missing").status_code == 404
    assert client.get(f"/api/v1/vod/{vod_id}", headers={"Range": "wrong"}).status_code == 416
    assert client.get(f"/api/v1/vod/{vod_id}", headers={"Range": "bytes=99-100"}).status_code == 416
    suffix = client.get(f"/api/v1/vod/{vod_id}", headers={"Range": "bytes=-4"})
    assert suffix.status_code == 206 and suffix.content == b"6789"
    whole = client.get(f"/api/v1/vod/{vod_id}")
    assert whole.status_code == 200 and whole.content == payload

    monkeypatch.setattr(api_day2, "WEB_DIST", api_day2.Path("/definitely/missing"))
    fallback = client.get("/web/matches/match-m1/live")
    assert fallback.status_code == 200 and "guest-video-player" in fallback.text

    with tx() as conn:
        conn.execute("DELETE FROM day2_vod_assets WHERE vod_id=%s", (vod_id,))


def test_media_metrics_success_and_failure_paths(monkeypatch):
    from app.api import day2 as api_day2

    class FakeResponse(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            self.close()

    monkeypatch.setattr(api_day2.urllib.request, "urlopen", lambda *_args, **_kwargs: FakeResponse(json.dumps({
        "items": [{"ready": True, "bytesReceived": 1000}, {"ready": False, "bytesReceived": 500}],
    }).encode()))
    api_day2._media_sample.update({"at": 0.0, "bytes": 0})
    assert api_day2._media_metrics() == (1, 0.0)
    monkeypatch.setattr(api_day2.urllib.request, "urlopen", lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError()))
    assert api_day2._media_metrics() == (0, 0.0)
