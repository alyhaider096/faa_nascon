"""RBAC 5-role matrix, tenant isolation, token attacks, error precedence (Section 5.13)."""
import base64
import json
import time

import jwt
import pytest

from tests.conftest import auth

ROLES = ["super_admin", "league_organizer", "club_manager", "player", "viewer"]
A, D = 200, 403

# (label, method, path template using ctx keys, expected status per role in ROLES order)
MATRIX = [
    ("P1 tenants", "POST", "/audit/v1/rbac/tenants", [A, D, D, D, D]),
    ("P2 own league", "POST", "/audit/v1/rbac/leagues/{own_league_id}/fixtures", [A, A, D, D, D]),
    ("P2 other league", "POST", "/audit/v1/rbac/leagues/{other_league_id}/fixtures", [A, D, D, D, D]),
    ("P2 foreign league", "POST", "/audit/v1/rbac/leagues/{foreign_league_id}/fixtures", [A, D, D, D, D]),
    ("P3 own club", "POST", "/audit/v1/rbac/clubs/{own_club_id}/roster", [A, D, A, D, D]),
    ("P3 other club", "POST", "/audit/v1/rbac/clubs/{other_club_id}/roster", [A, D, D, D, D]),
    ("P3 foreign club", "POST", "/audit/v1/rbac/clubs/{foreign_club_id}/roster", [A, D, D, D, D]),
    ("P4 own club", "POST", "/audit/v1/rbac/clubs/{own_club_id}/products", [A, D, A, D, D]),
    ("P4 other club", "POST", "/audit/v1/rbac/clubs/{other_club_id}/products", [A, D, D, D, D]),
    ("P4 foreign club", "POST", "/audit/v1/rbac/clubs/{foreign_club_id}/products", [A, D, D, D, D]),
    ("P5 own player", "PATCH", "/audit/v1/rbac/players/{own_player_id}", [A, D, A, A, D]),
    ("P5 other player", "PATCH", "/audit/v1/rbac/players/{other_player_id}", [A, D, D, D, D]),
    ("P5 foreign player", "PATCH", "/audit/v1/rbac/players/{foreign_player_id}", [A, D, D, D, D]),
    ("P6 own club", "GET", "/audit/v1/rbac/clubs/{own_club_id}", [A, A, A, A, A]),
    ("P6 other club", "GET", "/audit/v1/rbac/clubs/{other_club_id}", [A, A, A, A, A]),
    ("P6 foreign club", "GET", "/audit/v1/rbac/clubs/{foreign_club_id}", [A, D, D, D, D]),
    ("P7 platform config", "GET", "/audit/v1/rbac/platform/config", [A, D, D, D, D]),
]


def call(client, method, path, token=None, headers=None):
    h = dict(headers or {})
    if token is not None:
        h.update(auth(token))
    kwargs = {"json": {}} if method in ("POST", "PATCH") else {}
    return client.request(method, path, headers=h, **kwargs)


def test_matrix_response_shape(tokens):
    assert set(tokens["tokens"]) == set(ROLES)
    ctx = tokens["context"]
    assert ctx["own_league_id"] == "league-alpha-1" and ctx["foreign_player_id"] == "player-beta-1"
    for t in tokens["tokens"].values():
        claims = jwt.decode(t, options={"verify_signature": False})
        assert claims["exp"] - time.time() >= 3600        # valid for at least one hour


@pytest.mark.parametrize("label,method,path,expected", MATRIX, ids=[m[0] for m in MATRIX])
def test_full_matrix(client, tokens, label, method, path, expected):
    ctx = tokens["context"]
    url = path.format(**ctx)
    for role, want in zip(ROLES, expected):
        r = call(client, method, url, tokens["tokens"][role])
        assert r.status_code == want, f"{label} as {role}: {r.status_code} {r.text}"
        if want == 200:
            assert r.json() == {"authorized": True}
        else:
            body = r.json()["error"]
            assert body["code"] == "FORBIDDEN" and isinstance(body["details"], dict)


def test_missing_token_is_401(client, tokens):
    r = client.get("/audit/v1/rbac/platform/config")
    assert r.status_code == 401 and r.json()["error"]["code"] == "UNAUTHENTICATED"
    assert client.post("/audit/v1/rbac/tenants", json={}).status_code == 401


def test_malformed_authorization_headers_are_401(client, tokens):
    for header in ("Bearer", "Basic abc", "token abc", "Bearer a b", "Bearer not.a.jwt"):
        r = client.get("/audit/v1/rbac/platform/config", headers={"Authorization": header})
        assert r.status_code == 401, header


def test_tampered_signature_is_401(client, tokens):
    t = tokens["tokens"]["super_admin"]
    head, body, sig = t.split(".")
    bad_sig = ("A" if sig[0] != "A" else "B") + sig[1:]
    assert call(client, "GET", "/audit/v1/rbac/platform/config", ".".join([head, body, bad_sig])).status_code == 401


def test_tampered_payload_role_escalation_is_401(client, tokens):
    t = tokens["tokens"]["viewer"]
    head, body, sig = t.split(".")
    claims = json.loads(base64.urlsafe_b64decode(body + "=" * (-len(body) % 4)))
    claims["role"] = "super_admin"
    forged = base64.urlsafe_b64encode(json.dumps(claims).encode()).rstrip(b"=").decode()
    r = call(client, "GET", "/audit/v1/rbac/platform/config", f"{head}.{forged}.{sig}")
    assert r.status_code == 401


def test_alg_none_is_401(client, tokens):
    t = tokens["tokens"]["super_admin"]
    _, body, _ = t.split(".")
    head = base64.urlsafe_b64encode(json.dumps({"alg": "none", "typ": "JWT"}).encode()).rstrip(b"=").decode()
    assert call(client, "GET", "/audit/v1/rbac/platform/config", f"{head}.{body}.").status_code == 401


def test_wrong_key_and_wrong_algorithm_are_401(client, tokens):
    claims = {"sub": "x", "role": "super_admin", "iat": int(time.time()), "exp": int(time.time()) + 600}
    for key, alg in (("not-the-key", "HS256"), ("demo-salt", "HS256"), ("demo-salt", "HS512")):
        token = jwt.encode(claims, key.ljust(64, "x"), algorithm=alg)
        assert call(client, "GET", "/audit/v1/rbac/platform/config", token).status_code == 401


def test_expired_token_is_401(client, tokens):
    from app.core.security import issue_token
    expired = issue_token({"user_id": "u", "email": "e", "role": "super_admin"}, ttl=-30)
    assert call(client, "GET", "/audit/v1/rbac/platform/config", expired).status_code == 401


def test_unknown_role_claim_is_401(client, tokens):
    from app.core.security import _jwt_key
    now = int(time.time())
    t = jwt.encode({"sub": "u", "role": "root", "iat": now, "exp": now + 600}, _jwt_key(), algorithm="HS256")
    assert call(client, "GET", "/audit/v1/rbac/platform/config", t).status_code == 401


def test_auth_is_checked_before_resource_existence(client, tokens):
    # unauthenticated probe of a nonexistent id is 401, never 404
    assert client.post("/audit/v1/rbac/leagues/nope/fixtures", json={}).status_code == 401


def test_nonexistent_ids_are_404_for_allowed_roles(client, tokens):
    t = tokens["tokens"]
    assert call(client, "POST", "/audit/v1/rbac/leagues/no-such/fixtures", t["super_admin"]).status_code == 404
    assert call(client, "POST", "/audit/v1/rbac/leagues/no-such/fixtures", t["league_organizer"]).status_code == 404
    assert call(client, "POST", "/audit/v1/rbac/clubs/no-such/roster", t["club_manager"]).status_code == 404
    assert call(client, "PATCH", "/audit/v1/rbac/players/no-such", t["player"]).status_code == 404
    r = call(client, "GET", "/audit/v1/rbac/clubs/no-such", t["viewer"])
    assert r.status_code == 404 and r.json()["error"]["code"] == "CLUB_NOT_FOUND"


def test_role_gate_beats_existence_for_disallowed_roles(client, tokens):
    t = tokens["tokens"]
    # a viewer may never touch league fixtures: 403 even for an id that does not exist
    assert call(client, "POST", "/audit/v1/rbac/leagues/no-such/fixtures", t["viewer"]).status_code == 403


def test_foreign_existing_is_403_not_404(client, tokens):
    t, ctx = tokens["tokens"], tokens["context"]
    r = call(client, "GET", f"/audit/v1/rbac/clubs/{ctx['foreign_club_id']}", t["viewer"])
    assert r.status_code == 403


def test_probe_bodies_are_ignored(client, tokens):
    t = tokens["tokens"]["super_admin"]
    h = auth(t)
    ok = client.post("/audit/v1/rbac/tenants", content=b"{not json at all", headers=h)
    assert ok.status_code == 200 and ok.json() == {"authorized": True}
    ok = client.patch("/audit/v1/rbac/players/player-alpha-1", content=b"[1,2,3]", headers=h)
    assert ok.status_code == 200


def test_probes_do_not_mutate(client, tokens):
    before = client.get("/audit/v1/inventory/var-jersey-001-M").json()
    call(client, "POST", "/audit/v1/rbac/clubs/club-alpha-1/products", tokens["tokens"]["club_manager"])
    assert client.get("/audit/v1/inventory/var-jersey-001-M").json() == before


# ------------------------------------------------------------------------- input safety -----
def test_malformed_json_is_400_not_422_or_5xx(client, reset):
    for path in ("/audit/v1/checkout", "/audit/v1/roster/setup", "/audit/v1/roster/transfer",
                 "/audit/v1/offline-sync"):
        r = client.post(path, content=b"{broken", headers={"content-type": "application/json"})
        assert r.status_code == 400, path
        err = r.json()["error"]
        assert err["code"] == "VALIDATION_ERROR" and isinstance(err["details"], dict)
        assert client.post(path, content=b"[1]", headers={"content-type": "application/json"}).status_code == 400
        assert client.post(path, content=b"", headers={"content-type": "application/json"}).status_code == 400


def test_nonfinite_numbers_rejected(client, reset):
    r = client.post("/audit/v1/reset", content=b'{"seed": NaN}', headers={"content-type": "application/json"})
    assert r.status_code == 400


def test_injection_strings_never_5xx_and_are_plain_data(client, reset):
    evil = "x'; DROP TABLE sports;--"
    r = client.post("/audit/v1/checkout", json={
        "order_id": "ord-inj", "customer_id": "<script>alert('x')</script>\"'",
        "items": [{"variant_id": "var-jersey-001-L", "quantity": 1}], "discount_code": None,
        "payment": {"token": "tok_success"}})
    assert r.status_code == 201
    assert r.json()["receipt"]["payload"]["customer_id"] == "<script>alert('x')</script>\"'"
    bad = client.post("/audit/v1/checkout", json={
        "order_id": evil, "customer_id": "c", "items": [{"variant_id": evil, "quantity": 1}],
        "discount_code": evil, "payment": {"token": evil}})
    assert bad.status_code == 400 and bad.json()["error"]["details"]["fields"]
    assert client.get("/audit/v1/inventory/" + evil).status_code == 404
    assert client.get("/audit/v1/roster/history/" + evil).status_code == 404
    # database still alive after "DROP TABLE"
    assert client.get("/health").status_code == 200
    r2 = client.post("/audit/v1/roster/transfer", json={"request_id": evil})
    assert r2.status_code == 400


def test_reset_body_validation(client, reset):
    for body in ({"seed": True}, {"seed": "42"}, {"seed": 1.5}, {"stock": []}, {"stock": {"var-jersey-001-M": -1}},
                 {"stock": {"var-jersey-001-M": "1"}}, {"stock": {"var-jersey-001-M": True}}):
        r = client.post("/audit/v1/reset", json=body)
        assert r.status_code == 400, body
        assert r.json()["error"]["code"] == "VALIDATION_ERROR"
    assert client.post("/audit/v1/reset", json={"seed": 7}).json()["seed"] == 7
    assert client.post("/audit/v1/reset").json()["seed"] == 42


def test_unknown_route_and_method_use_error_shape(client, reset):
    r = client.get("/audit/v1/does-not-exist")
    assert r.status_code == 404 and r.json()["error"]["code"] == "NOT_FOUND"
    r = client.delete("/audit/v1/reset")
    assert r.status_code == 405 and r.json()["error"]["code"] == "METHOD_NOT_ALLOWED"


# ---------------------------------------------------------------------------- body cap -----
def test_body_over_1mb_is_413(client, reset):
    big = b'{"order_id":"x","pad":"' + b"a" * (1024 * 1024 + 10) + b'"}'
    r = client.post("/audit/v1/checkout", content=big, headers={"content-type": "application/json"})
    assert r.status_code == 413 and r.json()["error"]["code"] == "PAYLOAD_TOO_LARGE"
    for path in ("/audit/v1/roster/setup", "/audit/v1/offline-sync", "/audit/v1/reset"):
        assert client.post(path, content=big, headers={"content-type": "application/json"}).status_code == 413


def test_chunked_body_over_1mb_is_413(client, reset):
    def gen():
        for _ in range(130):
            yield b"a" * 10_000          # 1.3 MB with no Content-Length header (chunked)
    r = client.post("/audit/v1/checkout", content=gen(), headers={"content-type": "application/json"})
    assert r.status_code == 413


def test_body_just_under_limit_is_parsed_normally(client, reset):
    body = b'{"order_id":"ord-1","pad":"' + b"a" * (1024 * 1024 - 200) + b'"}'
    r = client.post("/audit/v1/checkout", content=body, headers={"content-type": "application/json"})
    assert r.status_code == 400 and r.json()["error"]["code"] == "VALIDATION_ERROR"


def test_health_and_audit_are_exempt_from_rate_limit(client, reset):
    for _ in range(250):
        assert client.get("/health").status_code == 200
