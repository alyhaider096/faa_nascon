"""Diagnostic capture, not an acceptance pass: record actual implemented/missing contracts.

Run explicitly against the isolated test harness, which resets its database.
This filename intentionally stays outside normal test_* acceptance collection.
"""
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess

from websockets.sync.client import connect
from websockets.exceptions import InvalidStatus


def sanitize(value):
    if isinstance(value, dict):
        return {key: '<redacted>' if key in ('token', 'password', 'pdf_base64') else sanitize(item)
                for key, item in value.items()}
    if isinstance(value, list):
        return [sanitize(item) for item in value]
    return value


def test_capture_actual_contracts(client, server, reset):
    records = []

    def capture(label, method, path, body=None, token=None):
        response = client.request(method, path, json=body,
            headers={'Authorization': 'Bearer ' + token} if token else {})
        try:
            result = response.json()
        except ValueError:
            result = response.text[:300]
        records.append({'label': label, 'request': {'method': method, 'path': path,
            'body': sanitize(body), 'authorization': '<redacted>' if token else None},
            'response': {'status': response.status_code, 'location': response.headers.get('location'),
                         'body': sanitize(result)}})
        return response

    capture('health', 'GET', '/health')
    login = capture('member login', 'POST', '/api/v1/auth/login',
                    {'email': 'admin@nascon.test', 'password': 'Nascon@26'})
    assert login.status_code == 200
    member = login.json()['token']
    guest = 'guest_anon_tok_7721'
    capture('SPA hosting', 'GET', '/web/matches/match-m1/live')
    capture('QR redirect', 'GET', '/q/m1-live')
    capture('public match', 'GET', '/api/v1/public/matches/match-m1')
    capture('public co-stream', 'GET', '/api/v1/public/costream/cs-session-101')
    capture('required reset match', 'GET', '/audit/v1/score/match-m1')
    capture('existing seeded match before mutations', 'GET', '/api/v1/matches/match-001', token=member)
    capture('existing pinned merchandise', 'GET', '/api/v1/matches/match-001/pinned', token=member)
    capture('guest session', 'POST', '/api/v1/guest/session', {})
    capture('guest cart staging', 'POST', '/api/v1/guest/cart',
            {'items': [{'variant_id': 'var-jersey-001-L', 'quantity': 1}]}, guest)
    capture('guest chat guard', 'POST', '/api/v1/chat',
            {'chat_room_id': 'chat-cs-session-101', 'message_id': 'contract-chat', 'text': 'Hello'}, guest)
    order = {'order_id': 'contract-guest-order', 'customer_id': 'user-viewer',
             'items': [{'variant_id': 'var-jersey-001-L', 'quantity': 1}],
             'discount_code': None, 'payment': {'token': 'tok_success'}}
    capture('guest audit checkout guard', 'POST', '/audit/v1/checkout', order, guest)
    capture('guest member checkout guard', 'POST', '/api/v1/checkout', {**order, 'order_id': 'contract-member-order'}, guest)
    event = {'event_id': 'contract-guest-goal', 'match_id': 'match-001', 'type': 'score',
             'payload': {'team_id': 'club-alpha-1', 'event_type': 'goal'}}
    capture('guest audit event guard', 'POST', '/audit/v1/events', event, guest)
    capture('cart merge', 'POST', '/audit/v1/guest/cart-merge',
            {'guest_token': guest, 'registered_user_id': 'user-admin',
             'guest_cart': [{'variant_id': 'var-jersey-001-L', 'quantity': 1}], 'test_write_block': True}, member)
    capture('member cart read', 'GET', '/api/v1/cart', token=member)
    for action in ('generate', 'rotate', 'revoke'):
        capture('stream key ' + action, 'POST', '/api/v1/stream/key',
                {'action': action, 'player_id': 'player-alpha-1', 'label': 'qa-contract'}, member)
    capture('audit stream-key fallback', 'POST', '/audit/v1/stream/key',
            {'action': 'generate', 'player_id': 'player-alpha-1', 'label': 'qa-contract'}, member)
    for action in ('create', 'join', 'invite', 'set_layout', 'mute', 'spotlight', 'kick', 'leave', 'stop'):
        capture('co-stream ' + action, 'POST', '/api/v1/costream/sessions/cs-session-101/actions',
                {'action': action}, member)
    capture('QR metadata', 'GET', '/audit/v1/qr/match-m1?inspect=true')
    for fmt in ('svg', 'png', 'pdf'):
        capture('QR export ' + fmt, 'GET', '/audit/v1/qr/match-m1/export.' + fmt)

    sockets = []
    ws_base = server.replace('http://', 'ws://')
    for path, token, role in [('/ws/matches/match-001', member, 'member'),
                              ('/ws/matches/match-001', guest, 'guest'),
                              ('/ws/v1/matches/match-001', guest, 'guest')]:
        try:
            with connect(ws_base + path + '?token=' + token, open_timeout=5) as ws:
                sockets.append({'path': path, 'role': role, 'first_frame': json.loads(ws.recv(timeout=5))})
        except InvalidStatus as exc:
            sockets.append({'path': path, 'role': role, 'handshake_http_status': exc.response.status_code})
    with connect(ws_base + '/ws/v1/matches/match-001?token=' + member) as ws:
        hello = json.loads(ws.recv(timeout=5))
        capture('member score notification trigger', 'POST', '/api/v1/matches/match-001/events',
                {**event, 'event_id': 'contract-member-goal'}, member)
        score_frame = json.loads(ws.recv(timeout=5))
        capture('merchandise notification trigger', 'POST', '/api/v1/matches/match-001/pin',
                {'product_id': 'prod-jersey-001'}, member)
        merch_frame = json.loads(ws.recv(timeout=5))
        sockets.append({'path': '/ws/v1/matches/match-001', 'role': 'member',
                        'frames': [hello, score_frame, merch_frame]})

    root = Path(__file__).resolve().parents[2]
    output = {'scope': 'Actual isolated local HTTP/WebSocket capture; NOT deployed acceptance and NOT an all-contracts pass',
              'source_sha': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=root, text=True).strip(),
              'captured_at_utc': datetime.now(timezone.utc).isoformat(), 'base_url': server,
              'records': records, 'sockets': sockets,
              'missing_frames': ['chat', 'invitation', 'host_change'],
              'media': 'No implemented media/VOD routes; no LAN ingest/playback verified'}
    (root / 'tests/reports/integration-contract-examples.json').write_text(json.dumps(output, indent=2) + '\n', encoding='utf-8')
    print('Diagnostic examples captured; inspect status mismatches before making any acceptance claim.')
