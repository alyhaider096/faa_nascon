"""The four adversarial scenario contracts, exercised against real PostgreSQL."""
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest


def test_four_way_host_drop_preserves_room_and_composite_identity(client, reset):
    participants = ['player-alpha-1', 'player-alpha-2', 'player-beta-1', 'player-beta-2']
    body = {'session_id': 'cs-grade-four', 'host_player_id': participants[0],
            'participants': participants, 'layout': 'grid_4'}
    before = client.post('/audit/v1/costream/session', json=body)
    assert before.status_code == 201
    dropped = client.post('/audit/v1/costream/session', json={**body, 'simulate_host_drop': True})
    assert dropped.status_code == 200
    state = dropped.json()
    assert state['active_host'] == participants[1]
    assert state['handoff_occurred'] is True
    assert state['participant_count'] == 3
    assert state['active_participants'] == participants[1:]
    assert state['chat_room_id'] == before.json()['chat_room_id']
    assert state['composite_playback_url'] == before.json()['composite_playback_url']
    assert state['status'] == 'active'
    # HTTP media continuity / process cleanup needs an actual media publisher;
    # these assertions deliberately establish the state contract only.


@pytest.mark.parametrize(('event', 'target'), [
    ('match_end', '/web/matches/match-m1/vod'),
    ('match_postponed', '/web/matches/match-m1/notice?state=postponed'),
])
def test_printed_qr_immediately_changes_destination(client, reset, event, target):
    before = client.get('/audit/v1/qr/match-m1?inspect=true').json()
    changed = client.post('/audit/v1/events', json={
        'event_id': f'grade-{event}', 'match_id': 'match-m1', 'type': event, 'payload': {},
    })
    assert changed.status_code == 201, changed.text
    after = client.get('/audit/v1/qr/match-m1?inspect=true').json()
    assert before['short_url'] == after['short_url']
    assert after['target_route'] == target
    assert before['signature'] != after['signature']
    redirect = client.get('/q/m1-live', follow_redirects=False)
    assert redirect.status_code == 302
    assert redirect.headers['location'] == target


def test_ten_simultaneous_moderators_deduplicate_same_user(client, reset):
    gate = Barrier(10)

    def moderate(index):
        gate.wait(timeout=10)
        return client.post('/audit/v1/moderation/test', json={
            'chat_room_id': 'chat-grade-race', 'check_dlq': True,
            'incoming_messages': [
                {'message_id': 'same-offense', 'sender': 'user-spammer', 'text': 'b@d.w0rd'},
                {'message_id': 'same-mute', 'sender': 'user-spammer', 'text': 'AAAA'},
                {'message_id': 'second-offense', 'sender': 'user-spammer', 'text': 'b@d.w0rd'},
            ],
        })

    with ThreadPoolExecutor(max_workers=10) as executor:
        responses = list(executor.map(moderate, range(10)))
    for response in responses:
        assert response.status_code == 200, response.text
        data = response.json()
        assert data['kicked_users'] == ['user-spammer']
        assert data['muted_users'] == ['user-spammer']
        assert data['dlq_status']['queue_depth'] == 0
        assert data['dlq_status']['undelivered_events'] == []


def test_network_retry_and_concurrent_cart_merge_reserve_once(client, reset):
    token = client.post('/api/v1/guest/session', json={}).json()['guest_token']
    before = client.get('/audit/v1/inventory/var-jersey-001-L').json()
    body = {'guest_token': token, 'registered_user_id': 'user-viewer',
            'guest_cart': [{'variant_id': 'var-jersey-001-L', 'quantity': 1}],
            'test_write_block': True}
    gate = Barrier(2)

    def merge(_):
        gate.wait(timeout=10)
        return client.post('/audit/v1/guest/cart-merge', json=body)

    with ThreadPoolExecutor(max_workers=2) as executor:
        responses = list(executor.map(merge, range(2)))
    replay = client.post('/audit/v1/guest/cart-merge', json=body)
    for response in [*responses, replay]:
        assert response.status_code == 200, response.text
        assert response.json()['active_cart']['total_items'] == 1
        assert response.json() == responses[0].json()
    after = client.get('/audit/v1/inventory/var-jersey-001-L').json()
    assert after['reserved'] == before['reserved'] + 1
    assert after['stock'] == before['stock']
