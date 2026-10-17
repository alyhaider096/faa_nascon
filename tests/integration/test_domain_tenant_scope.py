"""Tenant-isolation regressions for authenticated domain read routes."""


def _token(client, email: str) -> str:
    response = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "Nascon@26"},
    )
    assert response.status_code == 200, response.text
    return response.json()["token"]


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_foreign_tenant_match_detail_is_forbidden(client, reset):
    response = client.post(
        "/audit/v1/leagues",
        json={
            "league_id": "league-beta-1",
            "sport_id": "football",
            "teams": ["beta-a", "beta-b"],
            "fixtures": [
                {"match_id": "match-beta-private", "home": "beta-a", "away": "beta-b"}
            ],
            "qualification": {"spots": 1},
        },
    )
    assert response.status_code == 201, response.text

    viewer = _token(client, "viewer@nascon.test")
    admin = _token(client, "admin@nascon.test")

    standings = client.get(
        "/api/v1/leagues/league-beta-1/standings",
        headers=_auth(viewer),
    )
    assert standings.status_code == 403
    assert standings.json()["error"]["code"] == "FORBIDDEN"

    match = client.get(
        "/api/v1/matches/match-beta-private",
        headers=_auth(viewer),
    )
    assert match.status_code == 403
    assert match.json()["error"]["code"] == "FORBIDDEN"

    # Platform super-admin remains explicitly cross-tenant.
    allowed = client.get(
        "/api/v1/matches/match-beta-private",
        headers=_auth(admin),
    )
    assert allowed.status_code == 200
