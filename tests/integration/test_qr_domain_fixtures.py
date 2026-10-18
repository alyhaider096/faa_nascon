"""Verify QR prerequisite fixture preparation against the real local domain API."""
import json
from pathlib import Path
import subprocess
import sys


def test_qr_fixture_preparation_uses_supported_domain_transitions(client, server, reset, tmp_path):
    root = Path(__file__).resolve().parents[2]
    output = tmp_path / 'qr-cases.json'
    result = subprocess.run([sys.executable, str(root / 'tests/qr/prepare_domain_fixtures.py'),
        '--base-url', server, '--output', str(output), '--allow-mutations'],
        capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stderr
    cases = json.loads(output.read_text())
    assert len(cases) == 4
    assert [case['state'] for case in cases] == ['upcoming', 'in_progress', 'completed', 'in_progress']
    assert len({case['entity_id'] for case in cases}) == 4
    for case in cases:
        projection = client.get('/audit/v1/score/' + case['entity_id'])
        assert projection.status_code == 200 and projection.json()['status'] == case['state']
    # Preparation must not reset or mutate the pre-existing baseline live match.
    assert client.get('/audit/v1/score/match-001').json()['status'] == 'in_progress'
