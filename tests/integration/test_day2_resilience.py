"""Media revocation, worker recovery, and invitation lifecycle safety checks."""
import io
import json
from types import SimpleNamespace

import pytest


def test_media_revocation_kicks_publishers_only_and_tolerates_closed_session(monkeypatch):
    from app.api import day2
    from urllib.error import HTTPError
    calls = []

    def request(url, **kwargs):
        address = getattr(url, 'full_url', url)
        calls.append(address)
        if address.endswith('/list'):
            return io.BytesIO(json.dumps({'items': [
                {'id': 'publisher', 'path': 'live/key', 'state': 'publish'},
                {'id': 'viewer', 'path': 'live/key', 'state': 'read'},
                {'id': 'other', 'path': 'live/other', 'state': 'publish'},
            ]}).encode())
        if '/webrtc/' in address:
            raise HTTPError(address, 404, 'already closed', {}, None)
        return io.BytesIO(b'')

    monkeypatch.setattr(day2.urllib.request, 'urlopen', request)
    day2._kick_media_publishers('key')
    assert calls == [
        'http://media:9997/v3/rtmp/conns/list',
        'http://media:9997/v3/rtmp/conns/kick/publisher',
        'http://media:9997/v3/webrtc/sessions/list',
        'http://media:9997/v3/webrtc/sessions/kick/publisher',
    ]


def test_media_path_probe_preserves_unknown_state_and_metrics_delta(monkeypatch):
    from app import worker
    from app.api import day2
    payload = {'items': [{'name': 'live/key', 'ready': True, 'bytesReceived': 1000},
                         {'name': 'inactive', 'ready': False}]}
    monkeypatch.setattr(worker.urllib.request, 'urlopen',
                        lambda *a, **k: io.BytesIO(json.dumps(payload).encode()))
    assert worker.active_media_paths() == {'live/key'}
    monkeypatch.setattr(day2, '_media_sample', {'at': 0.0, 'bytes': 0})
    samples = iter([10.0, 12.0])
    monkeypatch.setattr(day2, 'time', SimpleNamespace(monotonic=lambda: next(samples)))
    assert day2._media_metrics() == (1, 0.0)
    payload['items'][0]['bytesReceived'] = 2000
    active, bitrate = day2._media_metrics()
    assert active == 1 and bitrate == 4.0

    def unavailable(*args, **kwargs):
        raise OSError('media unavailable')
    monkeypatch.setattr(worker.urllib.request, 'urlopen', unavailable)
    assert worker.active_media_paths() is None
    assert day2._media_metrics() == (0, 0.0)


@pytest.mark.parametrize('known_media', [True, False])
def test_worker_recovers_connection_after_failure_and_stops_cleanly(monkeypatch, known_media):
    from app import worker
    connections, sleeps, indexed = [], [], []
    monkeypatch.setattr(worker, '_running', True)
    monkeypatch.setattr(worker.signal, 'signal', lambda *args: None)
    monkeypatch.setattr(worker, 'wait_for_db', lambda *args: None)
    monkeypatch.setattr(worker.queue, 'client', lambda *args: object())
    monkeypatch.setattr(worker.object_store, 'client', lambda *args: object())

    class Connection:
        closed = False
        def close(self): self.closed = True

    def connect(*args, **kwargs):
        conn = Connection()
        connections.append(conn)
        return conn

    def relay(conn, redis):
        if len(connections) == 1:
            raise OSError('transient queue failure')
        return 1

    def sleep(delay):
        sleeps.append(delay)
        if delay != 2.0:
            worker._stop()

    def index(*args):
        indexed.append(args)
        return 1

    monkeypatch.setattr(worker.psycopg, 'connect', connect)
    monkeypatch.setattr(worker, 'relay_once', relay)
    monkeypatch.setattr(worker, 'active_media_paths', lambda: set() if known_media else None)
    monkeypatch.setattr(worker, 'index_recordings_once', index)
    monkeypatch.setattr(worker.time, 'sleep', sleep)
    worker.main()
    assert len(connections) == 2 and connections[0].closed
    assert sleeps == [2.0, 0.05]
    assert len(indexed) == int(known_media)


def test_invitation_join_host_authority_and_last_participant_leave(client, reset):
    from app.core import db
    from app.core.errors import DomainError
    from app.domain import day2
    created = client.post('/audit/v1/costream/session', json={
        'session_id': 'cs-invite-lifecycle', 'host_player_id': 'player-alpha-1',
        'participants': ['player-alpha-1'], 'layout': 'grid_4',
    })
    assert created.status_code == 201

    def action(actor, body):
        with db.tx() as conn:
            return day2.costream_action(conn, 'cs-invite-lifecycle', actor, 'player', body)

    with pytest.raises(DomainError) as denied:
        action('player-beta-1', {'action': 'join'})
    assert denied.value.status == 403
    invite = action('player-alpha-1', {'action': 'invite', 'player_id': 'player-beta-1'})
    assert invite['pending_invitations'] == ['player-beta-1']
    joined = action('player-beta-1', {'action': 'join'})
    assert joined['participant_count'] == 2 and joined['pending_invitations'] == []
    assert action('player-beta-1', {'action': 'join'})['participant_count'] == 2
    with pytest.raises(DomainError) as denied:
        action('player-beta-1', {'action': 'set_layout', 'layout': 'grid_2'})
    assert denied.value.status == 403
    assert action('player-alpha-1', {'action': 'set_layout', 'layout': 'grid_2'})['layout'] == 'grid_2'
    handed = action('player-alpha-1', {'action': 'leave'})
    assert handed['active_host'] == 'player-beta-1' and handed['handoff_occurred']
    ended = action('player-beta-1', {'action': 'leave'})
    assert ended['participant_count'] == 0 and ended['status'] == 'terminated'
    assert ended['active_host'] is None and ended['composite_playback_url'] is None
