import json
import os
from pathlib import Path

import httpx
import pytest


def pytest_addoption(parser):
    parser.addoption('--qr-base-url', default=os.environ.get('QR_BASE_URL'))
    parser.addoption('--qr-cases', default=os.environ.get('QR_CASES'))
    parser.addoption('--qr-allow-mutations', action='store_true', default=False)
    parser.addoption('--qr-postpone-request', default=os.environ.get('QR_POSTPONE_REQUEST'))


@pytest.fixture(scope='session')
def qr_client(request):
    base = request.config.getoption('--qr-base-url')
    if not base:
        pytest.skip('NOT RUN: configure --qr-base-url for real QR acceptance')
    with httpx.Client(base_url=base.rstrip('/'), timeout=15, follow_redirects=False, trust_env=False) as client:
        yield client


@pytest.fixture(scope='session')
def qr_salt(qr_client):
    # Root integration conftest injects a public DAY2_SALT for its in-process app.
    # External targets need a separate oracle key so collection cannot overwrite it.
    salt = os.environ.get('QR_DAY2_SALT') or os.environ.get('DAY2_SALT')
    if not salt:
        pytest.fail('DAY2_SALT is missing; supply privately in the test process environment', pytrace=False)
    return salt


@pytest.fixture(scope='session')
def qr_cases(request):
    path = request.config.getoption('--qr-cases')
    if not path:
        pytest.skip('NOT RUN: provide --qr-cases with seeded entity IDs and current states')
    cases = json.loads(Path(path).read_text(encoding='utf-8'))
    assert isinstance(cases, list) and cases, 'QR cases must be a nonempty JSON array'
    assert len({case['entity_id'] for case in cases}) == len(cases), 'Fixture entity IDs must be unique'
    return cases


@pytest.fixture
def mutation_target(request, qr_client):
    if not request.config.getoption('--qr-allow-mutations'):
        pytest.skip('NOT RUN: mutation requires --qr-allow-mutations on an exclusive disposable target')
    return qr_client
