"""Rolling 100 requests / 10 s per IP on /api/v1/* only. Runs last in the rbac group."""
import time


def test_rate_limit_429_retry_after_exemptions_and_recovery(client, reset):
    time.sleep(10.5)                      # let any earlier /api/v1 traffic leave the window
    codes = []
    first = client.get("/api/v1/ping")
    assert first.status_code == 200 and first.json() == {"pong": True}
    codes.append(first.status_code)
    t0 = time.time()
    last_429 = None
    for _ in range(149):
        r = client.get("/api/v1/ping")
        codes.append(r.status_code)
        if r.status_code == 429:
            last_429 = r
    assert time.time() - t0 < 5, "burst must land inside the 5 s window"
    assert codes.count(429) >= 40
    assert codes.count(200) == 100          # exactly the allowance
    assert last_429.headers["retry-after"].isdigit() and int(last_429.headers["retry-after"]) >= 1
    assert last_429.json()["error"]["code"] == "RATE_LIMITED"
    # exempt routes keep working while /api/v1 is throttled
    assert client.get("/health").status_code == 200
    assert client.get("/audit/v1/inventory/var-jersey-001-M").status_code == 200
    assert client.post("/audit/v1/reset").status_code == 200
    time.sleep(11)
    assert client.get("/api/v1/ping").status_code == 200
