"""Required three-session Day 2 browser acceptance suite.

Run after the complete Compose stack is healthy:

    curl -fsS -X POST http://127.0.0.1:8080/audit/v1/reset
    RUN_SELENIUM_GRID=1 pytest -n 3 tests/selenium \
      --junitxml=tests/reports/selenium-report.xml
"""
from __future__ import annotations

import os
import time
from uuid import uuid4

import httpx
import pytest

pytest.importorskip("selenium", reason="install backend/requirements-dev.txt for Grid acceptance")

from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait


WEB_BASE_URL = os.getenv("SELENIUM_WEB_BASE_URL", "http://api:8080").rstrip("/")
API_BASE_URL = os.getenv("SELENIUM_API_BASE_URL", "http://127.0.0.1:8080").rstrip("/")


def _visible(driver, test_id: str, timeout: float = 3):
    return WebDriverWait(driver, timeout).until(
        EC.visibility_of_element_located((By.CSS_SELECTOR, f'[data-testid="{test_id}"]'))
    )


def test_qr_resolution_and_zero_friction_load(browser):
    browser.get(f"{WEB_BASE_URL}/q/m1-live")
    WebDriverWait(browser, 3).until(EC.url_contains("/web/matches/match-m1/live"))
    assert _visible(browser, "guest-video-player")
    assert _visible(browser, "live-score-banner")
    assert not browser.find_elements(By.CSS_SELECTOR, '[data-testid="progressive-auth-modal"]')


def test_guest_write_block_opens_progressive_modal(browser):
    browser.get(f"{WEB_BASE_URL}/web/matches/match-m1/live")
    chat = _visible(browser, "chat-message-list")
    before = chat.text
    field = _visible(browser, "chat-input-field")
    field.send_keys(f"guest-blocked-{uuid4().hex}")
    _visible(browser, "chat-send-btn").click()
    assert _visible(browser, "progressive-auth-modal", timeout=3)
    assert chat.text == before


def test_guest_cart_staging_and_realtime_score_sync(browser):
    browser.get(f"{WEB_BASE_URL}/web/matches/match-m1/live")
    count = _visible(browser, "guest-cart-count")
    assert count.text == "0"
    _visible(browser, "add-to-guest-cart-btn").click()
    WebDriverWait(browser, 3).until(lambda _driver: count.text == "1")

    score = _visible(browser, "live-score-banner")
    before = score.text
    started = time.monotonic()
    response = httpx.post(
        f"{API_BASE_URL}/audit/v1/events",
        json={
            "event_id": f"selenium-score-{uuid4().hex}",
            "match_id": "match-m1",
            "type": "score",
            "payload": {"team_id": "club-alpha-2", "event_type": "goal"},
        },
        timeout=3,
    )
    assert response.status_code == 201, response.text
    WebDriverWait(browser, 0.5, poll_frequency=0.02).until(lambda _driver: score.text != before)
    assert time.monotonic() - started < 0.5
