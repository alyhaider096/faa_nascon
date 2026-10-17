#!/usr/bin/env bash
# Runs the whole backend suite against a real PostgreSQL + Redis and regenerates COVERAGE.json.
# Needs: TEST_DATABASE_URL (a THROWAWAY database; the suite resets it) and optionally TEST_REDIS_URL.
#   TEST_DATABASE_URL=postgresql://user:pw@127.0.0.1:5432/nascon_test ./run_tests.sh
# The public demo salt is injected by tests/conftest.py; the real team salt is never used or needed.
set -euo pipefail
cd "$(dirname "$0")"

: "${TEST_DATABASE_URL:?Set TEST_DATABASE_URL to a throwaway PostgreSQL database (it will be reset)}"
export TEST_REDIS_URL="${TEST_REDIS_URL:-redis://127.0.0.1:6379/0}"

python3 -m pip install -q --disable-pip-version-check -r backend/requirements.txt -r backend/requirements-dev.txt 2>&1 | tail -n 2 || true

rm -f .coverage
python3 -m pytest tests -q -p no:cacheprovider \
  --cov=backend/app --cov-report=term --cov-config=/dev/null
status=$?
python3 scripts/coverage_report.py
exit "$status"
