"""Real service acceptance. Never claims success from mocks or an absent target."""
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlsplit
import json
from pathlib import Path
from uuid import uuid4

import pymupdf
import pytest

from qr_contract import assert_metadata, decode_export, expected_route


def metadata(client, entity_id, inspect=True):
    response = client.get(f'/audit/v1/qr/{entity_id}', params={'inspect': 'true'} if inspect else {})
    assert response.status_code == 200, f'QR metadata HTTP {response.status_code}'
    return response.json()


def test_all_configured_entities(qr_client, qr_cases, qr_salt):
    for case in qr_cases:
        assert_metadata(metadata(qr_client, case['entity_id']), case, qr_salt)


def test_full_fixture_coverage(qr_cases):
    """A reduced case list must not silently claim all-state acceptance."""
    assert {c.get('state') for c in qr_cases if c['entity_type'] == 'match'} >= {
        'upcoming', 'in_progress', 'completed', 'postponed', 'cancelled', 'abandoned'}
    assert {c['entity_type'] for c in qr_cases} >= {'match', 'player', 'club', 'costream'}


def test_inspection_preserves_count_and_signature(qr_client, qr_cases):
    for case in qr_cases:
        before = metadata(qr_client, case['entity_id'])
        for _ in range(3):
            after = metadata(qr_client, case['entity_id'])
            assert after['scan_count'] == before['scan_count']
            assert after['short_url'] == before['short_url']
            assert after['signature'] == before['signature']


def test_unknown_entity_and_short_code(qr_client):
    unknown = 'qa-unknown-' + uuid4().hex
    for path in (f'/audit/v1/qr/{unknown}', f'/q/{unknown}'):
        response = qr_client.get(path)
        assert response.status_code == 404
        error = response.json()['error']
        assert set(error) == {'code', 'message', 'details'}
        assert error['code'] == 'QR_NOT_FOUND' and isinstance(error['details'], dict)


@pytest.mark.parametrize('fmt,mime', [('svg', 'image/svg+xml'), ('png', 'image/png'), ('pdf', 'application/pdf')])
def test_export_decodes_stable_short_url(qr_client, qr_cases, fmt, mime):
    for case in qr_cases:
        data = metadata(qr_client, case['entity_id'])
        response = qr_client.get(f"/audit/v1/qr/{case['entity_id']}/export.{fmt}")
        assert response.status_code == 200
        assert response.headers['content-type'].split(';')[0].strip() == mime
        assert decode_export(response.content, fmt) == {data['short_url']}
        if fmt == 'pdf':
            with pymupdf.open(stream=response.content, filetype='pdf') as doc:
                assert case['entity_id'] in ''.join(page.get_text() for page in doc)


def test_redirect_location_tracks_current_state(mutation_target, qr_cases):
    for case in qr_cases:
        data = metadata(mutation_target, case['entity_id'])
        response = mutation_target.get(urlsplit(data['short_url']).path)
        assert response.status_code == 302
        location = urlsplit(response.headers['location'])
        assert location.path + ('?' + location.query if location.query else '') == data['target_route']


def test_scan_counter_concurrency(mutation_target, qr_cases):
    case = qr_cases[0]
    before = metadata(mutation_target, case['entity_id'])['scan_count']
    with ThreadPoolExecutor(max_workers=10) as pool:
        counts = list(pool.map(lambda _: metadata(mutation_target, case['entity_id'], inspect=False)['scan_count'], range(10)))
    assert sorted(counts) == list(range(before + 1, before + 11))
    assert metadata(mutation_target, case['entity_id'])['scan_count'] == before + 10


def live_match(cases):
    return next(c for c in cases if c['entity_type'] == 'match' and c.get('state') == 'in_progress')


def assert_transition(client, case, before, state, salt):
    after = metadata(client, case['entity_id'])
    assert_metadata(after, {**case, 'state': state}, salt)
    assert after['short_url'] == before['short_url']
    assert after['target_route'] == expected_route(case['entity_id'], 'match', state)
    assert after['signature'] != before['signature']
    response = client.get(urlsplit(before['short_url']).path)
    assert response.status_code == 302
    location = urlsplit(response.headers['location'])
    assert location.path + ('?' + location.query if location.query else '') == after['target_route']


def test_postponement_after_print(mutation_target, qr_cases, qr_salt, request):
    path = request.config.getoption('--qr-postpone-request')
    if not path:
        pytest.skip('NOT RUN: await Abdullah\'s supported postponement request; no invented event/endpoint')
    adapter = json.loads(Path(path).read_text(encoding='utf-8'))
    assert adapter['path'].startswith('/api/') and not adapter['path'].startswith('//')
    case = next(c for c in qr_cases if c['entity_id'] == adapter['entity_id'])
    before = metadata(mutation_target, case['entity_id'])
    # Optional authentication comes from an environment variable, never the manifest.
    import os
    token = os.environ.get('QR_ORGANIZER_TOKEN')
    response = mutation_target.request(adapter['method'], adapter['path'], json=adapter['body'],
        headers={'Authorization': 'Bearer ' + token} if token else {})
    assert response.status_code in (200, 201, 204)
    assert_transition(mutation_target, case, before, 'postponed', qr_salt)


def test_completion_after_print(mutation_target, qr_cases, qr_salt):
    case = live_match(qr_cases)
    before = metadata(mutation_target, case['entity_id'])
    assert before['entity_status'] == 'in_progress', 'Use a separate live fixture from the postponement case'
    response = mutation_target.post('/audit/v1/events', json={'event_id': 'qa-qr-end-' + uuid4().hex,
        'match_id': case['entity_id'], 'type': 'match_end', 'payload': {}})
    assert response.status_code == 201, f'match_end HTTP {response.status_code}'
    assert_transition(mutation_target, case, before, 'completed', qr_salt)
