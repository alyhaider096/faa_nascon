"""Test harness: a real uvicorn server runs in-process (so coverage sees it) against a real
PostgreSQL. Set TEST_DATABASE_URL to point at a throwaway database; the suite resets it freely.

    TEST_DATABASE_URL=postgresql://nascon@127.0.0.1:5432/nascon  pytest
"""
from __future__ import annotations

import os
import socket
import sys
import threading
import time
from pathlib import Path

import httpx
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT))

# Public demo salt for tests only (Appendix A vector). The real team salt is never used in tests.
TEST_SALT = "demo-salt"
os.environ["DAY1_SALT"] = TEST_SALT
os.environ["DAY2_SALT"] = TEST_SALT
os.environ["DATABASE_URL"] = os.environ.get("TEST_DATABASE_URL", "postgresql://nascon@127.0.0.1:5432/nascon")
os.environ.setdefault("REDIS_URL", os.environ.get("TEST_REDIS_URL", "redis://127.0.0.1:6379/0"))


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="session")
def server():
    import uvicorn
    from app.main import app

    port = _free_port()
    cfg = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning", lifespan="on")
    srv = uvicorn.Server(cfg)
    thread = threading.Thread(target=srv.run, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{port}"
    deadline = time.time() + 60
    while time.time() < deadline:
        try:
            if httpx.get(base + "/health", timeout=2).status_code == 200:
                break
        except httpx.HTTPError:
            pass
        time.sleep(0.2)
    else:
        raise RuntimeError("test server did not become healthy")
    yield base
    srv.should_exit = True
    thread.join(timeout=10)


@pytest.fixture(scope="session")
def client(server):
    with httpx.Client(base_url=server, timeout=30) as c:
        yield c


@pytest.fixture()
def reset(client):
    """Reset to the baseline before a test; returns a function to re-reset with options."""
    def _reset(body=None):
        r = client.post("/audit/v1/reset", json=body) if body is not None else client.post("/audit/v1/reset")
        assert r.status_code == 200, r.text
        return r.json()
    _reset()
    return _reset


@pytest.fixture()
def tokens(client, reset):
    r = client.post("/audit/v1/rbac-matrix")
    assert r.status_code == 200
    return r.json()


def auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}
