"""Create score-domain fixtures only on an explicitly authorized disposable target.

No reset, QR-service edits, invented postponement API, or shared configuration edits.
"""
import argparse
import json
from pathlib import Path
from uuid import uuid4

import httpx


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--base-url', required=True)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--allow-mutations', required=True, action='store_true')
    args = parser.parse_args()
    namespace = 'qa-qr-' + uuid4().hex[:12]
    states = [('preview', 'upcoming'), ('live', 'in_progress'), ('vod', 'completed'),
              ('to-postpone', 'in_progress')]
    fixtures = [{'match_id': namespace + '-' + suffix, 'home': namespace + '-home',
                 'away': namespace + '-away'} for suffix, _ in states]
    with httpx.Client(base_url=args.base_url.rstrip('/'), timeout=30, trust_env=False) as client:
        response = client.post('/audit/v1/leagues', json={'league_id': namespace, 'sport_id': 'football',
            'teams': [namespace + '-home', namespace + '-away'], 'fixtures': fixtures,
            'qualification': {'spots': 1}})
        if response.status_code != 201:
            raise RuntimeError(f'League creation failed: HTTP {response.status_code}; no reset attempted')
        for fixture, (_, state) in zip(fixtures, states):
            if state == 'upcoming':
                continue
            kinds = ['match_start', 'match_end'] if state == 'completed' else ['match_start']
            for kind in kinds:
                response = client.post('/audit/v1/events', json={'event_id': fixture['match_id'] + '-' + kind,
                    'match_id': fixture['match_id'], 'type': kind, 'payload': {}})
                if response.status_code != 201:
                    raise RuntimeError(f'{kind} failed: HTTP {response.status_code}; partial fixture namespace {namespace}')
        cases = []
        for fixture, (_, state) in zip(fixtures, states):
            response = client.get('/audit/v1/score/' + fixture['match_id'])
            assert response.status_code == 200 and response.json()['status'] == state
            cases.append({'entity_id': fixture['match_id'], 'entity_type': 'match', 'state': state})
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(cases, indent=2) + '\n', encoding='utf-8')
    print(f'Created and read back four score-domain fixtures in namespace {namespace}.')
    print('QR mapping, postponed/cancelled/abandoned state and other entity fixtures remain host prerequisites.')
    print('This partial manifest does not pass the full-fixture-coverage acceptance gate.')


if __name__ == '__main__':
    main()
