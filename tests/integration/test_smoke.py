def test_health_and_reset(client, reset):
    assert client.get("/health").json() == {"status": "ok"}
    out = reset()
    assert out["status"] == "reset_complete"
