"""Transactional append-only streams and their deterministic projections."""
from copy import deepcopy
import hashlib
from sqlalchemy import select, text
from .common import DomainError, canonical, identifier, integer, invalid, tie_order
from .models import Event, League, Match, Outbox, Setting
from .sports import sport_config


def lock_key(session, namespace, id_):
    """Postgres transaction locks also cover resources not created yet.

    SQLite is for sequential unit tests only, not proof of PostgreSQL concurrency.
    """
    if session.bind.dialect.name == 'postgresql':
        key = int.from_bytes(hashlib.sha256((namespace + ':' + id_).encode()).digest()[:8], 'big', signed=True)
        session.execute(text('SELECT pg_advisory_xact_lock(:key)'), {'key': key})


def register_league(session, body):
    if not isinstance(body, dict):
        invalid('body')
    for k in ('league_id', 'sport_id'):
        if not identifier(body.get(k)):
            invalid(k)
    teams, fixtures = body.get('teams'), body.get('fixtures')
    if not isinstance(teams, list) or not 2 <= len(teams) <= 40 or any(not identifier(t) for t in teams):
        invalid('teams')
    if len(set(teams)) != len(teams) or not isinstance(fixtures, list):
        invalid('teams', 'fixtures')
    ids = []
    clean_fixtures = []
    for fixture in fixtures:
        if not isinstance(fixture, dict) or not identifier(fixture.get('match_id')):
            invalid('fixtures')
        a, b = fixture.get('home'), fixture.get('away')
        if a not in teams or b not in teams or a == b:
            invalid('fixtures')
        ids.append(fixture['match_id'])
        clean_fixtures.append({k: fixture[k] for k in ('match_id', 'home', 'away')})
    if len(set(ids)) != len(ids):
        invalid('fixtures.match_id')
    points = body.get('points', {'win': 3, 'draw': 1, 'loss': 0})
    if not isinstance(points, dict) or any(not integer(points.get(k)) for k in ('win', 'draw', 'loss')):
        invalid('points')
    qualification = body.get('qualification')
    if not isinstance(qualification, dict) or not integer(qualification.get('spots'), 1, len(teams)):
        invalid('qualification.spots')
    if 'lots_seed' in body and not integer(body['lots_seed']):
        invalid('lots_seed')
    if 'tie_break_order' in body:
        tie_order(body['tie_break_order'])
    config = sport_config(session, body['sport_id'])
    lock_key(session, 'league', body['league_id'])
    if session.get(League, body['league_id']):
        raise DomainError(409, 'LEAGUE_EXISTS')
    for id_ in sorted(ids):
        lock_key(session, 'match', id_)
        if session.get(Match, id_):
            raise DomainError(409, 'MATCH_EXISTS')
    setting = session.get(Setting, 'reset')
    seed = setting.value['seed'] if setting else 42
    stored = {'teams': teams, 'fixtures': clean_fixtures, 'points': {k: points[k] for k in ('win', 'draw', 'loss')},
              'tie_break_order': tie_order(body.get('tie_break_order', config['tie_break_order'])),
              'qualification': {'spots': qualification['spots']}, 'lots_seed': body.get('lots_seed', seed)}
    session.add(League(id=body['league_id'], sport_id=body['sport_id'], config=deepcopy(stored)))
    session.flush()
    session.add_all(Match(id=f['match_id'], sport_id=body['sport_id'], league_id=body['league_id'],
                          home=f['home'], away=f['away']) for f in clean_fixtures)
    session.flush()
    return {'league_id': body['league_id'], 'status': 'created', 'team_count': len(teams), 'fixture_count': len(fixtures)}


EVENT_FIELDS = {'match_init': ('sport_id', 'home_team_id', 'away_team_id'), 'match_start': (),
                'score': ('team_id', 'event_type'), 'discipline': ('team_id', 'points'),
                'tiebreak_winner': ('team_id',), 'match_end': (), 'compensation': ('compensates', 'reason')}


def validate_event(body):
    if not isinstance(body, dict):
        invalid('body')
    for k in ('event_id', 'match_id'):
        if not identifier(body.get(k)):
            invalid(k)
    type_, payload = body.get('type'), body.get('payload')
    if not isinstance(type_, str) or type_ not in EVENT_FIELDS or not isinstance(payload, dict):
        invalid('type', 'payload')
    for k in EVENT_FIELDS[type_]:
        if k not in payload:
            invalid('payload.' + k)
        if k == 'points':
            ok = integer(payload[k])
        elif k == 'reason':
            ok = isinstance(payload[k], str)
        elif k == 'event_type':
            ok = isinstance(payload[k], str)
        else:
            ok = identifier(payload[k])
        if not ok:
            invalid('payload.' + k)
    if type_ == 'match_init':
        if payload['home_team_id'] == payload['away_team_id']:
            invalid('payload.away_team_id')
        if payload.get('league_id') is not None and not identifier(payload['league_id']):
            invalid('payload.league_id')
    # Only the outer contract fields form the event identity. The entire payload
    # is kept verbatim: the signature recipe explicitly signs request.payload.
    try:
        canonical(payload)
    except (ValueError, TypeError):
        invalid('payload')
    return {k: deepcopy(body[k]) for k in ('event_id', 'match_id', 'type', 'payload')}


def event_response(event):
    return {'event_id': event.id, 'match_id': event.match_id, 'type': event.type,
            'sequence': event.sequence, 'match_version': event.sequence, 'signature': event.signature}


def get_match_version(session, match_id, lock=False):
    if lock:
        lock_key(session, 'match', match_id)
    match = session.get(Match, match_id)
    if not match:
        raise DomainError(404, 'MATCH_NOT_FOUND')
    return len(session.scalars(select(Event).where(Event.match_id == match_id)).all())


def append_event(session, body, sign_record):
    request = validate_event(body)
    id_, mid, type_, payload = (request[k] for k in ('event_id', 'match_id', 'type', 'payload'))
    # Consistent global-event then match lock ordering avoids duplicate-ID races.
    lock_key(session, 'event', id_)
    prior = session.get(Event, id_)
    if prior:
        if canonical(prior.request) != canonical(request):
            raise DomainError(409, 'DUPLICATE_EVENT_ID')
        return 200, event_response(prior)
    lock_key(session, 'match', mid)
    match = session.get(Match, mid)
    if type_ == 'match_init':
        config = sport_config(session, payload['sport_id'])
        if payload.get('league_id') and not session.get(League, payload['league_id']):
            raise DomainError(404, 'LEAGUE_NOT_FOUND')
        if match:
            raise DomainError(409, 'MATCH_EXISTS')
        match = Match(id=mid, sport_id=config['sport_id'], league_id=payload.get('league_id'),
                      home=payload['home_team_id'], away=payload['away_team_id'])
        session.add(match)
        session.flush()
    elif not match:
        raise DomainError(404, 'MATCH_NOT_FOUND')
    config = sport_config(session, match.sport_id)
    projection = project_score(session, mid)
    if type_ in ('score', 'discipline', 'tiebreak_winner') and payload['team_id'] not in (match.home, match.away):
        invalid('payload.team_id')
    if type_ == 'score' and payload['event_type'] not in config['scoring_events']:
        raise DomainError(400, 'UNKNOWN_EVENT_TYPE')
    target = None
    if type_ == 'compensation':
        target = session.get(Event, payload['compensates'])
        if not target:
            raise DomainError(404, 'EVENT_NOT_FOUND')
    status = projection['status']
    if type_ == 'match_start' and status != 'upcoming':
        raise DomainError(409, 'ILLEGAL_TRANSITION')
    if type_ in ('score', 'discipline', 'tiebreak_winner') and status != 'in_progress':
        raise DomainError(409, 'MATCH_NOT_IN_PROGRESS')
    if type_ == 'match_end':
        if status != 'in_progress':
            raise DomainError(409, 'ILLEGAL_TRANSITION')
        if projection['home']['score'] == projection['away']['score'] and not config['draw_allowed'] and not projection['tiebreak_winner_team_id']:
            raise DomainError(409, 'TIE_NOT_ALLOWED')
    if type_ == 'compensation':
        targeted = any(e['type'] == 'compensation' and e['payload']['compensates'] == target.id for e in projection['events'])
        if target.match_id != mid or target.type not in ('score', 'discipline', 'tiebreak_winner') or targeted:
            raise DomainError(409, 'INVALID_COMPENSATION')
    if type_ == 'score':
        periods, model = config['periods'], config['scoring_model']
        side = projection['home'] if payload['team_id'] == match.home else projection['away']
        if model == 'innings' and (side['balls'] >= periods['innings_per_team'] * periods['overs_per_innings'] * periods['balls_per_over'] or
                                  side['wickets'] >= periods['innings_per_team'] * periods['wickets_per_innings']):
            raise DomainError(409, 'INNINGS_COMPLETE')
        if model == 'round' and max(projection['home']['score'], projection['away']['score']) >= (periods['best_of'] + 1) // 2:
            raise DomainError(409, 'SERIES_ALREADY_DECIDED')
    event = Event(id=id_, match_id=mid, sequence=projection['version'] + 1, type=type_,
                  payload=deepcopy(payload), request=request, signature=sign_record(id_, payload))
    session.add(event)
    session.add(Outbox(id=id_, payload={'kind': 'match_updated', 'match_id': mid, 'event_id': id_,
                                      'version': event.sequence}))
    session.flush()
    return 201, event_response(event)


def project_score(session, match_id):
    match = session.get(Match, match_id)
    if not match:
        raise DomainError(404, 'MATCH_NOT_FOUND')
    config = sport_config(session, match.sport_id)
    model, periods = config['scoring_model'], config['periods']
    events = session.scalars(select(Event).where(Event.match_id == match_id).order_by(Event.sequence)).all()
    compensated = {e.payload['compensates']: e.id for e in events if e.type == 'compensation'}
    def side(team):
        return {'team_id': team, 'score': 0, 'wickets': 0 if model == 'innings' else None,
                'balls': 0 if model == 'innings' else None, 'overs': '0.0' if model == 'innings' else None, 'fair_play': 0}
    home, away = side(match.home), side(match.away)
    status, tiebreak = 'upcoming', None
    for event in events:
        if event.id in compensated or event.type == 'compensation':
            continue
        payload = event.payload
        team = home if payload.get('team_id') == match.home else away
        if event.type == 'match_start':
            status = 'in_progress'
        elif event.type == 'match_end':
            status = 'completed'
        elif event.type == 'tiebreak_winner':
            tiebreak = payload['team_id']
        elif event.type == 'discipline':
            team['fair_play'] += payload['points']
        elif event.type == 'score':
            rule = config['scoring_events'][payload['event_type']]
            if model == 'event':
                team['score'] += rule['points']
            elif model == 'round':
                team['score'] += rule['rounds']
            else:
                team['score'] += rule['runs']
                team['balls'] += int(rule['legal_ball'])
                team['wickets'] += int(rule['wicket'])
                bpo = periods['balls_per_over']
                team['overs'] = f"{team['balls'] // bpo}.{team['balls'] % bpo}"
    winner = match.home if home['score'] > away['score'] else match.away if away['score'] > home['score'] else tiebreak
    outcome = 'pending'
    if status == 'completed':
        outcome = 'home_win' if winner == match.home else 'away_win' if winner == match.away else 'draw' if config['draw_allowed'] else 'undecided'
    return {'match_id': match.id, 'sport_id': match.sport_id, 'league_id': match.league_id,
            'status': status, 'outcome': outcome, 'winner_team_id': winner, 'tiebreak_winner_team_id': tiebreak,
            'home': home, 'away': away, 'version': len(events),
            'events': [{'sequence': e.sequence, 'event_id': e.id, 'type': e.type, 'payload': deepcopy(e.payload),
                        'signature': e.signature, 'compensated': e.id in compensated,
                        'compensated_by': compensated.get(e.id)} for e in events]}
