"""Local QA-tool checks using synthetic exports; never backend acceptance."""
import copy
import hashlib
import hmac
import io

import pymupdf
import pytest
import qrcode
import qrcode.image.svg

from qr_contract import MATCH_STATES, assert_metadata, decode_export, expected_route, signature


def sample():
    entity = 'match-m1'
    short = 'http://localhost:8080/q/m1-live'
    route = '/web/matches/match-m1/live'
    return dict(entity_id=entity, entity_type='match', entity_status='in_progress', short_url=short,
        target_route=route, deep_link_uri='nascon://entity/match-m1', scan_count=0,
        export_formats={fmt: f'http://localhost:8080/audit/v1/qr/{entity}/export.{fmt}' for fmt in ('svg', 'png', 'pdf')},
        signature=signature('public-test-salt', entity, short, route))


@pytest.mark.parametrize('state,suffix', list(zip(MATCH_STATES,
    ('preview', 'live', 'vod', 'notice?state=postponed', 'notice?state=cancelled', 'notice?state=abandoned'))))
def test_match_routing_reference(state, suffix):
    assert expected_route('match-m1', 'match', state) == '/web/matches/match-m1/' + suffix


@pytest.mark.parametrize('kind,entity,path', [('player', 'player-alpha-1', 'players'),
    ('club', 'club-alpha-1', 'clubs'), ('costream', 'cs-session-101', 'costream')])
def test_other_entity_routes(kind, entity, path):
    assert expected_route(entity, kind, 'active') == f'/web/{path}/{entity}'


def test_independent_literal_canonical_message():
    message = 'match-m1|{"entity_id":"match-m1","short_url":"http://localhost:8080/q/m1-live","target_route":"/web/matches/match-m1/live"}'
    expected = hmac.new(b'public-test-salt', message.encode('utf-8'), hashlib.sha256).hexdigest()
    data = sample()
    assert data['signature'] == expected
    assert_metadata(data, dict(entity_id='match-m1', entity_type='match', state='in_progress'), 'public-test-salt')
    with pytest.raises(AssertionError):
        assert_metadata(data, dict(entity_id='match-m1', entity_type='match'), 'wrong-public-test-key')


@pytest.mark.parametrize('field,value', [('scan_count', True), ('scan_count', -1), ('scan_count', None),
    ('short_url', '/q/m1-live'), ('signature', 'abc...'), ('signature', 'A' * 64),
    ('deep_link_uri', 'nascon://wrong'), ('target_route', '/web/matches/match-m1/vod'),
    ('export_formats', {'png': 'wrong'})])
def test_metadata_rejects_contract_corruption(field, value):
    data = copy.deepcopy(sample())
    data[field] = value
    with pytest.raises(AssertionError):
        assert_metadata(data, dict(entity_id='match-m1', entity_type='match', state='in_progress'), 'public-test-salt')


def test_export_decoders_use_actual_qr_payloads():
    url = 'http://localhost:8080/q/m1-live'
    png = io.BytesIO()
    qrcode.make(url).save(png, format='PNG')
    svg = io.BytesIO()
    qrcode.make(url, image_factory=qrcode.image.svg.SvgPathImage).save(svg)
    with pymupdf.open() as doc:
        page = doc.new_page()
        page.insert_text((50, 40), 'match-m1')
        page.insert_image(pymupdf.Rect(50, 60, 450, 460), stream=png.getvalue())
        pdf = doc.tobytes()
    for fmt, body in [('png', png.getvalue()), ('svg', svg.getvalue()), ('pdf', pdf)]:
        assert decode_export(body, fmt) == {url}
        assert 'http://wrong.example/q/other' not in decode_export(body, fmt)


def test_invalid_export_headers_fail():
    for fmt in ('png', 'svg', 'pdf'):
        with pytest.raises(AssertionError):
            decode_export(b'not a QR export', fmt)
