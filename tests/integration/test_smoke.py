def test_health_and_reset(client, reset):
    assert client.get("/health").json() == {"status": "ok"}
    out = reset()
    assert out["status"] == "reset_complete"


def test_expo_web_preview_cors_preflight(client):
    response = client.options(
        "/api/v1/auth/login",
        headers={
            "Origin": "http://localhost:19006",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "authorization,content-type",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:19006"
    assert "POST" in response.headers["access-control-allow-methods"]
    assert "Authorization" in response.headers["access-control-allow-headers"]
