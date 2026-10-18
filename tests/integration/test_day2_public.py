"""Production-facing Day 2 contracts consumed by the merged mobile/web client."""
from __future__ import annotations

import json


def _login(client, email="viewer@nascon.test"):
    response = client.post("/api/v1/auth/login", json={"email": email, "password": "Nascon@26"})
    assert response.status_code == 200, response.text
    return response.json()["token"]


def test_public_match_guest_cart_and_dynamic_qr(client, reset):
    match = client.get("/api/v1/public/matches/match-m1")
    assert match.status_code == 200
    assert match.json()["home"]["score"] == 1
    assert match.json()["pinned_product"]["product_id"] == "prod-jersey-001"

    session = client.post("/api/v1/guest/session", json={})
    assert session.status_code == 201
    guest = session.json()["guest_token"]
    staged = client.post(
        "/api/v1/guest/cart", headers={"Authorization": f"Bearer {guest}"},
        json={"items": [{"variant_id": "var-jersey-001-L", "quantity": 1}]},
    )
    assert staged.status_code == 200 and staged.json()["total_items"] == 1

    before = client.get("/audit/v1/qr/match-m1?inspect=true").json()
    ended = client.post("/audit/v1/events", json={
        "event_id": "day2-public-end", "match_id": "match-m1", "type": "match_end", "payload": {},
    })
    assert ended.status_code == 201
    assert client.post("/audit/v1/events", json={
        "event_id": "day2-public-end", "match_id": "match-m1", "type": "match_end", "payload": {},
    }).status_code == 200
    after = client.get("/audit/v1/qr/match-m1?inspect=true").json()
    assert before["short_url"] == after["short_url"]
    assert after["target_route"] == "/web/matches/match-m1/vod"
    assert before["signature"] != after["signature"]


def test_member_chat_follow_and_identity_bound_merge(client, reset):
    guest = client.post("/api/v1/guest/session", json={}).json()["guest_token"]
    blocked = client.post(
        "/api/v1/chat", headers={"Authorization": f"Bearer {guest}"},
        json={"chat_room_id": "chat-match-m1", "message_id": "guest-message", "text": "hello"},
    )
    assert blocked.status_code == 403
    assert blocked.json()["error"]["code"] == "GUEST_WRITE_FORBIDDEN"

    token = _login(client)
    headers = {"Authorization": f"Bearer {token}"}
    posted = client.post("/api/v1/chat", headers=headers, json={
        "chat_room_id": "chat-match-m1", "message_id": "member-message", "text": "b@d.w0rd",
    })
    assert posted.status_code == 201 and posted.json()["message"]["text"] == "***"
    history = client.get("/api/v1/chat/chat-match-m1", headers=headers)
    assert history.status_code == 200 and history.json()["messages"][0]["message_id"] == "member-message"

    followed = client.post("/api/v1/follows", headers=headers, json={
        "entity_type": "player", "entity_id": "player-alpha-1", "action": "follow",
    })
    assert followed.status_code == 200 and followed.json() == {"following": True, "followers": 1}

    merged = client.post("/audit/v1/guest/cart-merge", headers=headers, json={
        "guest_token": guest, "registered_user_id": "user-viewer",
        "guest_cart": [{"variant_id": "var-jersey-001-L", "quantity": 1}], "test_write_block": True,
    })
    assert merged.status_code == 200 and merged.json()["active_cart"]["total_items"] == 1
    wrong_identity = client.post("/audit/v1/guest/cart-merge", headers=headers, json={
        "guest_token": "guest_anon_tok_7721", "registered_user_id": "player-alpha-1",
        "guest_cart": [{"variant_id": "var-jersey-001-L", "quantity": 1}], "test_write_block": True,
    })
    assert wrong_identity.status_code == 403


def test_guest_websocket_receives_score_without_member_jwt(client, server, reset):
    from websockets.sync.client import connect

    guest = client.post("/api/v1/guest/session", json={}).json()["guest_token"]
    ws_base = server.replace("http://", "ws://")
    with connect(f"{ws_base}/ws/matches/match-m1?token={guest}") as socket:
        assert json.loads(socket.recv(timeout=5)) == {"type": "hello", "match_id": "match-m1"}
        response = client.post("/audit/v1/events", json={
            "event_id": "day2-public-score", "match_id": "match-m1", "type": "score",
            "payload": {"team_id": "club-alpha-2", "event_type": "goal"},
        })
        assert response.status_code == 201
        update = json.loads(socket.recv(timeout=5))
        assert update["type"] == "score" and update["home_score"] == 1 and update["away_score"] == 1
