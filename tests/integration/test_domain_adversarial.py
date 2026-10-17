"""Contract adversaries over real HTTP and the platform's psycopg/SQLAlchemy bridge.

Expected signatures and Swiss optima are computed independently of app helpers.
Only public demo salt is used. Tests require the throwaway server in conftest.py.
"""
from collections import Counter
from copy import deepcopy
from fractions import Fraction
import hashlib
import hmac
import json

import pytest


def post(client, path, body, status=200):
    response = client.post('/audit/v1/' + path, json=body)
    assert response.status_code == status, response.text
    return response.json()


def event(client, mid, eid, kind, payload=None, status=201):
    return post(client, 'events', {'event_id': eid, 'match_id': mid,
                'type': kind, 'payload': payload or {}}, status)


def signature(eid, payload):
    encoded = json.dumps(payload, sort_keys=True, ensure_ascii=False,
                         separators=(',', ':')).encode('utf-8')
    return hmac.new(b'demo-salt', eid.encode('utf-8') + b'|' + encoded, hashlib.sha256).hexdigest()


def sport(model='event', **changes):
    models = {
        'event': ({'count': 2, 'duration_minutes': 7}, {'pulse': {'points': 1}}),
        'innings': ({'innings_per_team': 1, 'overs_per_innings': 5,
                    'balls_per_over': 4, 'wickets_per_innings': 2},
                   {'pulse': {'runs': 4, 'legal_ball': True, 'wicket': False},
                    'out': {'runs': 0, 'legal_ball': True, 'wicket': True},
                    'free': {'runs': 1, 'legal_ball': False, 'wicket': False},
                    'small': {'runs': 3, 'legal_ball': True, 'wicket': False}}),
        'round': ({'best_of': 3}, {'pulse': {'rounds': 1}}),
    }
    periods, events = models[model]
    return {'sport_id': 'unknown-' + model, 'name': 'Config only', 'scoring_model': model,
            'periods': periods, 'scoring_events': events, 'draw_allowed': True,
            'overtime': {'policy': 'none'}, 'roster': {'min_squad_size': 1,
            'max_squad_size': 8, 'required_positions': {}}, **changes}


def register(client, lid, sid, teams, fixtures, **options):
    return post(client, 'leagues', {'league_id': lid, 'sport_id': sid, 'teams': teams,
                'fixtures': [{'match_id': m, 'home': a, 'away': b} for m, a, b in fixtures],
                'qualification': {'spots': 1}, **options}, 201)


def play(client, mid, actions):
    event(client, mid, mid + ':start', 'match_start')
    for i, payload in enumerate(actions):
        event(client, mid, f'{mid}:score:{i}', 'score', payload)
    event(client, mid, mid + ':end', 'match_end')


def pairings(teams):
    if not teams:
        yield []
        return
    a, *rest = teams
    for b in rest:
        for remaining in pairings([t for t in rest if t != b]):
            yield [(a, b), *remaining]


@pytest.mark.parametrize('n', [3, 7, 64])
def test_swiss_first_round_exact_seed_split_http(client, reset, n):
    teams = [f't{i}' for i in range(1, n + 1)]
    out = post(client, 'fixtures', {'format': 'swiss', 'teams': teams})
    assert out['bye'] == (teams[-1] if n % 2 else None)
    assert [(p['home'], p['away']) for p in out['pairings']] == [
        (teams[i], teams[i + n // 2]) for i in range(n // 2)]
    assert all(r['score'] == r['buchholz'] == 0 for r in out['standings'])


def test_swiss_global_optimum_against_exhaustive_oracle_http(client, reset):
    teams = [f't{i}' for i in range(1, 9)]
    games = [{'home': teams[i], 'away': teams[i+4],
              'result': 'home' if i % 2 else 'draw'} for i in range(4)]
    history = [{'round': 1, 'bye': None, 'matches': games}]
    out = post(client, 'fixtures', {'format': 'swiss', 'teams': teams,
               'params': {'round': 2, 'history': history}})
    scores = {t: 0 for t in teams}
    for g in games:
        scores[g['home']] += 1 if g['result'] == 'home' else .5
        scores[g['away']] += .5 if g['result'] == 'draw' else 0
    previous = {frozenset((g['home'], g['away'])) for g in games}
    valid = [p for p in pairings(teams) if all(frozenset(pair) not in previous for pair in p)]
    expected = min(sum(abs(scores[a] - scores[b]) for a, b in pairs) for pairs in valid)
    chosen = [(p['home'], p['away']) for p in out['pairings']]
    assert len({t for pair in chosen for t in pair}) == len(teams)
    assert all(frozenset(pair) not in previous for pair in chosen)
    assert sum(abs(scores[a] - scores[b]) for a, b in chosen) == expected


def test_swiss_impossible_matching_is_409_not_greedy_partial_http(client, reset):
    # Every team has two available opponents, but the remaining graph is two
    # disconnected odd triangles: no complete rematch-free matching exists.
    history = [{'round': r+1, 'bye': None, 'matches': [
        {'home': f't{i+1}', 'away': f't{4+(i+r)%3}', 'result': 'draw'} for i in range(3)]}
        for r in range(3)]
    error = post(client, 'fixtures', {'format': 'swiss', 'teams': [f't{i}' for i in range(1, 7)],
                 'params': {'round': 4, 'total_rounds': 5, 'history': history}}, 409)['error']
    assert error['code'] == 'NO_VALID_PAIRING' and error['details']['round'] == 4


def test_swiss_bye_preference_and_buchholz_http(client, reset):
    history = [{'round': 1, 'bye': 't5', 'matches': [
        {'home': 't1', 'away': 't3', 'result': 'home'},
        {'home': 't2', 'away': 't4', 'result': 'draw'}]}]
    out = post(client, 'fixtures', {'format': 'swiss', 'teams': [f't{i}' for i in range(1, 6)],
                 'params': {'round': 2, 'total_rounds': 3, 'history': history}})
    assert out['bye'] == 't3'  # worst score, no previous bye
    assert [(r['team_id'], r['score'], r['buchholz']) for r in out['standings']] == [
        ('t1', 1, 0), ('t5', 1, 0), ('t2', .5, .5), ('t4', .5, .5), ('t3', 0, 1)]


@pytest.mark.parametrize('policy', ['void_all', 'forfeit_remaining'])
def test_double_round_robin_withdrawals_keep_byes_and_all_fixtures_http(client, reset, policy):
    teams = ['a', 'b', 'c', 'd', 'e']
    out = post(client, 'fixtures', {'format': 'round_robin', 'teams': teams, 'params': {
        'legs': 2, 'withdrawal_policy': policy, 'withdrawals': [
            {'team_id': 'a', 'after_round': 1}, {'team_id': 'b', 'after_round': 6}]}})
    assert out['round_count'] == 10 and out['summary']['total'] == 20
    byes, oriented, statuses = Counter(), Counter(), Counter()
    for r in out['rounds']:
        assert len(r['byes']) == 1
        byes.update(r['byes'])
        for m in r['matches']:
            home, away = m['home'], m['away']
            oriented[home, away] += 1
            assert m['match_id'].startswith(f"RR-L{m['leg']}-R{r['round']}-M")
            withdrew = {'a': 1, 'b': 6}
            both = home in withdrew and away in withdrew
            any_withdrew = home in withdrew or away in withdrew
            active = [t for t in (home, away) if t in withdrew and r['round'] > withdrew[t]]
            expected = 'voided' if both or (policy == 'void_all' and any_withdrew) else 'forfeit' if active else 'scheduled'
            assert m['status'] == expected
            assert m['awarded_to'] == (next(t for t in (home, away) if t not in active) if expected == 'forfeit' else None)
            statuses[m['status']] += 1
    assert set(byes.values()) == {2}
    assert len(oriented) == 20 and set(oriented.values()) == {1}
    assert all(out['summary'][k] == statuses[k] for k in ('scheduled', 'forfeit', 'voided'))


@pytest.mark.parametrize('n', [3, 5, 8, 128])
def test_double_elimination_graph_and_seeded_byes_http(client, reset, n):
    out = post(client, 'fixtures', {'format': 'double_elim', 'teams': [f't{i}' for i in range(1, n+1)],
                 'params': {'bracket_reset': True}})
    winners = [m for r in out['winners'] for m in r['matches']]
    losers = [m for r in out['losers'] for m in r['matches']]
    assert len(winners) == out['bracket_size'] - 1
    assert len(losers) == out['bracket_size'] - 2
    assert sum(m['bye'] for m in out['winners'][0]['matches']) == out['bracket_size'] - n
    feeds = Counter()
    for match in winners + losers + out['grand_final']:
        for key in ('winner_to', 'loser_to'):
            target = match[key]
            if target:
                feeds[target['match_id'], target['slot']] += 1
    assert set(feeds.values()) == {1}
    assert winners[-1]['winner_to'] == {'match_id': 'GF1', 'slot': 'home'}
    assert losers[-1]['winner_to'] == {'match_id': 'GF1', 'slot': 'away'}
    assert out['grand_final'][1]['required'] is None


@pytest.mark.parametrize('losers_champion_wins_first', [False, True])
def test_double_elimination_play_through_non_power_two_and_reset_http(client, reset, losers_champion_wins_first):
    teams = ['a', 'b', 'c', 'd', 'e']
    results, losses = [], Counter()
    for _ in range(16):
        out = post(client, 'fixtures', {'format': 'double_elim', 'teams': teams,
                     'params': {'bracket_reset': True, 'results': results}})
        matches = [m for r in out['winners'] + out['losers'] for m in r['matches']] + out['grand_final']
        available = [m for m in matches if m['home'] and m['away'] and not m['winner']
                     and not m['bye'] and m['required'] is True]
        if not available:
            break
        match = available[0]
        if match['match_id'] == 'GF1':
            assert losses[match['home']] == 0 and losses[match['away']] == 1
        winner = match['away'] if match['match_id'] == 'GF1' and losers_champion_wins_first else match['home']
        loser = match['away'] if winner == match['home'] else match['home']
        losses[loser] += 1
        results.append({'match_id': match['match_id'], 'winner': winner})
    else:
        pytest.fail('Bracket did not terminate')
    assert out['grand_final'][1]['required'] is losers_champion_wins_first
    champion = out['grand_final'][1 if losers_champion_wins_first else 0]['winner']
    assert champion is not None
    assert all(losses[t] == 2 for t in teams if t != champion)
    assert losses[champion] == (1 if losers_champion_wins_first else 0)
    assert len(results) == (2 * len(teams) - 1 if losers_champion_wins_first else 2 * len(teams) - 2)


def test_three_way_mini_league_restarts_on_split_ignoring_outsider_scores_http(client, reset):
    cfg = sport(scoring_events={'one': {'points': 1}, 'two': {'points': 2}, 'three': {'points': 3}, 'huge': {'points': 100}})
    post(client, 'sports', cfg, 201)
    fixtures = [('ab', 'a', 'b'), ('bc', 'b', 'c'), ('ca', 'c', 'a'),
                ('ad', 'a', 'd'), ('bd', 'b', 'd'), ('cd', 'c', 'd')]
    register(client, 'lg', cfg['sport_id'], ['a','b','c','d'], fixtures)
    for mid, winner, name in [('ab','a','three'), ('bc','b','two'), ('ca','c','one'),
                              ('ad','a','one'), ('bd','b','one'), ('cd','c','huge')]:
        play(client, mid, [{'team_id': winner, 'event_type': name}])
    result = client.get('/audit/v1/standings/lg').json()
    assert [r['team_id'] for r in result['table']] == ['a','b','c','d']
    assert [r['points'] for r in result['table']] == [6,6,6,0]
    assert result['table'][0]['resolved_by'] == 'h2h_diff'
    assert result['table'][1]['resolved_by'] == 'h2h_points'
    assert result['table'][2]['diff'] > result['table'][1]['diff']  # outsider advantage must not win this tie
    assert result['h2h']['b']['c']['points'] == 3


def test_nrr_uses_total_legal_balls_and_full_all_out_allocation_http(client, reset):
    cfg = sport('innings')
    post(client, 'sports', cfg, 201)
    register(client, 'lg-nrr', cfg['sport_id'], ['a','b'], [('n1','a','b'), ('n2','b','a')])
    play(client, 'n1', [{'team_id':'a','event_type':'pulse'}, {'team_id':'a','event_type':'pulse'},
                       {'team_id':'a','event_type':'out'}, {'team_id':'a','event_type':'out'},
                       {'team_id':'b','event_type':'pulse'}])
    play(client, 'n2', [{'team_id':'a','event_type':'small'}, {'team_id':'b','event_type':'small'},
                       {'team_id':'b','event_type':'free'}])
    # a all-out: 8/5 overs; second game 3/(1/4). b uses one legal ball each game.
    # Aggregate rates, never mean per-match NRR or treat '1.2' as decimal overs.
    expected = round(float(Fraction(11, 1) / Fraction(21, 4) - Fraction(8, 1) / Fraction(1, 2)), 3)
    table = {r['team_id']: r for r in client.get('/audit/v1/standings/lg-nrr').json()['table']}
    assert table['a']['diff'] == expected and table['b']['diff'] == -expected
    assert table['a']['scored'] == 11 and table['a']['conceded'] == 8
    assert client.get('/audit/v1/score/n1').json()['home']['overs'] == '1.0'


@pytest.mark.parametrize('model', ['event', 'innings', 'round'])
def test_mystery_models_signatures_compensation_and_completed_replay_http(client, reset, model):
    cfg = sport(model)
    post(client, 'sports', cfg, 201)
    mid = 'custom-' + model
    payload = {'sport_id': cfg['sport_id'], 'home_team_id': 'a', 'away_team_id': 'b'}
    event(client, mid, 'init', 'match_init', payload)
    event(client, mid, 'start', 'match_start')
    scored = {'team_id': 'a', 'event_type': 'pulse', 'metadata': {'é': [True, None, {'ب': 2}]}}
    first = event(client, mid, 'score', 'score', scored)
    assert first['signature'] == signature('score', scored)
    event(client, mid, 'discipline', 'discipline', {'team_id':'b', 'points':-2})
    event(client, mid, 'end', 'match_end')
    event(client, mid, 'undo', 'compensation', {'compensates':'score','reason':'review'})
    assert event(client, mid, 'score', 'score', scored, 200) == first
    out = client.get('/audit/v1/score/' + mid).json()
    assert out['home']['score'] == 0 and out['away']['fair_play'] == -2
    assert out['status'] == 'completed' and out['outcome'] == 'draw'
    assert out['version'] == 6
    for e in out['events']:
        assert e['signature'] == signature(e['event_id'], e['payload'])
    original = next(e for e in out['events'] if e['event_id'] == 'score')
    assert original['compensated'] is True and original['compensated_by'] == 'undo'
    bad = event(client, mid, 'again', 'compensation', {'compensates':'score','reason':'again'}, 409)
    assert bad['error']['code'] == 'INVALID_COMPENSATION'


def test_completed_tiebreak_compensation_reopens_qualification_http(client, reset):
    cfg = sport(draw_allowed=False)
    post(client, 'sports', cfg, 201)
    register(client, 'lg-tie', cfg['sport_id'], ['a','b'], [('tie','a','b')])
    event(client, 'tie', 'start', 'match_start')
    event(client, 'tie', 'winner', 'tiebreak_winner', {'team_id':'a'})
    event(client, 'tie', 'end', 'match_end')
    before = client.get('/audit/v1/standings/lg-tie').json()['table']
    assert before[0]['status'] == 'clinched' and before[1]['status'] == 'eliminated'
    event(client, 'tie', 'undo', 'compensation', {'compensates':'winner','reason':'review'})
    assert client.get('/audit/v1/score/tie').json()['outcome'] == 'undecided'
    after = client.get('/audit/v1/standings/lg-tie').json()['table']
    assert all(r['played'] == 0 and r['status'] == 'still_possible' for r in after)


@pytest.mark.parametrize('change', [{'scoring_events': {'x': {'points': True}}},
    {'tie_break_order': ['scored','scored']}, {'periods': {'count':1,'duration_minutes':False}}])
def test_mystery_sport_schema_rejections_are_atomic_http(client, reset, change):
    cfg = sport()
    bad = post(client, 'sports', {**deepcopy(cfg), **change}, 400)
    assert bad['error']['code'] == 'VALIDATION_ERROR' and bad['error']['details']['fields']
    post(client, 'sports', cfg, 201)  # rejected create must not reserve the identifier
