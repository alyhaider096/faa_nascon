#!/usr/bin/env python3
"""Turn a measured coverage data file into COVERAGE.json (six areas, line-coverage percent).

Only measured values are written. An area whose source files do not exist yet is reported as 0.0
(never estimated) and listed on stderr so the gap is visible.
"""
import json
import sys
from pathlib import Path

import coverage

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "backend" / "app"
AREAS = {
    "fixtures": ["domain/fixtures.py"],
    "scoring": ["domain/scoring.py", "domain/sports.py"],
    "standings": ["domain/standings.py", "domain/leagues.py"],
    "store": ["domain/store.py"],
    "roster": ["domain/roster.py"],
    "rbac": ["core/security.py", "core/middleware.py"],
}


def main(out: Path) -> int:
    cov = coverage.Coverage(data_file=str(ROOT / ".coverage"))
    cov.load()
    data = cov.get_data()
    result, missing = {}, []
    for area, rels in AREAS.items():
        stmts = covered = 0
        for rel in rels:
            path = APP / rel
            if not path.exists():
                missing.append(f"{area}: {rel} not present")
                continue
            _, statements, _, missed, _ = cov.analysis2(str(path))
            stmts += len(statements)
            covered += len(statements) - len(missed)
        result[area] = round(100.0 * covered / stmts, 1) if stmts else 0.0
    out.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result))
    for m in missing:
        print("note:", m, file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main(ROOT / "COVERAGE.json"))
