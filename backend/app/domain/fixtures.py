"""Custom tournament construction; general graph matching only for Swiss optimization."""
import math
import networkx as nx
from .common import DomainError, identifier, integer, invalid


def generate_fixtures(body):
    if not isinstance(body, dict):
        invalid('body')
    fmt, teams, params = body.get('format'), body.get('teams'), body.get('params', {})
    if fmt not in ('round_robin', 'swiss', 'single_elim', 'double_elim'):
        invalid('format')
    lo, hi = {'round_robin': (2, 40), 'swiss': (2, 64), 'single_elim': (2, 128), 'double_elim': (3, 128)}[fmt]
    if not isinstance(teams, list) or not lo <= len(teams) <= hi or any(not identifier(t) for t in teams):
        invalid('teams')
    if len(set(teams)) != len(teams) or not isinstance(params, dict):
        invalid('teams', 'params')
    if fmt == 'round_robin':
        return round_robin(teams, params)
    if fmt == 'swiss':
        return swiss(teams, params)
    return elimination(teams, params, fmt == 'double_elim')


def round_robin(teams, params):
    legs = params.get('legs', 1)
    if not integer(legs, 1, 2):
        invalid('params.legs')
    ring = list(teams) + ([None] if len(teams) % 2 else [])
    per_leg = len(ring) - 1
    policy = params.get('withdrawal_policy', 'forfeit_remaining')
    withdrawals = params.get('withdrawals', [])
    if policy not in ('void_all', 'forfeit_remaining') or not isinstance(withdrawals, list):
        invalid('params.withdrawals', 'params.withdrawal_policy')
    withdrawn = {}
    for w in withdrawals:
        if not isinstance(w, dict) or w.get('team_id') not in teams or not integer(w.get('after_round'), 0, per_leg * legs):
            invalid('params.withdrawals')
        if w['team_id'] in withdrawn:
            invalid('params.withdrawals')
        withdrawn[w['team_id']] = w['after_round']
    rounds, summary = [], {'total': 0, 'scheduled': 0, 'forfeit': 0, 'voided': 0}
    first_leg = []
    for r in range(per_leg):
        pairs, byes = [], []
        for i in range(len(ring) // 2):
            a, b = ring[i], ring[-i - 1]
            if a is None or b is None:
                byes.append(a or b)
            else:
                # Orient a regular cyclic tournament, then attach the extra
                # participant for even fields. Removing a dummy bye from an
                # even-field orientation would unbalance odd fields by two.
                ai, bi, n = teams.index(a), teams.index(b), len(teams)
                if n % 2:
                    a_home = 0 < (bi - ai) % n <= n // 2
                elif ai == n - 1 or bi == n - 1:
                    other = bi if ai == n - 1 else ai
                    a_home = (ai == n - 1) == (other % 2 == 0)
                else:
                    a_home = 0 < (bi - ai) % (n - 1) <= (n - 1) // 2
                if not a_home:
                    a, b = b, a
                pairs.append((a, b))
        first_leg.append((pairs, byes))
        ring = [ring[0], ring[-1], *ring[1:-1]]
    for leg in range(1, legs + 1):
        for r, (pairs, byes) in enumerate(first_leg, 1):
            number = (leg - 1) * per_leg + r
            matches = []
            for i, (a, b) in enumerate(pairs, 1):
                if leg == 2:
                    a, b = b, a
                status, award = 'scheduled', None
                if a in withdrawn and b in withdrawn:
                    status = 'voided'
                elif policy == 'void_all' and (a in withdrawn or b in withdrawn):
                    status = 'voided'
                elif a in withdrawn and number > withdrawn[a]:
                    status, award = 'forfeit', b
                elif b in withdrawn and number > withdrawn[b]:
                    status, award = 'forfeit', a
                matches.append({'match_id': f'RR-L{leg}-R{number}-M{i}', 'leg': leg,
                                'home': a, 'away': b, 'status': status, 'awarded_to': award})
                summary['total'] += 1
                summary[status] += 1
            rounds.append({'round': number, 'matches': matches, 'byes': list(byes)})
    return {'format': 'round_robin', 'legs': legs, 'team_count': len(teams),
            'round_count': per_leg * legs, 'rounds': rounds, 'summary': summary}


def swiss(teams, params):
    n = len(teams)
    total = params.get('total_rounds', math.ceil(math.log2(n)))
    current = params.get('round', 1)
    history = params.get('history', [])
    if not integer(total, 1, n - 1) or not integer(current, 1, total) or not isinstance(history, list):
        invalid('params.total_rounds', 'params.round', 'params.history')
    if len(history) != current - 1:
        invalid('params.history')
    score = dict.fromkeys(teams, 0)
    opponents = {t: [] for t in teams}
    had_bye, seen_rounds, played_pairs = set(), set(), set()
    for entry in history:
        if not isinstance(entry, dict) or not integer(entry.get('round'), 1, current - 1):
            invalid('params.history')
        if entry['round'] in seen_rounds:
            invalid('params.history')
        seen_rounds.add(entry['round'])
        bye, matches = entry.get('bye'), entry.get('matches')
        if not isinstance(matches, list) or len(matches) != n // 2 or (n % 2 and bye not in teams) or (not n % 2 and bye is not None):
            invalid('params.history')
        used = {bye} if bye else set()
        if bye:
            score[bye] += 2
            had_bye.add(bye)
        for match in matches:
            if not isinstance(match, dict):
                invalid('params.history')
            a, b, result = match.get('home'), match.get('away'), match.get('result')
            if not isinstance(a, str) or not isinstance(b, str) or a not in score or b not in score or a == b or a in used or b in used or result not in ('home', 'away', 'draw'):
                invalid('params.history')
            used.update((a, b))
            opponents[a].append(b)
            opponents[b].append(a)
            played_pairs.add(frozenset((a, b)))
            score[a] += 2 if result == 'home' else 1 if result == 'draw' else 0
            score[b] += 2 if result == 'away' else 1 if result == 'draw' else 0
    buchholz = {t: sum(score[o] for o in opponents[t]) for t in teams}
    rank = sorted(teams, key=lambda t: (-score[t], -buchholz[t], teams.index(t)))
    standings = [{'rank': i, 'team_id': t, 'score': score[t] / 2, 'buchholz': buchholz[t] / 2} for i, t in enumerate(rank, 1)]
    chosen, pairs = None, None
    if current == 1:
        chosen = teams[-1] if n % 2 else None
        pairs = [(teams[i], teams[i + n // 2]) for i in range(n // 2)]
    else:
        candidates = sorted((t for t in teams if t not in had_bye), key=lambda t: (score[t], -teams.index(t))) if n % 2 else [None]
        for bye in candidates:
            available = [t for t in rank if t != bye]
            graph = nx.Graph()
            graph.add_nodes_from(available)
            for i, a in enumerate(available):
                for b in available[i + 1:]:
                    if frozenset((a, b)) not in played_pairs:
                        graph.add_edge(a, b, weight=abs(score[a] - score[b]))
            # Blossom is a general graph algorithm, not a fixture-generation library.
            matching = nx.min_weight_matching(graph, weight='weight')
            if len(matching) * 2 == len(available):
                chosen = bye
                pairs = sorted((tuple(sorted(pair, key=teams.index)) for pair in matching), key=lambda pair: teams.index(pair[0]))
                break
        if pairs is None:
            raise DomainError(409, 'NO_VALID_PAIRING', {'round': current})
    return {'format': 'swiss', 'round': current, 'total_rounds': total, 'bye': chosen,
            'standings': standings, 'pairings': [{'match_id': f'SW-R{current}-M{i}', 'home': a, 'away': b}
                                               for i, (a, b) in enumerate(pairs, 1)]}


def seed_order(size):
    order = [1, 2]
    while len(order) < size:
        new_size = 2 * len(order)
        order = [x for s in order for x in (s, new_size + 1 - s)]
    return order


def elimination(teams, params, double):
    third, reset = params.get('third_place_match', False), params.get('bracket_reset', True)
    results = params.get('results', [])
    if (not double and type(third) is not bool) or (double and type(reset) is not bool) or not isinstance(results, list):
        invalid('params')
    size = 1 << (len(teams) - 1).bit_length()
    depth = size.bit_length() - 1
    nodes, incoming = {}, {}

    def make(id_, bracket, r, i):
        match = {'match_id': id_, 'bracket': bracket, 'round': r, 'index': i,
                 'home': None, 'away': None, 'home_seed': None, 'away_seed': None,
                 'bye': False, 'winner': None, 'loser': None, 'winner_to': None, 'loser_to': None}
        if double:
            match.update(conditional=False, required=True)
        nodes[id_] = match
        incoming[id_] = {}
        return match

    prefix = 'WR' if double else 'R'
    main = [{'round': r, 'matches': [make(f'{prefix}{r}M{i}', 'winners' if double else 'main', r, i)
                                      for i in range(1, size // (2 ** r) + 1)]} for r in range(1, depth + 1)]

    def link(source, kind, target, slot):
        nodes[source][kind + '_to'] = {'match_id': target, 'slot': slot}
        incoming[target][slot] = (source, kind)

    for r in range(1, depth):
        for i in range(1, size // 2**r + 1):
            link(f'{prefix}{r}M{i}', 'winner', f'{prefix}{r + 1}M{(i + 1) // 2}', 'home' if i % 2 else 'away')
    losers, grand = [], []
    if double:
        for r in range(1, 2 * (depth - 1) + 1):
            count = size // 2 ** (((r + 1) // 2) + 1)
            losers.append({'round': r, 'matches': [make(f'LR{r}M{i}', 'losers', r, i) for i in range(1, count + 1)]})
        for i in range(1, size // 2 + 1):
            link(f'WR1M{i}', 'loser', f'LR1M{(i + 1) // 2}', 'home' if i % 2 else 'away')
        for r in range(2, depth + 1):
            for i in range(1, size // 2**r + 1):
                # Opposite drop order reduces immediate repeats; exact LR slot map is free.
                link(f'WR{r}M{i}', 'loser', f'LR{2*r - 2}M{size // 2**r + 1 - i}', 'away')
        for r in range(1, 2 * (depth - 1)):
            for i in range(1, len(losers[r - 1]['matches']) + 1):
                target = i if r % 2 else (i + 1) // 2
                slot = 'home' if r % 2 or i % 2 else 'away'
                link(f'LR{r}M{i}', 'winner', f'LR{r + 1}M{target}', slot)
        gf = make('GF1', 'grand_final', 1, 1)
        grand.append(gf)
        link(f'WR{depth}M1', 'winner', 'GF1', 'home')
        link(f'LR{2 * (depth - 1)}M1', 'winner', 'GF1', 'away')
        if reset:
            gf2 = make('GF2', 'grand_final', 2, 1)
            gf2.update(conditional=True, required=None)
            grand.append(gf2)
            # Reset reuses GF1 participants; both have exactly one loss when required.
            link('GF1', 'winner', 'GF2', 'home')
            link('GF1', 'loser', 'GF2', 'away')
    elif third and depth >= 2:
        tp = make('TP', 'third_place', depth, 1)
        main[-1]['matches'].append(tp)
        link(f'R{depth - 1}M1', 'loser', 'TP', 'home')
        link(f'R{depth - 1}M2', 'loser', 'TP', 'away')
    order = seed_order(size)
    for i, match in enumerate(main[0]['matches']):
        a, b = sorted(order[2*i:2*i + 2])
        match.update(home=teams[a - 1], home_seed=a, away=teams[b - 1] if b <= len(teams) else None,
                     away_seed=b if b <= len(teams) else None)

    supplied = {}
    for result in results:
        if not isinstance(result, dict) or not isinstance(result.get('match_id'), str) or result['match_id'] not in nodes or not identifier(result.get('winner')):
            invalid('params.results')
        if result['match_id'] in supplied:
            invalid('params.results')
        supplied[result['match_id']] = result['winner']
    resolved = set()

    def settle(id_):
        if id_ in resolved:
            return
        m = nodes[id_]
        for slot, (src, kind) in incoming[id_].items():
            settle(src)
            source = nodes[src]
            m[slot] = source[kind]
            team = m[slot]
            m[slot + '_seed'] = teams.index(team) + 1 if team else None
        if id_ == 'GF2':
            first = nodes['GF1']
            m['required'] = None if first['winner'] is None else first['winner'] == first['away']
            m['home'], m['away'] = first['home'], first['away']
            m['home_seed'], m['away_seed'] = first['home_seed'], first['away_seed']
        ready = all(src in resolved and (nodes[src]['winner'] is not None or nodes[src]['bye']) for src, _ in incoming[id_].values())
        if ready and (m['home'] is None or m['away'] is None) and id_ != 'GF2':
            m['bye'] = True
            m['winner'] = m['home'] or m['away']
        if id_ in supplied:
            win = supplied[id_]
            if win not in (m['home'], m['away']) or (m['bye'] and win != m['winner']) or (id_ == 'GF2' and m['required'] is not True):
                invalid('params.results')
            m['winner'] = win
            m['loser'] = m['away'] if win == m['home'] else m['home']
        resolved.add(id_)

    for id_ in nodes:
        settle(id_)
    if double:
        return {'format': 'double_elim', 'bracket_size': size, 'bracket_reset': reset,
                'winners': main, 'losers': losers, 'grand_final': grand}
    return {'format': 'single_elim', 'bracket_size': size, 'rounds': main}
