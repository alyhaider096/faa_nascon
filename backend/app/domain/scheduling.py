"""Product scheduling layer, separate from the pure autograder fixture interface.

Host performs role/ownership authorization before calling these tenant-scoped services.
"""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from uuid import uuid4
from sqlalchemy import select
from .common import DomainError, identifier, integer, invalid
from .models import Competition, Outbox, ScheduledMatch
from .scoring import lock_key


def configure_competition(session, tenant_id, body):
    if not identifier(tenant_id) or not isinstance(body, dict):
        invalid('tenant_id', 'body')
    if any(not identifier(body.get(k)) for k in ('competition_id', 'season_id', 'sport_id')):
        invalid('competition_id', 'season_id', 'sport_id')
    if body.get('format') not in ('single_stage', 'multi_division', 'knockout', 'hybrid'):
        invalid('format')
    from .sports import sport_config
    # Validate the whole request before resolving references.
    divisions = body.get('divisions', [])
    stages = body.get('stages', [])
    if not isinstance(divisions, list) or not isinstance(stages, list):
        invalid('divisions', 'stages')
    division_ids = set()
    for division in divisions:
        if not isinstance(division, dict) or not identifier(division.get('division_id')):
            invalid('divisions')
        if division['division_id'] in division_ids:
            invalid('divisions')
        division_ids.add(division['division_id'])
        for key in ('promote', 'relegate'):
            if not integer(division.get(key, 0), 0):
                invalid('divisions.' + key)
    if body['format'] == 'multi_division' and len(divisions) < 2:
        invalid('divisions')
    if body['format'] == 'hybrid':
        if len(stages) < 2 or not all(isinstance(s, dict) for s in stages):
            invalid('stages')
        if stages[0].get('format') != 'round_robin' or stages[-1].get('format') not in ('single_elim', 'double_elim'):
            invalid('stages')
        if not integer(stages[0].get('advance_per_group'), 1):
            invalid('stages.advance_per_group')
    sport_config(session, body['sport_id'])
    lock_key(session, 'competition', body['competition_id'])
    current = session.get(Competition, body['competition_id'])
    if current and current.tenant_id != tenant_id:
        raise DomainError(403, 'FORBIDDEN')
    config = {k: deepcopy(body[k]) for k in ('competition_id', 'season_id', 'sport_id', 'format', 'divisions', 'stages') if k in body}
    if current:
        current.config = config
    else:
        session.add(Competition(id=body['competition_id'], tenant_id=tenant_id, config=config))
    session.flush()
    return config


def utc(value):
    if not isinstance(value, str):
        invalid('timestamp')
    try:
        parsed = datetime.strptime(value, '%Y-%m-%dT%H:%M:%SZ').replace(tzinfo=timezone.utc)
    except ValueError:
        invalid('timestamp')
    if parsed.strftime('%Y-%m-%dT%H:%M:%SZ') != value:
        invalid('timestamp')
    return parsed


def validate_schedule(body):
    if not isinstance(body, dict) or not identifier(body.get('venue_id')):
        invalid('venue_id')
    start, end = utc(body.get('start')), utc(body.get('end'))
    if end <= start:
        invalid('end')
    for key in ('team_ids', 'player_ids', 'depends_on'):
        values = body.get(key, [])
        if not isinstance(values, list) or any(not identifier(v) for v in values) or len(set(values)) != len(values):
            invalid(key)
    if len(body.get('team_ids', [])) != 2 or not integer(body.get('min_rest_minutes', 0), 0):
        invalid('team_ids', 'min_rest_minutes')
    windows = body.get('venue_windows', [])
    if not isinstance(windows, list):
        invalid('venue_windows')
    for window in windows:
        if not isinstance(window, dict) or utc(window.get('end')) <= utc(window.get('start')):
            invalid('venue_windows')
    return deepcopy(body)


def conflicts(session, tenant_id, match_id, config):
    start, end = utc(config['start']), utc(config['end'])
    errors = []
    windows = config.get('venue_windows', [])
    if windows and not any(utc(w['start']) <= start and end <= utc(w['end']) for w in windows):
        errors.append({'type': 'venue_unavailable', 'entity_ids': [config['venue_id']], 'match_ids': [match_id]})
    rows = session.scalars(select(ScheduledMatch).where(ScheduledMatch.tenant_id == tenant_id)).all()
    for row in rows:
        other = row.config
        if row.id == match_id or other.get('status') in ('cancelled', 'abandoned', 'postponed'):
            continue
        a, b = utc(other['start']), utc(other['end'])
        overlap = start < b and a < end
        shared_teams = sorted(set(config['team_ids']) & set(other['team_ids']))
        shared_players = sorted(set(config.get('player_ids', [])) & set(other.get('player_ids', [])))
        if overlap and config['venue_id'] == other['venue_id']:
            errors.append({'type': 'venue_overlap', 'entity_ids': [config['venue_id']], 'match_ids': [match_id, row.id]})
        for kind, ids in [('team_overlap', shared_teams), ('player_overlap', shared_players)]:
            if overlap and ids:
                errors.append({'type': kind, 'entity_ids': ids, 'match_ids': [match_id, row.id]})
        rest = max(config.get('min_rest_minutes', 0), other.get('min_rest_minutes', 0))
        if not overlap and (shared_teams or shared_players) and start < b + timedelta(minutes=rest) and a < end + timedelta(minutes=rest):
            errors.append({'type': 'minimum_rest', 'entity_ids': sorted(set(shared_teams + shared_players)), 'match_ids': [match_id, row.id]})
    return errors


def reschedule(session, tenant_id, match_id, body):
    if not identifier(tenant_id) or not identifier(match_id):
        invalid('tenant_id', 'match_id')
    config = validate_schedule(body)
    # Serialize a tenant's schedule to cover phantom rows sharing venue/players.
    lock_key(session, 'schedule', tenant_id)
    prior = session.get(ScheduledMatch, match_id)
    if prior and prior.tenant_id != tenant_id:
        raise DomainError(403, 'FORBIDDEN')
    if prior and prior.config.get('status') in ('in_progress', 'completed', 'cancelled', 'abandoned'):
        raise DomainError(409, 'ILLEGAL_TRANSITION')
    problems = conflicts(session, tenant_id, match_id, config)
    if problems:
        raise DomainError(409, 'SCHEDULING_CONFLICT', {'conflicts': problems})
    # Product-specific code; no new code is introduced on graded audit routes.
    config['status'] = 'upcoming'
    if prior:
        prior.config = config
    else:
        session.add(ScheduledMatch(id=match_id, tenant_id=tenant_id, config=config))
    session.add(Outbox(id=f'schedule:{uuid4().hex}',
                       payload={'kind': 'match_rescheduled', 'match_id': match_id, 'tenant_id': tenant_id}))
    session.flush()
    return config


TRANSITIONS = {'upcoming': {'in_progress', 'postponed', 'cancelled'},
               'in_progress': {'completed', 'postponed', 'abandoned'},
               'postponed': {'upcoming', 'cancelled'}, 'completed': set(),
               'abandoned': set(), 'cancelled': set()}


def change_schedule_status(session, tenant_id, match_id, status):
    lock_key(session, 'schedule', tenant_id)
    row = session.get(ScheduledMatch, match_id)
    if not row:
        raise DomainError(404, 'MATCH_NOT_FOUND')
    if row.tenant_id != tenant_id:
        raise DomainError(403, 'FORBIDDEN')
    if not isinstance(status, str) or status not in TRANSITIONS:
        invalid('status')
    if status not in TRANSITIONS[row.config['status']]:
        raise DomainError(409, 'ILLEGAL_TRANSITION')
    if status in ('upcoming', 'in_progress'):
        problems = conflicts(session, tenant_id, match_id, row.config)
        if problems:
            raise DomainError(409, 'SCHEDULING_CONFLICT', {'conflicts': problems})
    row.config = {**row.config, 'status': status}
    affected = []
    if status == 'postponed':
        pending = {match_id}
        for candidate in session.scalars(select(ScheduledMatch).where(ScheduledMatch.tenant_id == tenant_id)):
            if candidate.id == match_id:
                continue
            affected.append(candidate)
        changed = True
        while changed:
            changed = False
            for candidate in affected:
                if candidate.id not in pending and pending.intersection(candidate.config.get('depends_on', [])):
                    candidate.config = {**candidate.config, 'needs_reevaluation': True, 'resolved_slots': {},
                                        'conflicts': conflicts(session, tenant_id, candidate.id, candidate.config)}
                    pending.add(candidate.id)
                    changed = True
        affected = sorted(pending - {match_id})
    session.add(Outbox(id=f'status:{uuid4().hex}',
                       payload={'kind': 'match_status_changed', 'match_id': match_id, 'status': status,
                                'tenant_id': tenant_id, 'downstream_reevaluation': affected}))
    session.flush()
    return {'match_id': match_id, 'status': status, 'downstream_reevaluation': affected}


def advance_season(session, tenant_id, competition_id, next_season_id, ranked_divisions):
    """Apply configured promotion/relegation, highest division first.

    Host supplies finalized standings from the domain engine, not client assertions.
    The previous season's configuration is retained in the same immutable snapshot.
    """
    if not identifier(next_season_id) or not isinstance(ranked_divisions, dict):
        invalid('next_season_id', 'ranked_divisions')
    lock_key(session, 'competition', competition_id)
    row = session.get(Competition, competition_id)
    if not row:
        raise DomainError(404, 'LEAGUE_NOT_FOUND')
    if row.tenant_id != tenant_id:
        raise DomainError(403, 'FORBIDDEN')
    divisions = row.config.get('divisions', [])
    if row.config['format'] != 'multi_division' or set(ranked_divisions) != {d['division_id'] for d in divisions}:
        invalid('ranked_divisions')
    output = {d['division_id']: [] for d in divisions}
    seen = set()
    for index, division in enumerate(divisions):
        ranked = ranked_divisions[division['division_id']]
        if not isinstance(ranked, list) or not ranked or any(not identifier(t) for t in ranked):
            invalid('ranked_divisions')
        if len(set(ranked)) != len(ranked) or seen.intersection(ranked):
            invalid('ranked_divisions')
        seen.update(ranked)
        promote, relegate = division.get('promote', 0), division.get('relegate', 0)
        if promote + relegate > len(ranked) or (index == 0 and promote) or (index == len(divisions) - 1 and relegate):
            invalid('divisions.promote', 'divisions.relegate')
        for position, team in enumerate(ranked):
            target = index - 1 if position < promote else index + 1 if position >= len(ranked) - relegate else index
            output[divisions[target]['division_id']].append(team)
    snapshot = {'season_id': row.config['season_id'], 'ranked_divisions': deepcopy(ranked_divisions)}
    row.config = {**row.config, 'season_id': next_season_id, 'division_teams': output,
                  'season_history': [*row.config.get('season_history', []), snapshot]}
    session.flush()
    return {'season_id': next_season_id, 'division_teams': output}


def hybrid_knockout(session, tenant_id, competition_id, group_rankings):
    """Seed by finish position, then supplied group order; no score-name logic."""
    row = session.get(Competition, competition_id)
    if not row:
        raise DomainError(404, 'LEAGUE_NOT_FOUND')
    if row.tenant_id != tenant_id:
        raise DomainError(403, 'FORBIDDEN')
    if row.config['format'] != 'hybrid' or not isinstance(group_rankings, list) or not group_rankings:
        invalid('group_rankings')
    take = row.config['stages'][0]['advance_per_group']
    for group in group_rankings:
        if not isinstance(group, list) or len(group) < take or any(not identifier(t) for t in group):
            invalid('group_rankings')
    all_teams = [t for group in group_rankings for t in group]
    if len(set(all_teams)) != len(all_teams):
        invalid('group_rankings')
    seeded = [group[position] for position in range(take) for group in group_rankings]
    from .fixtures import generate_fixtures
    stage = row.config['stages'][-1]
    return generate_fixtures({'format': stage['format'], 'teams': seeded, 'params': stage.get('params', {})})


def resolve_downstream_slot(session, tenant_id, match_id, upstream_winners):
    """Rebuild invalidated bracket slots using authoritative upstream winners."""
    lock_key(session, 'schedule', tenant_id)
    row = session.get(ScheduledMatch, match_id)
    if not row:
        raise DomainError(404, 'MATCH_NOT_FOUND')
    if row.tenant_id != tenant_id:
        raise DomainError(403, 'FORBIDDEN')
    dependencies = row.config.get('depends_on', [])
    if not isinstance(upstream_winners, dict) or set(upstream_winners) != set(dependencies) or any(not identifier(t) for t in upstream_winners.values()):
        invalid('upstream_winners')
    config = {**row.config, 'resolved_slots': deepcopy(upstream_winners), 'needs_reevaluation': False}
    if len(dependencies) == 2:
        config['team_ids'] = [upstream_winners[d] for d in dependencies]
        if config['team_ids'][0] == config['team_ids'][1]:
            invalid('upstream_winners')
    problems = conflicts(session, tenant_id, match_id, config)
    if problems:
        raise DomainError(409, 'SCHEDULING_CONFLICT', {'conflicts': problems})
    row.config = config
    session.add(Outbox(id=f'slots:{uuid4().hex}', payload={'kind': 'bracket_slots_resolved', 'match_id': match_id,
                                                        'tenant_id': tenant_id}))
    session.flush()
    return config
