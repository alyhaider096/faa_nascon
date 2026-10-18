"""Reproduce measured Day 2 function-region coverage from coverage.py JSON.

Usage: python tests/day2/measure_coverage.py tests/reports/extended-coverage.json
The mapping includes all top-level functions in Day 2 API/domain and worker.
Module initialization and external dependencies are outside this declared scope.
"""
from __future__ import annotations

import ast
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
GROUPS = ('streaming', 'costream', 'qr_guest', 'moderation_dlq', 'observability')


def classify(name: str) -> str:
    if 'costream' in name:
        return 'costream'
    if name in {'metrics', '_media_metrics', 'erase_user', 'privacy'}:
        return 'observability'
    if any(term in name for term in ('moderation', 'profanity', 'normalized', 'chat')):
        return 'moderation_dlq'
    if any(term in name for term in ('stream', 'media', 'vod', 'player_exists',
                                     'player_not_found', 'object_chunks')):
        return 'streaming'
    return 'qr_guest'


def main():
    raw_path = Path(sys.argv[1])
    raw = json.loads(raw_path.read_text())
    groups = {key: [] for key in GROUPS}
    totals = {key: [0, 0] for key in GROUPS}
    for filename, record in raw['files'].items():
        filename = filename.replace('\\', '/')
        if not filename.endswith(('app/api/day2.py', 'app/domain/day2.py', 'app/worker.py')):
            continue
        tree = ast.parse((ROOT / filename).read_text())
        executed, missing = set(record['executed_lines']), set(record['missing_lines'])
        for node in tree.body:
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            selected = [classify(node.name)]
            if filename.endswith('app/worker.py'):
                selected = (['streaming'] if node.name in {'active_media_paths', 'index_recordings_once'}
                            else ['moderation_dlq', 'observability'])
            region = set(range(node.lineno, node.end_lineno + 1))
            covered, absent = len(executed & region), len(missing & region)
            for group in selected:
                totals[group][0] += covered
                totals[group][1] += absent
                groups[group].append({'file': filename, 'function': node.name,
                                      'covered': covered, 'missing': absent})
    if any(c + m == 0 for c, m in totals.values()):
        raise SystemExit('Missing measured module region; no coverage artifact written')
    percentages = {key: round(100*c/(c+m), 2) for key, (c, m) in totals.items()}
    sha = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    mapping = {'source_sha': sha, 'raw_report': raw_path.as_posix(),
               'scope': 'Executable lines within all top-level functions in Day 2 API/domain and worker. '
                        'Shared relay/main worker functions counted in moderation_dlq and observability. '
                        'Module initialization and dependencies outside these source files are excluded; '
                        'these percentages do not establish whole-stack or real-media acceptance.',
               'groups': groups}
    (ROOT / 'COVERAGE_DAY2.json').write_text(json.dumps(percentages, indent=2) + '\n')
    (ROOT / 'tests/reports/day2-coverage-mapping.json').write_text(json.dumps(mapping, indent=2) + '\n')
    print(json.dumps(percentages))


if __name__ == '__main__':
    main()
