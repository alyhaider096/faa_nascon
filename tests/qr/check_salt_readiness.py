"""Report missing Day 2 configuration without printing any key material."""
import argparse
import os
from pathlib import Path
import sys


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--env-file', type=Path)
    args = parser.parse_args()
    values = dict(os.environ)
    if args.env_file:
        for line in args.env_file.read_text(encoding='utf-8-sig').splitlines():
            if line.startswith(('DAY1_SALT=', 'DAY2_SALT=')):
                key, value = line.split('=', 1)
                values.setdefault(key, value)  # Exact bytes after =; do not strip salt.
    root = Path(__file__).resolve().parents[2]
    checks = {
        'Private DAY1_SALT supplied': bool(values.get('DAY1_SALT')),
        'Private DAY2_SALT supplied': bool(values.get('DAY2_SALT')),
        '.env.example declares DAY2_SALT': 'DAY2_SALT=' in (root / '.env.example').read_text(),
        'Compose forwards DAY2_SALT to API and worker': (root / 'docker-compose.yml').read_text().count('DAY2_SALT:') >= 2,
        'Backend loads DAY2_SALT': 'DAY2_SALT' in (root / 'backend/app/core/config.py').read_text(),
    }
    for label, ready in checks.items():
        print(('READY: ' if ready else 'BLOCKED: ') + label)
    print('Repository secret presence and running-service key correctness are NOT VERIFIED by this script.')
    print('Require an independent signature from the deployed service before marking salt setup complete.')
    return 0 if all(checks.values()) else 1


if __name__ == '__main__':
    sys.exit(main())
