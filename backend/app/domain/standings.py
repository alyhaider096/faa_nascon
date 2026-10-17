import hashlib
from .common import DomainError, tie_order
from .models import League
from .scoring import project_score
from .sports import sport_config


def standings(session, league_id):
    league = session.get(League, league_id)
    if not league:
        raise DomainError(404, 'LEAGUE_NOT_FOUND')
    config, sport = league.config, sport_config(session, league.sport_id)
    teams, weights = config['teams'], config['points']
    games = [project_score(session, f['match_id']) for f in config['fixtures']]
    finished = [g for g in games if g['status'] == 'completed' and g['outcome'] != 'undecided']
    table = {t: {'rank': 0, 'team_id': t, 'played': 0, 'won': 0, 'drawn': 0, 'lost': 0,
                 'scored': 0, 'conceded': 0, 'diff': 0, 'points': 0, 'fair_play': 0,
                 'status': 'still_possible', 'resolved_by': None} for t in teams}
    h2h = {a: {b: {'played': 0, 'points': 0, 'scored': 0, 'conceded': 0} for b in teams if b != a} for a in teams}

    def differential(team, subset):
        relevant = [(g['home'], g['away']) if g['home']['team_id'] == team else (g['away'], g['home'])
                    for g in subset if team in (g['home']['team_id'], g['away']['team_id'])]
        if sport['scoring_model'] != 'innings':
            return sum(a['score'] - b['score'] for a, b in relevant)
        p = sport['periods']
        def overs(side):
            return p['overs_per_innings'] if side['wickets'] >= p['wickets_per_innings'] else side['balls'] / p['balls_per_over']
        runs = sum(a['score'] for a, b in relevant)
        conceded = sum(b['score'] for a, b in relevant)
        faced = sum(overs(a) for a, b in relevant)
        bowled = sum(overs(b) for a, b in relevant)
        return round((runs / faced if faced else 0) - (conceded / bowled if bowled else 0), 3)

    for game in finished:
        for side, opp in ((game['home'], game['away']), (game['away'], game['home'])):
            t, opponent = side['team_id'], opp['team_id']
            row, pair = table[t], h2h[t][opponent]
            result = 'draw' if game['outcome'] == 'draw' else 'win' if game['winner_team_id'] == t else 'loss'
            row['played'] += 1
            row[{'win': 'won', 'draw': 'drawn', 'loss': 'lost'}[result]] += 1
            row['points'] += weights[result]
            row['scored'] += side['score']
            row['conceded'] += opp['score']
            row['fair_play'] += side['fair_play']
            pair['played'] += 1
            pair['points'] += weights[result]
            pair['scored'] += side['score']
            pair['conceded'] += opp['score']
    for t in teams:
        table[t]['diff'] = differential(t, finished)
    order = tie_order(config['tie_break_order'])

    def lots(t):
        return hashlib.sha256(f"{config['lots_seed']}|{league_id}|{t}".encode('utf-8')).hexdigest()

    def resolve(group):
        if len(group) < 2:
            return group
        subset = [g for g in finished if g['home']['team_id'] in group and g['away']['team_id'] in group]
        for criterion in order:
            if criterion == 'draw_lots':
                ordered = sorted(group, key=lots)
                for t in ordered[:-1]:
                    table[t]['resolved_by'] = criterion
                return ordered
            values = {}
            for t in group:
                values[t] = (sum(h2h[t][o]['points'] for o in group if o != t) if criterion == 'h2h_points'
                             else differential(t, subset) if criterion == 'h2h_diff'
                             else table[t][{'overall_diff': 'diff', 'scored': 'scored', 'fair_play': 'fair_play'}[criterion]])
            distinct = sorted(set(values.values()), reverse=True)
            if len(distinct) > 1:
                output = []
                for i, value in enumerate(distinct):
                    subgroup = resolve([t for t in group if values[t] == value])
                    if i < len(distinct) - 1:
                        table[subgroup[-1]]['resolved_by'] = criterion
                    output.extend(subgroup)
                return output
        return group

    ranked = []
    for points in sorted({table[t]['points'] for t in teams}, reverse=True):
        ranked.extend(resolve([t for t in teams if table[t]['points'] == points]))
    remaining = {t: sum(t in (g['home']['team_id'], g['away']['team_id']) for g in games if g not in finished) for t in teams}
    maximum = {t: table[t]['points'] + weights['win'] * remaining[t] for t in teams}
    spots = config['qualification']['spots']
    for rank, t in enumerate(ranked, 1):
        row = table[t]
        row['rank'] = rank
        if sum(maximum[o] >= row['points'] for o in teams if o != t) < spots:
            row['status'] = 'clinched'
        elif sum(table[o]['points'] > maximum[t] for o in teams if o != t) >= spots:
            row['status'] = 'eliminated'
    return {'league_id': league_id, 'sport_id': league.sport_id, 'qualification_spots': spots,
            'table': [table[t] for t in ranked], 'h2h': h2h}
