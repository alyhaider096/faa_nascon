"""Actual event writes and persisted score changes for all five mobile roles."""
import pytest

ACCOUNTS = [
    ("admin@nascon.test", True),
    ("organizer@nascon.test", True),
    ("manager@nascon.test", False),
    ("player@nascon.test", False),
    ("viewer@nascon.test", False),
]


def login(client, email):
    response = client.post('/api/v1/auth/login', json={"email": email, "password": "Nascon@26"})
    assert response.status_code == 200, response.text
    return {"Authorization": "Bearer " + response.json()["token"]}


def score_event(eid="role-goal"):
    return {"event_id": eid, "match_id": "match-001", "type": "score",
            "payload": {"team_id": "club-alpha-1", "event_type": "goal"}}


@pytest.mark.parametrize('email,allowed', ACCOUNTS)
@pytest.mark.parametrize('mode', ['direct', 'offline'])
@pytest.mark.parametrize('kind,delta', [('score', 1), ('compensation', -1)])
def test_each_role_event_confirmation_and_readback(client, reset, email, allowed, mode, kind, delta):
    headers = login(client, email)
    before = client.get('/audit/v1/score/match-001').json()
    event = score_event()
    if kind == 'compensation':
        event.update(type='compensation', payload={"compensates": "match-001-goal-home-1", "reason": "review"})
    if mode == 'direct':
        response = client.post('/api/v1/matches/match-001/events', headers=headers, json=event)
        assert response.status_code == (201 if allowed else 403), response.text
        if not allowed:
            assert response.json()['error']['code'] == 'FORBIDDEN'
        else:
            replay = client.post('/api/v1/matches/match-001/events', headers=headers, json=event)
            assert replay.status_code == 200 and replay.json() == response.json()
    else:
        request = {"device_id": "role-device", "actions": [{"action_id": "role-action", "type": "score_event",
            "queued_at": "2026-10-18T06:00:00Z", "base_version": before['version'], "payload": event}]}
        response = client.post('/api/v1/offline-sync', headers=headers, json=request)
        assert response.status_code == 200, response.text
        result = response.json()['results'][0]
        assert result['status'] == ('applied' if allowed else 'rejected')
        if not allowed:
            assert result['error_code'] == 'FORBIDDEN'
        else:
            replay = client.post('/api/v1/offline-sync', headers=headers, json=request)
            assert replay.json()['results'][0]['status'] == 'duplicate'
    after = client.get('/api/v1/matches/match-001', headers=headers)
    assert after.status_code == 200, after.text
    assert after.json()['home']['score'] == before['home']['score'] + delta * int(allowed)
    assert after.json()['version'] == before['version'] + int(allowed)


@pytest.mark.parametrize('mode', ['direct', 'offline'])
def test_organizer_cannot_cross_league_scope(client, reset, mode):
    response = client.post('/audit/v1/events', json={"event_id": "foreign-init", "match_id": "foreign-match",
        "type": "match_init", "payload": {"sport_id": "football", "home_team_id": "b1", "away_team_id": "b2", "league_id": "league-beta-1"}})
    assert response.status_code == 201, response.text
    body = {"event_id": "foreign-start", "match_id": "foreign-match", "type": "match_start", "payload": {}}
    headers = login(client, 'organizer@nascon.test')
    if mode == 'direct':
        result = client.post('/api/v1/matches/foreign-match/events', headers=headers, json=body)
        assert result.status_code == 403 and result.json()['error']['code'] == 'FORBIDDEN'
    else:
        result = client.post('/api/v1/offline-sync', headers=headers, json={"device_id": "scope-device", "actions": [
            {"action_id": "scope-action", "type": "score_event", "queued_at": "2026-10-18T06:00:00Z", "base_version": 1, "payload": body}]})
        assert result.status_code == 200, result.text
        assert result.json()['results'][0]['error_code'] == 'FORBIDDEN'
    assert client.get('/audit/v1/score/foreign-match').json()['status'] == 'upcoming'
