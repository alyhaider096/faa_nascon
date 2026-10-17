import pytest
from backend.app.domain.common import DomainError
from backend.app.domain.scheduling import (configure_competition, reschedule, change_schedule_status,
                                          advance_season, hybrid_knockout, resolve_downstream_slot)


def schedule(**changes):
    return {'venue_id':'v','team_ids':['a','b'],'player_ids':['p'],
            'start':'2026-10-17T10:00:00Z','end':'2026-10-17T11:00:00Z', **changes}


@pytest.mark.parametrize('fmt,details', [('single_stage',{}),('knockout',{}),
    ('multi_division',{'divisions':[{'division_id':'d1','promote':1},{'division_id':'d2','relegate':1}]}),
    ('hybrid',{'stages':[{'format':'round_robin','advance_per_group':2},{'format':'single_elim'}]})])
def test_competitions(session,fmt,details):
    body={'competition_id':'c','season_id':'s','sport_id':'football','format':fmt,**details}
    assert configure_competition(session,'tenant',body)['season_id']=='s'
    with pytest.raises(DomainError) as e:
        configure_competition(session,'foreign',body)
    assert e.value.status==403


def test_conflicts_and_rest(session):
    reschedule(session,'tenant','m1',schedule(min_rest_minutes=30))
    with pytest.raises(DomainError) as e:
        reschedule(session,'tenant','m2',schedule(team_ids=['c','d']))
    assert {c['type'] for c in e.value.details['conflicts']}=={'venue_overlap','player_overlap'}
    with pytest.raises(DomainError) as e:
        reschedule(session,'tenant','m2',schedule(venue_id='other',start='2026-10-17T11:10:00Z',end='2026-10-17T12:00:00Z'))
    assert e.value.details['conflicts'][0]['type']=='minimum_rest'
    with pytest.raises(DomainError) as e:
        reschedule(session,'tenant','m2',schedule(venue_windows=[{'start':'2026-10-17T12:00:00Z','end':'2026-10-17T13:00:00Z'}]))
    assert 'venue_unavailable' in {c['type'] for c in e.value.details['conflicts']}
    with pytest.raises(DomainError) as e:
        reschedule(session,'foreign','m1',schedule())
    assert e.value.status==403


def test_status_postponement_transitive_and_illegal(session):
    reschedule(session,'tenant','m1',schedule())
    reschedule(session,'tenant','m2',schedule(start='2026-10-17T12:00:00Z',end='2026-10-17T13:00:00Z',depends_on=['m1']))
    reschedule(session,'tenant','m3',schedule(start='2026-10-17T14:00:00Z',end='2026-10-17T15:00:00Z',depends_on=['m2']))
    out=change_schedule_status(session,'tenant','m1','postponed')
    assert out['downstream_reevaluation']==['m2','m3']
    with pytest.raises(DomainError) as e:
        change_schedule_status(session,'tenant','m1','completed')
    assert e.value.code=='ILLEGAL_TRANSITION'
    change_schedule_status(session,'tenant','m1','upcoming')
    change_schedule_status(session,'tenant','m1','in_progress')
    change_schedule_status(session,'tenant','m1','completed')
    with pytest.raises(DomainError):
        reschedule(session,'tenant','m1',schedule())


def test_promotion_and_hybrid_advancement(session):
    configure_competition(session,'t',{'competition_id':'c','season_id':'old','sport_id':'football',
        'format':'multi_division','divisions':[{'division_id':'top','relegate':1},{'division_id':'lower','promote':1}]})
    out=advance_season(session,'t','c','new',{'top':['a','b'],'lower':['c','d']})
    assert set(out['division_teams']['top'])=={'a','c'}
    assert set(out['division_teams']['lower'])=={'b','d'}
    configure_competition(session,'t',{'competition_id':'h','season_id':'s','sport_id':'football','format':'hybrid',
        'stages':[{'format':'round_robin','advance_per_group':1},{'format':'single_elim'}]})
    bracket=hybrid_knockout(session,'t','h',[['a','b'],['c','d']])
    assert bracket['rounds'][0]['matches'][0]['home']=='a'
    assert bracket['rounds'][0]['matches'][0]['away']=='c'


def test_resolve_slots(session):
    reschedule(session,'t','final',schedule(depends_on=['semi1','semi2']))
    config=resolve_downstream_slot(session,'t','final',{'semi1':'new1','semi2':'new2'})
    assert config['team_ids']==['new1','new2'] and not config['needs_reevaluation']
