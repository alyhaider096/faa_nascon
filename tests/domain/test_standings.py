import hashlib
import pytest
from backend.app.domain.common import DomainError
from backend.app.domain.scoring import register_league
from backend.app.domain.standings import standings
from test_scoring import emit


def finish(session, sign, mid, home, away, sport_event='goal', discipline=None):
    emit(session, sign, mid, 'match_start')
    for team, amount in [('a',home), ('b',away)]:
        for _ in range(amount):
            emit(session, sign, mid, 'score', {'team_id':team,'event_type':sport_event})
    if discipline:
        emit(session, sign, mid, 'discipline', discipline)
    emit(session, sign, mid, 'match_end')


def test_lots_and_empty_standings(session):
    register_league(session, {'league_id':'lg-1','sport_id':'football','teams':['t1','t2','t3'],
                            'fixtures':[], 'qualification':{'spots':2}})
    out = standings(session,'lg-1')
    assert [r['team_id'] for r in out['table']] == ['t1','t3','t2']
    assert out['h2h']['t1']['t2'] == {'played':0,'points':0,'scored':0,'conceded':0}
    assert all(r['status']=='still_possible' for r in out['table'])
    assert out['table'][0]['resolved_by']=='draw_lots'
    with pytest.raises(DomainError) as e:
        standings(session,'absent')
    assert e.value.code=='LEAGUE_NOT_FOUND'


def test_qualification_and_recompute(session, sign):
    register_league(session, {'league_id':'lg','sport_id':'football','teams':['a','b'],
                            'fixtures':[{'match_id':'m','home':'a','away':'b'}], 'qualification':{'spots':1}})
    emit(session, sign, 'm', 'match_start')
    emit(session, sign, 'm', 'score', {'team_id':'a','event_type':'goal'}, 'g')
    emit(session, sign, 'm', 'discipline', {'team_id':'b','points':-1})
    emit(session, sign, 'm', 'match_end')
    out = standings(session,'lg')
    assert [(r['team_id'],r['points'],r['status']) for r in out['table']] == [('a',3,'clinched'),('b',0,'eliminated')]
    assert out['table'][1]['fair_play'] == -1
    emit(session, sign, 'm','compensation',{'compensates':'g','reason':'review'})
    out = standings(session,'lg')
    assert all(r['drawn']==1 and r['points']==1 and r['status']=='still_possible' for r in out['table'])


def test_three_way_mini_league_and_restart(session, sign):
    fixtures = [{'match_id':'ab','home':'a','away':'b'},{'match_id':'bc','home':'b','away':'c'},
                {'match_id':'ca','home':'c','away':'a'}]
    register_league(session, {'league_id':'lg','sport_id':'football','teams':['a','b','c'],
                            'fixtures':fixtures,'qualification':{'spots':1}})
    for mid,winner,count in [('ab','a',3),('bc','b',2),('ca','c',1)]:
        emit(session,sign,mid,'match_start')
        for i in range(count):
            emit(session,sign,mid,'score',{'team_id':winner,'event_type':'goal'})
        emit(session,sign,mid,'match_end')
    out=standings(session,'lg')
    # All have 3 points. Mini-league diff: a=2,b=-1,c=-1.
    # Re-starting on {b,c} resolves by their head-to-head win, not lots.
    assert [r['team_id'] for r in out['table']]==['a','b','c']
    assert out['table'][0]['resolved_by']=='h2h_diff'
    assert out['table'][1]['resolved_by']=='h2h_points'


def test_nrr_all_out(session,sign):
    register_league(session, {'league_id':'lg','sport_id':'cricket','teams':['a','b'],
                            'fixtures':[{'match_id':'m','home':'a','away':'b'}],'qualification':{'spots':1}})
    emit(session,sign,'m','match_start')
    emit(session,sign,'m','score',{'team_id':'a','event_type':'six'})
    for _ in range(10):
        emit(session,sign,'m','score',{'team_id':'a','event_type':'wicket'})
    emit(session,sign,'m','score',{'team_id':'b','event_type':'single'})
    emit(session,sign,'m','match_end')
    out=standings(session,'lg')
    assert out['table'][0]['team_id']=='a'
    assert out['table'][0]['diff']==-5.7 # 6/20 - 1/(1/6)
