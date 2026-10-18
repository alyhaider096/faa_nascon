# QR QA handoff - Fatima

This directory supplies independent acceptance tests and score-domain fixtures.
It does not edit Ali's UI, Abdullah's QR service, shared configuration, migrations
or CI. Coordinate fixture execution on an exclusive disposable stack; do not
reset the shared backend. No teammate message has been sent automatically.

**Release blocker:** see [SALT_HANDOFF.md](SALT_HANDOFF.md). The real salt must
reach private runtime/CI configuration, and non-secret wiring must be integrated
and pushed. That setup is not complete merely because this test suite exists.

## Install and local helper checks

```powershell
python -m pip install -r tests/qr/requirements.txt
python -m pytest tests/qr/test_qr_helpers.py -q -p no:cacheprovider
```

The helper tests use public dummy keys and generated QR assets. They verify QA
tools, not backend implementation. Running all of `tests/qr` without a target
explicitly skips live acceptance and must never be reported as a live pass.

## Prerequisites for live acceptance

Abdullah supplies a reachable QR service, explicit private DAY2_SALT loading,
known entity IDs and QR registrations. Set `QR_BASE_URL` and `QR_CASES`, or use
the equivalent CLI options. `cases.example.json` describes the required fixture
set; its `qa-*` IDs are placeholders, not a claim those rows already exist.
Provide all six match states plus player, club and co-stream entities. Use one
live fixture for completion and a separate live fixture for postponement.
Run against a quiet target with no unrelated match changes or scans.

```powershell
# DAY2_SALT must already be supplied privately to this process.
python -m pytest tests/qr/test_qr_live.py -q -p no:cacheprovider --qr-base-url http://QA_HOST:8080 --qr-cases PATH_TO_ACTUAL_CASES.json --junitxml=tests/reports/qr-live.xml
```

This command leaves redirect/scan/transition checks skipped. Add
`--qr-allow-mutations` only for an authorized exclusive disposable target. The
suite does not automatically call reset. Scan-race testing performs ten real
metadata scans and requires contiguous counts without competing clients.

`prepare_domain_fixtures.py --base-url http://QA_HOST:8080 --output PATH_TO_CASES.json --allow-mutations`
creates uniquely named preview/live/completed matches and a second live match
using real Day 1 league/event interfaces, then reads back score states. It does
not create QR registrations or pretend postponement is implemented. Its output
is a partial manifest; supplement it with actual host-supported fixtures before
claiming the full-coverage gate. `tests/integration/test_qr_domain_fixtures.py`
verified this script against the isolated local HTTP backend and real PostgreSQL;
it has not run against Abdullah's deployed service.

## Postponement adapter

The scoring API has no `match_postponed` event. Wait for Abdullah's authorized
product route and provide its exact request in a local JSON file:

```json
{
  "entity_id": "ACTUAL_SECOND_LIVE_MATCH_ID",
  "method": "POST",
  "path": "/api/ACTUAL_SUPPORTED_ROUTE",
  "body": {"USE_THE_REAL_SCHEMA": true}
}
```

Supply it through `--qr-postpone-request PATH.json`. Its path/schema are explicit
placeholders. The optional bearer token is read from `QR_ORGANIZER_TOKEN`; never
put a token in the JSON or command line. Without the adapter, postponement is
NOT RUN. The completion test uses the real `match_end` event and requires a
separate still-live match after the postponement test.

## Acceptance checklist

| Requirement | Check | Current state |
| --- | --- | --- |
| FR-4.1 metadata | Exact required keys/types, deep link and independent HMAC | Prepared; live not run |
| FR-4.1 routing | Six match states plus player/club/co-stream | Prepared; fixtures needed |
| FR-4.1 printed link | Same short URL, new target/signature after real end/postpone | Prepared; live not run |
| FR-4.1 inspect | Repeated inspect preserves count/signature | Prepared; live not run |
| FR-4.1 scans | Ten concurrent scans, exact persistent count | Prepared; live not run |
| FR-4.1 redirect | 302 with current Location; unknown ID/code 404 QR_NOT_FOUND | Prepared; live not run |
| FR-4.1 exports | SVG/PNG/PDF MIME/magic and actual QR decode to stable short URL; PDF entity label | Helpers verified; service not run |
| NFR-9 telemetry | Stored data contains no IP/full UA/cookie/fingerprint | Needs authorized storage inspection; not covered by QR response alone |
| Day 2 salt | Private key present, non-secret wiring pushed, runtime signature verified | Wiring/runtime blocked |

The live tests never use the backend's signing helper. They compare the exact
three-field QR payload using pipe-separated canonical JSON. Export URLs are
checked as metadata; requests use the configured target, not an arbitrary host
returned in metadata. Evidence belongs in `tests/reports/` with SHA, target,
timestamp, commands, versions and actual passed/failed/skipped counts. Never
claim telemetry privacy from a response that merely omits private fields.
