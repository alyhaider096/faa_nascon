"""Reset repeatability (5.5), authenticated mobile API, realtime pin, outbox -> Redis relay."""
import json
import os

import httpx
import psycopg
import pytest
import redis
from psycopg.rows import dict_row

from tests.conftest import auth
from tests.roster.test_roster import scenario, req as roster_req

PASSWORD = "Nascon@26"
M = "var-jersey-001-M"


def login(client, email, password=PASSWORD):
    return client.post("/api/v1/auth/login", json={"email": email, "password": password})


def token(client, email):
    r = login(client, email)
    assert r.status_code == 200, r.text
    return r.json()["token"]


def snapshot(client):
    return {"inv": [client.get(f"/audit/v1/inventory/var-jersey-001-{s}").json() for s in "ML"],
            "health": client.get("/health").status_code,
            "matrix_keys": sorted(client.post("/audit/v1/rbac-matrix").json())}


# ------------------------------------------------------------------------------- reset -------
def test_reset_twice_same_public_state(client, reset):
    first = reset({"seed": 7})
    s1 = snapshot(client)
    client.post("/audit/v1/checkout", json={"order_id": "o-x", "customer_id": "c", "items": [{"variant_id": M, "quantity": 1}],
                                            "payment": {"token": "tok_success"}})
    client.post("/audit/v1/roster/setup", json=scenario())
    second = reset({"seed": 7})
    assert first == second
    assert snapshot(client) == s1
    assert client.get("/audit/v1/roster/history/p1").status_code == 404      # roster wiped
    assert client.get("/audit/v1/inventory/" + M).json()["stock"] == 1


def test_reset_clears_orders_so_order_id_is_reusable(client, reset):
    b = {"order_id": "o-re", "customer_id": "c", "items": [{"variant_id": M, "quantity": 1}],
         "payment": {"token": "tok_success"}}
    assert client.post("/audit/v1/checkout", json=b).status_code == 201
    reset()
    assert client.post("/audit/v1/checkout", json=b).status_code == 201


@pytest.mark.parametrize("body", [{"seed": "x"}, {"seed": True}, {"stock": []}, {"stock": {M: -1}}, {"stock": {M: 1.5}}])
def test_reset_validation_is_400(client, reset, body):
    assert client.post("/audit/v1/reset", json=body).status_code == 400


def test_reset_stock_override_applies(client, reset):
    reset({"stock": {M: 9}})
    assert client.get("/audit/v1/inventory/" + M).json()["stock"] == 9


# ------------------------------------------------------------------------------- mobile ------
def test_login_success_and_wrong_password(client, reset):
    r = login(client, "manager@nascon.test")
    assert r.status_code == 200
    b = r.json()
    assert b["token_type"] == "Bearer" and b["user"]["role"] == "club_manager"
    assert b["user"]["club_id"] == "club-alpha-1" and "password" not in json.dumps(b)
    bad = login(client, "manager@nascon.test", "nope")
    assert bad.status_code == 401 and bad.json()["error"]["code"] == "UNAUTHENTICATED"
    assert login(client, "ghost@nascon.test").status_code == 401


@pytest.mark.parametrize("body", [{}, {"email": "a"}, {"password": "p"}, {"email": 1, "password": "p"}, {"email": "", "password": ""}])
def test_login_validation_400(client, body):
    assert client.post("/api/v1/auth/login", json=body).status_code == 400


def test_endpoints_require_token(client, reset):
    for path in ("/api/v1/me", "/api/v1/bootstrap", "/api/v1/products", "/api/v1/clubs/club-alpha-1"):
        assert client.get(path).status_code == 401
    assert client.get("/api/v1/me", headers={"Authorization": "Bearer junk"}).status_code == 401


def test_me_and_bootstrap(client, reset):
    h = auth(token(client, "viewer@nascon.test"))
    me = client.get("/api/v1/me", headers=h).json()
    assert me["user"]["email"] == "viewer@nascon.test" and me["tenant"]["tenant_id"] == "tenant-alpha"
    bs = client.get("/api/v1/bootstrap", headers=h).json()
    assert bs["capabilities"] == {"can_score": False, "can_manage_roster": False, "can_buy": True}
    assert all(l["tenant_id"] == "tenant-alpha" for l in bs["leagues"])
    assert [p["product_id"] for p in bs["products"]] == ["prod-jersey-001"]
    adm = client.get("/api/v1/bootstrap", headers=auth(token(client, "admin@nascon.test"))).json()
    assert len(adm["leagues"]) >= len(bs["leagues"]) and adm["capabilities"]["can_score"]


def test_club_profile_scope_and_404(client, reset):
    h = auth(token(client, "viewer@nascon.test"))
    ok = client.get("/api/v1/clubs/club-alpha-1", headers=h)
    assert ok.status_code == 200 and "roster" in ok.json()
    assert client.get("/api/v1/clubs/nope", headers=h).status_code == 404


def test_mobile_checkout_order_flow_and_status_rbac(client, reset):
    v = auth(token(client, "viewer@nascon.test"))
    r = client.post("/api/v1/checkout", headers=v, json={
        "order_id": "mo-1", "items": [{"variant_id": M, "quantity": 1}], "payment": {"token": "tok_success"}})
    assert r.status_code == 201, r.text
    assert client.get("/api/v1/orders/mo-1", headers=v).json()["order_id"] == "mo-1"
    # another customer (player) in the same tenant cannot read it
    p = auth(token(client, "player@nascon.test"))
    assert client.get("/api/v1/orders/mo-1", headers=p).status_code == 403
    assert client.get("/api/v1/orders/ghost", headers=v).status_code == 404
    # viewer may not change status; club manager may
    assert client.post("/api/v1/orders/mo-1/status", headers=v, json={"status": "shipped"}).status_code == 403
    m = auth(token(client, "manager@nascon.test"))
    assert client.post("/api/v1/orders/mo-1/status", headers=m, json={"status": "bogus"}).status_code in (400, 409)
    assert client.post("/api/v1/orders/mo-1/status", headers=m, json={}).status_code == 400


def test_mobile_checkout_out_of_stock_409_and_products_listed(client, reset):
    v = auth(token(client, "viewer@nascon.test"))
    b = lambda oid: {"order_id": oid, "items": [{"variant_id": M, "quantity": 1}], "payment": {"token": "tok_success"}}
    assert client.post("/api/v1/checkout", headers=v, json=b("a")).status_code == 201
    r = client.post("/api/v1/checkout", headers=v, json=b("b"))
    assert r.status_code == 409 and r.json()["error"]["code"] == "OUT_OF_STOCK"
    prods = client.get("/api/v1/products", headers=v).json()["products"]
    assert prods and prods[0]["product_id"] == "prod-jersey-001"


def test_mobile_roster_transfer_scope(client, reset):
    client.post("/audit/v1/roster/setup", json=scenario())
    viewer = auth(token(client, "viewer@nascon.test"))
    assert client.post("/api/v1/roster/transfer", headers=viewer, json=roster_req(rid="m-t1")).status_code == 403
    assert client.post("/api/v1/roster/transfer", json=roster_req(rid="m-t1")).status_code == 401
    admin = auth(token(client, "admin@nascon.test"))
    r = client.post("/api/v1/roster/transfer", headers=admin, json=roster_req(rid="m-t2"))
    assert r.status_code in (200, 201), r.text
    assert client.get("/api/v1/roster/history/p2", headers=admin).status_code == 200


def test_mobile_offline_sync_requires_auth(client, reset):
    assert client.post("/api/v1/offline-sync", json={"device_id": "d", "actions": []}).status_code == 401


# --------------------------------------------------------------------------- pin + realtime --
def test_pin_authorization_and_pinned_readback(client, reset):
    v = auth(token(client, "viewer@nascon.test"))
    assert client.post("/api/v1/matches/mx/pin", headers=v, json={"product_id": "prod-jersey-001"}).status_code == 403
    m = auth(token(client, "manager@nascon.test"))
    assert client.post("/api/v1/matches/mx/pin", headers=m, json={}).status_code == 400
    assert client.post("/api/v1/matches/mx/pin", headers=m, json={"product_id": "nope"}).status_code == 404
    assert client.post("/api/v1/matches/mx/pin", headers=m, json={"product_id": "prod-jersey-001"}).status_code == 200
    got = client.get("/api/v1/matches/mx/pinned", headers=v).json()
    assert got["product"]["product_id"] == "prod-jersey-001"
    assert client.get("/api/v1/matches/other/pinned", headers=v).json()["product"] is None


def test_websocket_receives_pin_event_and_rejects_bad_token(client, server, reset):
    from websockets.sync.client import connect
    ws_base = server.replace("http://", "ws://")
    m = token(client, "manager@nascon.test")
    with connect(f"{ws_base}/ws/v1/matches/mw?token={m}") as ws:
        assert json.loads(ws.recv(timeout=5))["type"] == "hello"
        client.post("/api/v1/matches/mw/pin", headers=auth(m), json={"product_id": "prod-jersey-001"})
        msg = json.loads(ws.recv(timeout=5))
        assert msg["type"] == "product_pinned" and msg["product_id"] == "prod-jersey-001"
        ws.send("ping")
        assert ws.recv(timeout=5) == "pong"
    with pytest.raises(Exception):
        with connect(f"{ws_base}/ws/v1/matches/mw?token=bad") as ws:
            ws.recv(timeout=5)


# ------------------------------------------------------------------------------- outbox ------
def test_worker_relays_outbox_to_redis_stream(client, reset):
    from app import worker
    from app.core import queue
    r = redis.Redis.from_url(os.environ["REDIS_URL"], decode_responses=True)
    r.delete(queue.STREAM)
    client.post("/audit/v1/checkout", json={"order_id": "ob-1", "customer_id": "c",
                                            "items": [{"variant_id": M, "quantity": 1}],
                                            "payment": {"token": "tok_success"}})
    with psycopg.connect(os.environ["DATABASE_URL"], row_factory=dict_row, autocommit=True) as conn:
        pending = conn.execute("SELECT count(*) AS n FROM outbox WHERE published_at IS NULL").fetchone()["n"]
        assert pending >= 1
        assert worker.relay_once(conn, r) == pending
        assert worker.relay_once(conn, r) == 0                                   # nothing left, no dupes
        assert conn.execute("SELECT count(*) AS n FROM outbox WHERE published_at IS NULL").fetchone()["n"] == 0
    entries = r.xrange(queue.STREAM)
    assert len(entries) == pending
    assert any(json.loads(e[1]["payload"]).get("order_id") == "ob-1" for e in entries)
