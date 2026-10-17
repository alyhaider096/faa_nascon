from collections import Counter
from itertools import combinations
import time
import pytest
from backend.app.domain.common import DomainError
from backend.app.domain.fixtures import generate_fixtures


def generate(fmt, n, **params):
    return generate_fixtures({'format': fmt, 'teams': [f't{i}' for i in range(1, n + 1)], 'params': params})


@pytest.mark.parametrize('n', list(range(2, 41)))
@pytest.mark.parametrize('legs', [1, 2])
def test_round_robin_properties(n, legs):
    out = generate('round_robin', n, legs=legs)
    pairs = Counter()
    directed = Counter()
    home, away, byes = Counter(), Counter(), Counter()
    for r in out['rounds']:
        seen = list(r['byes'])
        byes.update(r['byes'])
        for m in r['matches']:
            a, b, leg = m['home'], m['away'], m['leg']
            seen.extend((a, b))
            pairs[frozenset((a, b))] += 1
            directed[a, b] += 1
            home[leg, a] += 1
            away[leg, b] += 1
        assert len(seen) == len(set(seen)) == n
        assert len(r['byes']) == n % 2
    assert len(pairs) == n * (n - 1) // 2
    assert set(pairs.values()) == {legs}
    assert all(abs(home[leg, f't{i}'] - away[leg, f't{i}']) <= 1 for leg in range(1, legs + 1) for i in range(1, n + 1))
    if legs == 2:
        assert set(directed.values()) == {1}
    if n % 2:
        assert set(byes.values()) == {legs}


def test_withdrawals():
    out = generate('round_robin', 5, withdrawals=[{'team_id': 't3', 'after_round': 2}])
    for r in out['rounds']:
        for m in r['matches']:
            if 't3' in (m['home'], m['away']) and r['round'] > 2:
                assert m['status'] == 'forfeit' and m['awarded_to'] != 't3'
    out = generate('round_robin', 4, withdrawal_policy='void_all', withdrawals=[{'team_id': 't1', 'after_round': 3}])
    assert out['summary']['voided'] == 3
    out = generate('round_robin', 4, withdrawals=[{'team_id': 't1', 'after_round': 3}, {'team_id': 't2', 'after_round': 3}])
    assert out['summary']['voided'] == 1


@pytest.mark.parametrize('n', [2, 3, 5, 6, 8, 17, 128])
def test_single_seed_and_graph(n):
    out = generate('single_elim', n)
    matches = [m for r in out['rounds'] for m in r['matches']]
    assert len(matches) == out['bracket_size'] - 1
    assert sum(m['bye'] for m in out['rounds'][0]['matches']) == out['bracket_size'] - n
    if n == 6:
        assert [(m['home'], m['away']) for m in out['rounds'][0]['matches']] == [('t1', None), ('t4', 't5'), ('t2', None), ('t3', 't6')]
        assert out['rounds'][1]['matches'][0]['home'] == 't1'


def test_result_propagation_and_third_place():
    out = generate('single_elim', 4, third_place_match=True,
                   results=[{'match_id': 'R1M1', 'winner': 't1'}, {'match_id': 'R1M2', 'winner': 't2'}])
    final, tp = out['rounds'][-1]['matches']
    assert (final['home'], final['away']) == ('t1', 't2')
    assert (tp['home'], tp['away']) == ('t4', 't3')


@pytest.mark.parametrize('n', [3, 4, 5, 8, 17, 128])
def test_double_graph(n):
    out = generate('double_elim', n, bracket_reset=True)
    winners = [m for r in out['winners'] for m in r['matches']]
    losers = [m for r in out['losers'] for m in r['matches']]
    assert len(winners) == out['bracket_size'] - 1
    assert len(losers) == out['bracket_size'] - 2
    sources = Counter()
    for m in winners + losers + out['grand_final']:
        if m['bracket'] == 'winners':
            assert m['loser_to']
        if m['bracket'] == 'losers':
            assert m['loser_to'] is None
        for kind in ('winner_to', 'loser_to'):
            if m[kind]:
                sources[m[kind]['match_id'], m[kind]['slot']] += 1
    assert set(sources.values()) == {1}
    assert out['grand_final'][1]['required'] is None


def test_grand_final_reset():
    results = [{'match_id': 'WR1M1', 'winner': 't1'}, {'match_id': 'WR1M2', 'winner': 't2'},
               {'match_id': 'WR2M1', 'winner': 't1'}, {'match_id': 'LR1M1', 'winner': 't3'},
               {'match_id': 'LR2M1', 'winner': 't2'}, {'match_id': 'GF1', 'winner': 't2'}]
    out = generate('double_elim', 4, results=results)
    assert out['grand_final'][1]['required'] is True
    assert out['grand_final'][1]['home'] == out['grand_final'][0]['home']
    results[-1]['winner'] = 't1'
    assert generate('double_elim', 4, results=results)['grand_final'][1]['required'] is False
    assert len(generate('double_elim', 4, bracket_reset=False)['grand_final']) == 1


def test_swiss_exact_first_and_buchholz():
    first = generate('swiss', 5)
    assert first['bye'] == 't5'
    assert [(p['home'], p['away']) for p in first['pairings']] == [('t1', 't3'), ('t2', 't4')]
    history = [{'round': 1, 'bye': 't5', 'matches': [{'home': 't1', 'away': 't3', 'result': 'home'}, {'home': 't2', 'away': 't4', 'result': 'draw'}]}]
    second = generate('swiss', 5, round=2, total_rounds=3, history=history)
    assert second['bye'] == 't3'
    assert [r['team_id'] for r in second['standings']] == ['t1', 't5', 't2', 't4', 't3']
    assert second['standings'][2]['buchholz'] == .5


def all_pairings(teams):
    if not teams:
        yield []
    else:
        a, *rest = teams
        for b in rest:
            for pairs in all_pairings([t for t in rest if t != b]):
                yield [(a, b)] + pairs


def test_swiss_global_optimum_and_performance():
    history = [{'round': 1, 'bye': None, 'matches': [{'home': f't{i}', 'away': f't{i+4}', 'result': 'home' if i % 2 else 'draw'} for i in range(1, 5)]}]
    out = generate('swiss', 8, round=2, history=history)
    scores = {r['team_id']: r['score'] for r in out['standings']}
    prior = {frozenset((m['home'], m['away'])) for m in history[0]['matches']}
    possible = [p for p in all_pairings(list(scores)) if all(frozenset(pair) not in prior for pair in p)]
    assert sum(abs(scores[p['home']] - scores[p['away']]) for p in out['pairings']) == min(sum(abs(scores[a] - scores[b]) for a, b in p) for p in possible)
    history = [{'round': 1, 'bye': None, 'matches': [{'home': f't{i}', 'away': f't{i+32}', 'result': 'draw'} for i in range(1, 33)]}]
    start = time.perf_counter()
    assert len(generate('swiss', 64, round=2, history=history)['pairings']) == 32
    assert time.perf_counter() - start < 5


def test_no_valid_pairing():
    # Remove K3,3 from K6: the remaining graph is two odd triangles.
    # Every participant still has possible opponents, but no perfect matching.
    history = [{'round': r + 1, 'bye': None,
                'matches': [{'home': f't{i+1}', 'away': f't{4 + (i+r)%3}', 'result': 'draw'}
                            for i in range(3)]} for r in range(3)]
    with pytest.raises(DomainError) as exc:
        generate('swiss', 6, round=4, total_rounds=5, history=history)
    assert exc.value.code == 'NO_VALID_PAIRING' and exc.value.details == {'round': 4}


@pytest.mark.parametrize('body', [None, {}, {'format': []}, {'format': 'swiss', 'teams': ['x', 'x']},
    {'format': 'round_robin', 'teams': ['a', 'b'], 'params': {'legs': True}},
    {'format': 'round_robin', 'teams': ['a', 'b'], 'params': {'withdrawals': [{'team_id': 'z', 'after_round': 0}]}},
    {'format': 'single_elim', 'teams': ['a', 'b'], 'params': {'results': [{'match_id': 'bad', 'winner': 'a'}]}},
    {'format': 'single_elim', 'teams': ['a', 'b'], 'params': {'results': [{'match_id': 'R1M1', 'winner': 'z'}]}},
    {'format': 'swiss', 'teams': ['a', 'b'], 'params': {'round': 2}}])
def test_fixture_validation(body):
    with pytest.raises(DomainError) as exc:
        generate_fixtures(body)
    assert exc.value.status == 400
