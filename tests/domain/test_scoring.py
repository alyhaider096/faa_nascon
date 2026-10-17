from copy import deepcopy
import hashlib
import hmac
import pytest
from sqlalchemy import select
from backend.app.domain.common import DomainError, canonical, signer
from backend.app.domain.models import Event, Match, Outbox, Sport
from backend.app.domain.scoring import append_event, project_score, register_league, get_match_version
from backend.app.domain.sports import create_sport
from backend.app.domain.seeds import reset_domain, BASELINE


def emit(session, sign, mid, type_, payload=None, id_=None):
    id_ = id_ or f'{mid}-{len(session.scalars(select(Event)).all()) + 1}'
    return append_event(session, {'event_id': id_, 'match_id': mid, 'type': type_, 'payload': payload or {}}, sign)


def init(session, sign, sport='football', mid='m'):
    emit(session, sign, mid, 'match_init', {'sport_id': sport, 'home_team_id': 'a', 'away_team_id': 'b'})
    emit(session, sign, mid, 'match_start')


def test_signature_vector_and_unicode(sign):
    assert sign('evt-1', {'team_id': 't1', 'event_type': 'goal'}) == '972a8b558690b19121cc5bea84978f85e8eb15a3735018db36616bab1d7ec501'
    payload = {'z': [3, {'é': True, 'a': None}], 'a': 'پاکستان'}
    expected = hmac.new(b'demo-salt', ('id|' + canonical(payload)).encode('utf-8'), hashlib.sha256).hexdigest()
    assert sign('id', payload) == expected
    assert sign('id', dict(reversed(list(payload.items())))) == expected
    assert signer('other')('id', payload) != expected
    with pytest.raises(ValueError):
        signer('')


def test_mystery_sport_compensation_replay_and_log_immutability(session, sign):
    config = deepcopy(BASELINE[0])
    config.update(sport_id='mystery', name='Mystery', scoring_events={'zap': {'points': 7}})
    create_sport(session, config)
    init(session, sign, 'mystery')
    request = {'event_id': 'e', 'match_id': 'm', 'type': 'score', 'payload': {'team_id': 'a', 'event_type': 'zap'}}
    status, response = append_event(session, request, sign)
    assert status == 201
    emit(session, sign, 'm', 'discipline', {'team_id': 'b', 'points': -3}, 'd')
    emit(session, sign, 'm', 'match_end')
    original = deepcopy(session.get(Event, 'e').payload)
    emit(session, sign, 'm', 'compensation', {'compensates': 'e', 'reason': 'review'}, 'c')
    score = project_score(session, 'm')
    assert score['home']['score'] == 0 and score['away']['fair_play'] == -3
    assert score['outcome'] == 'draw'
    assert session.get(Event, 'e').payload == original
    assert score['events'][2]['compensated'] and score['events'][2]['compensated_by'] == 'c'
    assert append_event(session, request, sign) == (200, response)
    assert all(e['signature'] == sign(e['event_id'], e['payload']) for e in score['events'])
    assert len(session.scalars(select(Outbox)).all()) == score['version']
    assert get_match_version(session, 'm', lock=True) == score['version']
    with pytest.raises(DomainError, match='Duplicate event id'):
        append_event(session, {**request, 'payload': {'team_id': 'b', 'event_type': 'zap'}}, sign)
    with pytest.raises(DomainError) as e:
        emit(session, sign, 'm', 'compensation', {'compensates': 'e', 'reason': 'again'})
    assert e.value.code == 'INVALID_COMPENSATION'


def test_innings_limit_and_compensation(session, sign):
    config = deepcopy(BASELINE[2])
    config.update(sport_id='short', name='Short')
    config['periods'].update(overs_per_innings=1, balls_per_over=2, wickets_per_innings=1)
    create_sport(session, config)
    init(session, sign, 'short')
    emit(session, sign, 'm', 'score', {'team_id': 'a', 'event_type': 'wide'}, 'wide')
    emit(session, sign, 'm', 'score', {'team_id': 'a', 'event_type': 'six'}, 'six')
    p = project_score(session, 'm')['home']
    assert (p['score'], p['balls'], p['overs']) == (7, 1, '0.1')
    emit(session, sign, 'm', 'score', {'team_id': 'a', 'event_type': 'wicket'}, 'out')
    with pytest.raises(DomainError) as e:
        emit(session, sign, 'm', 'score', {'team_id': 'a', 'event_type': 'wide'})
    assert e.value.code == 'INNINGS_COMPLETE'
    emit(session, sign, 'm', 'compensation', {'compensates': 'out', 'reason': 'review'})
    emit(session, sign, 'm', 'score', {'team_id': 'a', 'event_type': 'single'})
    assert project_score(session, 'm')['home']['overs'] == '1.0'


def test_round_limit_and_tiebreak_compensation(session, sign):
    init(session, sign, 'esports')
    for _ in range(2):
        emit(session, sign, 'm', 'score', {'team_id': 'a', 'event_type': 'round_win'})
    with pytest.raises(DomainError) as e:
        emit(session, sign, 'm', 'score', {'team_id': 'b', 'event_type': 'round_win'})
    assert e.value.code == 'SERIES_ALREADY_DECIDED'
    init(session, sign, 'basketball', 'tie')
    with pytest.raises(DomainError) as e:
        emit(session, sign, 'tie', 'match_end')
    assert e.value.code == 'TIE_NOT_ALLOWED'
    emit(session, sign, 'tie', 'tiebreak_winner', {'team_id': 'b'}, 'tb')
    emit(session, sign, 'tie', 'match_end')
    assert project_score(session, 'tie')['winner_team_id'] == 'b'
    emit(session, sign, 'tie', 'compensation', {'compensates': 'tb', 'reason': 'review'})
    assert project_score(session, 'tie')['outcome'] == 'undecided'


@pytest.mark.parametrize('type_,payload,code', [
    ('match_start', {}, 'ILLEGAL_TRANSITION'), ('match_init', {'sport_id':'football','home_team_id':'a','away_team_id':'b'}, 'MATCH_EXISTS'),
    ('score', {'team_id':'a','event_type':'unknown'}, 'UNKNOWN_EVENT_TYPE'),
    ('score', {'team_id':'z','event_type':'goal'}, 'VALIDATION_ERROR'),
    ('compensation', {'compensates':'unknown','reason':'x'}, 'EVENT_NOT_FOUND'),
    ('compensation', {'compensates':'m-1','reason':'x'}, 'INVALID_COMPENSATION')])
def test_event_errors(session, sign, type_, payload, code):
    init(session, sign)
    with pytest.raises(DomainError) as e:
        emit(session, sign, 'm', type_, payload)
    assert e.value.code == code


@pytest.mark.parametrize('body', [None, {}, {'event_id':True,'match_id':'m','type':'score','payload':{}},
    {'event_id':'x','match_id':'m','type':[], 'payload':{}},
    {'event_id':'x','match_id':'m','type':'discipline', 'payload':{'team_id':'a','points':True}},
    {'event_id':'x','match_id':'m','type':'match_init','payload':{'sport_id':'football','home_team_id':'a','away_team_id':'a'}}])
def test_event_schema_errors(session, sign, body):
    with pytest.raises(DomainError) as e:
        append_event(session, body, sign)
    assert e.value.status == 400


def league_body(**kw):
    return {'league_id':'lg', 'sport_id':'football','teams':['a','b'],
            'fixtures':[{'match_id':'m','home':'a','away':'b'}], 'qualification':{'spots':1}, **kw}


def test_league_registration_and_reset(session, sign):
    assert register_league(session, league_body())['fixture_count'] == 1
    assert project_score(session, 'm')['version'] == 0
    assert project_score(session, 'm')['status'] == 'upcoming'
    emit(session, sign, 'm', 'match_start')
    with pytest.raises(DomainError) as e:
        register_league(session, league_body())
    assert e.value.code == 'LEAGUE_EXISTS'
    reset_domain(session, 73)
    assert session.scalars(select(Event)).all() == []
    assert session.scalars(select(Match)).all() == []
    before = [(s.id, deepcopy(s.config)) for s in session.scalars(select(Sport).order_by(Sport.id))]
    reset_domain(session, 73)
    assert before == [(s.id, s.config) for s in session.scalars(select(Sport).order_by(Sport.id))]


@pytest.mark.parametrize('change,code', [({'teams':['a','a']}, 'VALIDATION_ERROR'),
    ({'sport_id':'missing'}, 'SPORT_NOT_FOUND'), ({'qualification': {'spots':0}}, 'VALIDATION_ERROR'),
    ({'points': {'win':True,'draw':1,'loss':0}}, 'VALIDATION_ERROR'),
    ({'fixtures':[{'match_id':'m','home':'a','away':'a'}]}, 'VALIDATION_ERROR')])
def test_league_errors(session, change, code):
    with pytest.raises(DomainError) as e:
        register_league(session, league_body(**change))
    assert e.value.code == code


@pytest.mark.parametrize('change', [ {'sport_id':"x'; DROP TABLE sports;--"}, {'scoring_model':[]}, {'name':''},
    {'periods':{'count':True,'duration_minutes':1}}, {'draw_allowed':1}, {'scoring_events':{}},
    {'overtime':{'policy':'bad'}}, {'roster':{'min_squad_size':4,'max_squad_size':2,'required_positions':{}}},
    {'tie_break_order':['scored','scored']}])
def test_sport_schema(session, change):
    with pytest.raises(DomainError) as e:
        create_sport(session, {**deepcopy(BASELINE[0]), **change})
    assert e.value.status == 400


def test_missing_resources_and_state(session, sign):
    for f in (lambda: project_score(session,'absent'), lambda: get_match_version(session,'absent'),
              lambda: emit(session, sign,'absent','match_start')):
        with pytest.raises(DomainError) as e:
            f()
        assert e.value.code == 'MATCH_NOT_FOUND'
    emit(session, sign,'m','match_init', {'sport_id':'football','home_team_id':'a','away_team_id':'b'})
    with pytest.raises(DomainError) as e:
        emit(session, sign,'m','score',{'team_id':'a','event_type':'goal'})
    assert e.value.code == 'MATCH_NOT_IN_PROGRESS'
