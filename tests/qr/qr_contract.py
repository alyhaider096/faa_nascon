"""Independent QR acceptance helpers; no production imports."""
import hashlib
import hmac
import io
import json
import re
from urllib.parse import urlsplit

KEYS = {'entity_id', 'entity_type', 'entity_status', 'short_url', 'target_route',
        'deep_link_uri', 'scan_count', 'export_formats', 'signature'}
MATCH_STATES = ('upcoming', 'in_progress', 'completed', 'postponed', 'cancelled', 'abandoned')


def expected_route(entity_id, entity_type, state):
    if entity_type == 'match':
        suffix = {'upcoming': 'preview', 'in_progress': 'live', 'completed': 'vod'}.get(state)
        if suffix:
            return f'/web/matches/{entity_id}/{suffix}'
        if state in ('postponed', 'cancelled', 'abandoned'):
            return f'/web/matches/{entity_id}/notice?state={state}'
        raise ValueError('Unsupported match fixture state')
    prefix = {'player': 'players', 'club': 'clubs', 'costream': 'costream'}[entity_type]
    return f'/web/{prefix}/{entity_id}'


def signature(salt, entity_id, short_url, target_route):
    payload = dict(entity_id=entity_id, short_url=short_url, target_route=target_route)
    message = entity_id + '|' + json.dumps(payload, sort_keys=True, separators=(',', ':'), ensure_ascii=False)
    return hmac.new(salt.encode('utf-8'), message.encode('utf-8'), hashlib.sha256).hexdigest()


def assert_metadata(data, case, salt):
    assert set(data) == KEYS, 'QR response key set differs from Section 5.6'
    assert data['entity_id'] == case['entity_id']
    assert data['entity_type'] == case['entity_type']
    assert isinstance(data['entity_status'], str)
    if 'state' in case:
        assert data['entity_status'] == case['state']
    assert data['target_route'] == expected_route(case['entity_id'], case['entity_type'], data['entity_status'])
    assert data['deep_link_uri'] == f"nascon://entity/{case['entity_id']}"
    assert type(data['scan_count']) is int and data['scan_count'] >= 0
    assert isinstance(data['short_url'], str)
    short = urlsplit(data['short_url'])
    assert short.scheme in ('http', 'https') and short.netloc and short.path.startswith('/q/')
    assert not short.query and not short.fragment and not short.username
    assert set(data['export_formats']) == {'svg', 'png', 'pdf'}
    for fmt, url in data['export_formats'].items():
        assert isinstance(url, str)
        parsed = urlsplit(url)
        assert parsed.scheme in ('http', 'https') and parsed.netloc
        assert parsed.path == f"/audit/v1/qr/{case['entity_id']}/export.{fmt}"
    assert isinstance(data['signature'], str) and re.fullmatch('[0-9a-f]{64}', data['signature'])
    expected = signature(salt, data['entity_id'], data['short_url'], data['target_route'])
    assert hmac.compare_digest(data['signature'], expected), 'QR signature mismatch (key is not logged)'


def decode_export(body, fmt):
    """Render actual bytes and decode QR payloads, not document text or filenames."""
    from PIL import Image
    import pymupdf
    import zxingcpp

    if fmt == 'png':
        assert body.startswith(b'\x89PNG\r\n\x1a\n')
        images = [Image.open(io.BytesIO(body)).convert('RGB')]
    else:
        if fmt == 'svg':
            assert body.lstrip().startswith((b'<svg', b'<?xml'))
            with pymupdf.open(stream=body, filetype='svg') as svg:
                pdf = svg.convert_to_pdf()
            document = pymupdf.open(stream=pdf, filetype='pdf')
        else:
            assert body.startswith(b'%PDF-')
            document = pymupdf.open(stream=body, filetype='pdf')
        with document:
            images = []
            for page in document:
                pix = page.get_pixmap(matrix=pymupdf.Matrix(3, 3), colorspace=pymupdf.csRGB, alpha=False)
                images.append(Image.frombytes('RGB', (pix.width, pix.height), pix.samples))
    return {result.text for image in images for result in zxingcpp.read_barcodes(image,
            formats=zxingcpp.BarcodeFormat.QRCode)}
