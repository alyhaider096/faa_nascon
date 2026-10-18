from __future__ import annotations

import os
from urllib.request import urlopen

import pytest


GRID_URL = os.getenv("SELENIUM_GRID_URL", "http://127.0.0.1:4444")


def _grid_ready() -> bool:
    try:
        with urlopen(f"{GRID_URL}/status", timeout=2) as response:
            return response.status == 200
    except OSError:
        return False


@pytest.fixture()
def browser(request):
    if os.getenv("RUN_SELENIUM_GRID") != "1":
        pytest.skip("set RUN_SELENIUM_GRID=1 to execute the real Grid acceptance suite")
    if not _grid_ready():
        pytest.fail(f"Selenium Grid is not reachable at {GRID_URL}")

    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options as ChromeOptions
    from selenium.webdriver.firefox.options import Options as FirefoxOptions

    worker = getattr(request.config, "workerinput", {}).get("workerid", "gw0")
    requested = os.getenv("SELENIUM_BROWSER")
    browser_name = requested or ("firefox" if worker.endswith("2") else "chrome")
    if browser_name == "firefox":
        options = FirefoxOptions()
        options.add_argument("-headless")
    else:
        options = ChromeOptions()
        options.add_argument("--headless=new")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")

    driver = webdriver.Remote(command_executor=GRID_URL, options=options)
    driver.set_window_size(390, 844)
    yield driver
    driver.quit()
