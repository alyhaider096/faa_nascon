"""Baseline rules are data, never branches in scoring logic."""
from sqlalchemy import delete
from .models import Competition, Event, League, Match, Outbox, ScheduledMatch, Setting, Sport
from .sports import create_sport
from .common import TIE_BREAKS


BASELINE = [
    {'sport_id': 'football', 'name': 'Football', 'scoring_model': 'event',
     'periods': {'count': 2, 'duration_minutes': 45}, 'scoring_events': {'goal': {'points': 1}},
     'draw_allowed': True, 'overtime': {'policy': 'none'},
     'roster': {'min_squad_size': 11, 'max_squad_size': 25, 'required_positions': {'gk': 1}}},
    {'sport_id': 'basketball', 'name': 'Basketball', 'scoring_model': 'event',
     'periods': {'count': 4, 'duration_minutes': 12},
     'scoring_events': {'free_throw': {'points': 1}, 'two_pointer': {'points': 2}, 'three_pointer': {'points': 3}},
     'draw_allowed': False, 'overtime': {'policy': 'extra_time', 'duration_minutes': 5},
     'roster': {'min_squad_size': 5, 'max_squad_size': 15, 'required_positions': {}}},
    {'sport_id': 'cricket', 'name': 'Cricket', 'scoring_model': 'innings',
     'periods': {'innings_per_team': 1, 'overs_per_innings': 20, 'balls_per_over': 6, 'wickets_per_innings': 10},
     'scoring_events': {name: {'runs': runs, 'legal_ball': legal, 'wicket': wicket}
                        for name, runs, legal, wicket in [('dot_ball', 0, True, False), ('single', 1, True, False),
                        ('two', 2, True, False), ('four', 4, True, False), ('six', 6, True, False),
                        ('wide', 1, False, False), ('no_ball', 1, False, False), ('wicket', 0, True, True)]},
     'draw_allowed': True, 'overtime': {'policy': 'super_over'},
     'roster': {'min_squad_size': 11, 'max_squad_size': 18, 'required_positions': {'wicketkeeper': 1}}},
    {'sport_id': 'esports', 'name': 'Esports', 'scoring_model': 'round',
     'periods': {'best_of': 3}, 'scoring_events': {'round_win': {'rounds': 1}},
     'draw_allowed': False, 'overtime': {'policy': 'none'},
     'roster': {'min_squad_size': 5, 'max_squad_size': 8, 'required_positions': {}}},
]


def reset_domain(session, seed=42):
    """Host reset must serialize against all API writers and pause/drain workers.

    This only resets Fatima's fragment; Abdullah resets roster/store/auth/sync too.
    No commit: host reset transaction owns atomicity.
    """
    for model in (Outbox, Event, ScheduledMatch, Competition, Match, League, Sport, Setting):
        session.execute(delete(model))
    session.add(Setting(id='reset', value={'seed': seed}))
    for config in BASELINE:
        create_sport(session, {**config, 'tie_break_order': TIE_BREAKS})
    session.flush()
