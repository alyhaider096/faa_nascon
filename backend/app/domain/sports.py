from copy import deepcopy
import re
from sqlalchemy import select
from .common import DomainError, TIE_BREAKS, integer, invalid, tie_order
from .models import Sport


def validate_sport(body):
    if not isinstance(body, dict):
        invalid('body')
    required = ['sport_id', 'name', 'scoring_model', 'periods', 'scoring_events',
                'draw_allowed', 'overtime', 'roster']
    missing = [k for k in required if k not in body]
    if missing:
        invalid(*missing)
    sport_id, model = body['sport_id'], body['scoring_model']
    if not isinstance(sport_id, str) or not re.fullmatch(r'[a-z0-9_-]{2,40}', sport_id):
        invalid('sport_id')
    if not isinstance(body['name'], str) or not 1 <= len(body['name']) <= 80:
        invalid('name')
    if model not in ('event', 'innings', 'round'):
        invalid('scoring_model')
    periods = body['periods']
    fields = {'event': ['count', 'duration_minutes'], 'innings': ['innings_per_team',
              'overs_per_innings', 'balls_per_over', 'wickets_per_innings'], 'round': ['best_of']}[model]
    if not isinstance(periods, dict) or any(not integer(periods.get(k), 1) for k in fields):
        invalid('periods')
    if model == 'round' and periods['best_of'] % 2 == 0:
        invalid('periods.best_of')
    events = body['scoring_events']
    if not isinstance(events, dict) or not events:
        invalid('scoring_events')
    clean_events = {}
    for name, event in events.items():
        if not isinstance(name, str) or not re.fullmatch(r'[a-z0-9_]{1,40}', name) or not isinstance(event, dict):
            invalid('scoring_events')
        keys = {'event': ['points'], 'innings': ['runs', 'legal_ball', 'wicket'], 'round': ['rounds']}[model]
        if model == 'innings':
            ok = integer(event.get('runs'), 0) and type(event.get('legal_ball')) is bool and type(event.get('wicket')) is bool
        else:
            ok = integer(event.get(keys[0]), 1)
        if not ok:
            invalid('scoring_events.' + name)
        clean_events[name] = {k: event[k] for k in keys}
    if type(body['draw_allowed']) is not bool:
        invalid('draw_allowed')
    overtime, roster = body['overtime'], body['roster']
    if not isinstance(overtime, dict) or overtime.get('policy') not in ('none', 'extra_time', 'shootout', 'golden_score', 'super_over'):
        invalid('overtime')
    if 'duration_minutes' in overtime and not integer(overtime['duration_minutes'], 0):
        invalid('overtime.duration_minutes')
    if not isinstance(roster, dict) or not integer(roster.get('min_squad_size'), 1) or not integer(roster.get('max_squad_size'), 1):
        invalid('roster')
    if roster['min_squad_size'] > roster['max_squad_size']:
        invalid('roster')
    positions = roster.get('required_positions')
    if not isinstance(positions, dict) or any(not isinstance(k, str) or not integer(v, 0) for k, v in positions.items()):
        invalid('roster.required_positions')
    return {'sport_id': sport_id, 'name': body['name'], 'scoring_model': model,
            'periods': {k: periods[k] for k in fields}, 'scoring_events': clean_events,
            'draw_allowed': body['draw_allowed'],
            'overtime': {k: overtime[k] for k in ('policy', 'duration_minutes') if k in overtime},
            'tie_break_order': tie_order(body.get('tie_break_order', TIE_BREAKS)),
            'roster': {k: deepcopy(roster[k]) for k in ('min_squad_size', 'max_squad_size', 'required_positions')}}


def create_sport(session, body):
    config = validate_sport(body)
    from .scoring import lock_key
    lock_key(session, 'sport', config['sport_id'])
    if session.get(Sport, config['sport_id']):
        raise DomainError(409, 'SPORT_EXISTS')
    session.add(Sport(id=config['sport_id'], config=config))
    session.flush()
    return {'sport_id': config['sport_id'], 'status': 'created', 'config': deepcopy(config)}


def sport_config(session, sport_id):
    sport = session.get(Sport, sport_id)
    if not sport:
        raise DomainError(404, 'SPORT_NOT_FOUND')
    return sport.config
