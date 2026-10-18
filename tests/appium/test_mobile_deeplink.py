"""Physical-device Appium checks required by the Day 2 handbook.

These tests intentionally skip unless RUN_APPIUM_DEVICE=1 is supplied. A skipped
result is not acceptance evidence; the final device run must save appium-report.xml.
"""
from __future__ import annotations

import os
import time
from pathlib import Path
from urllib.request import urlopen

import pytest


APPIUM_URL = os.getenv("APPIUM_URL", "http://127.0.0.1:4723")
APP_PACKAGE = os.getenv("ANDROID_APP_PACKAGE", "com.faa.leagueops")
APK_PATH = Path(os.getenv("ANDROID_APK_PATH", "mobile/release/app-release.apk")).resolve()


def _appium_ready() -> bool:
    try:
        with urlopen(f"{APPIUM_URL}/status", timeout=2) as response:
            return response.status == 200
    except OSError:
        return False


@pytest.fixture(scope="module")
def mobile_driver():
    if os.getenv("RUN_APPIUM_DEVICE") != "1":
        pytest.skip("set RUN_APPIUM_DEVICE=1 with an authorized device for physical acceptance")
    if not APK_PATH.is_file():
        pytest.fail(f"rebuilt APK is missing: {APK_PATH}")
    if not _appium_ready():
        pytest.fail(f"Appium is not ready at {APPIUM_URL}")

    from appium import webdriver
    from appium.options.android import UiAutomator2Options

    options = UiAutomator2Options().load_capabilities({
        "platformName": "Android",
        "appium:automationName": "UiAutomator2",
        "appium:app": str(APK_PATH),
        "appium:appPackage": APP_PACKAGE,
        "appium:autoGrantPermissions": True,
        "appium:newCommandTimeout": 120,
    })
    if serial := os.getenv("ANDROID_DEVICE_UDID"):
        options.set_capability("appium:udid", serial)
    driver = webdriver.Remote(APPIUM_URL, options=options)
    yield driver
    driver.quit()


@pytest.mark.parametrize(
    ("url", "expected_text"),
    [
        ("nascon://entity/match-m1", "LIVE"),
        ("nascon://stream/cs-session-101", "CO-STREAM"),
    ],
)
def test_mobile_deep_link_foregrounds_expected_screen(mobile_driver, url, expected_text):
    started = time.monotonic()
    mobile_driver.execute_script("mobile: deepLink", {"url": url, "package": APP_PACKAGE})
    assert time.monotonic() - started < 2
    assert mobile_driver.current_package == APP_PACKAGE
    deadline = time.monotonic() + 2
    while time.monotonic() < deadline:
        if expected_text in mobile_driver.page_source.upper():
            break
        time.sleep(0.05)
    else:
        pytest.fail(f"{expected_text!r} was not visible after opening {url}")


def test_cross_surface_costream_chat(mobile_driver):
    if os.getenv("RUN_CROSS_SURFACE") != "1":
        pytest.skip("set RUN_CROSS_SURFACE=1 after configuring the device's API base URL")

    from appium.webdriver.common.appiumby import AppiumBy
    from selenium import webdriver as selenium_webdriver
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait

    message = f"cross-surface-{int(time.time() * 1000)}"
    options = Options()
    options.add_argument("--headless=new")
    browser = selenium_webdriver.Remote(
        command_executor=os.getenv("SELENIUM_GRID_URL", "http://127.0.0.1:4444"),
        options=options,
    )
    try:
        browser.get(
            os.getenv("SELENIUM_WEB_BASE_URL", "http://api:8080").rstrip("/")
            + "/web/costream/cs-session-101"
        )
        WebDriverWait(browser, 3).until(
            lambda driver: driver.find_element(By.CSS_SELECTOR, '[data-testid="chat-message-list"]')
        )

        mobile_driver.execute_script(
            "mobile: deepLink",
            {"url": "nascon://stream/cs-session-101", "package": APP_PACKAGE},
        )
        chat = mobile_driver.find_element(AppiumBy.ACCESSIBILITY_ID, "Chat message")
        chat.send_keys(message)
        mobile_driver.find_element(AppiumBy.ACCESSIBILITY_ID, "Send chat message").click()
        mobile_driver.find_element(AppiumBy.ACCESSIBILITY_ID, "Sign in to continue")
        mobile_driver.find_element(
            AppiumBy.ANDROID_UIAUTOMATOR,
            'new UiSelector().text("Sign in and resume")',
        ).click()

        started = time.monotonic()
        WebDriverWait(browser, 3, poll_frequency=0.05).until(
            lambda driver: message
            in driver.find_element(By.CSS_SELECTOR, '[data-testid="chat-message-list"]').text
        )
        assert time.monotonic() - started < 3
    finally:
        browser.quit()
