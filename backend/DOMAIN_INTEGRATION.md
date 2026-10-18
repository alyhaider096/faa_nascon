# Fatima domain integration for Abdullah

For the current mounted HTTP/socket interfaces and Day 2 completion/postponement
integration gaps, see [DAY2_DOMAIN_HANDOFF.md](DAY2_DOMAIN_HANDOFF.md). The wiring
instructions below describe the original domain fragment; verify the existing
host integration before mounting duplicate routers or adding a second worker.

This branch supplies sports, fixtures, league registration, signed event streams,
score projections and standings. It does not introduce a second application
entrypoint or own Docker, roster, store, auth, the global reset route or sync.

## Install and mount

Run from repository root, with Python 3.11+:

```sh
python -m pip install -r backend/requirements-domain.txt
# Host additionally installs its PostgreSQL driver, e.g. psycopg[binary].
```

Use a synchronous SQLAlchemy Session. Inject the same session into nested domain
calls; callers own commit/rollback. With psycopg3 the engine URL is
`postgresql+psycopg://...`, not the default psycopg2 URL. The `.env.example`
database URL is a deployment input, so normalize it when creating the engine.

```python
from backend.app.domain.api import build_router, domain_error_handler
from backend.app.domain.common import DomainError, signer
from backend.app.domain.models import Base
from backend.app.domain.seeds import reset_domain

# app and SessionFactory are supplied by Abdullah's application.
# startup_salt = os.environ['DAY1_SALT']; never hard-code the real value.
sign_record = signer(startup_salt)  # or inject your identical shared helper

def get_session():
    # Commit/rollback must occur before the HTTP response is sent. Configure
    # the host dependency lifecycle accordingly; test this against its FastAPI version.
    with SessionFactory() as session, session.begin():
        yield session

app.add_exception_handler(DomainError, domain_error_handler)
app.include_router(build_router(get_session, sign_record))
```

Schema fragment: `models.Base.metadata`. Include its tables in your migration
assembly. `Base.metadata.create_all(engine)` can bootstrap the empty database at
startup if that is your agreed migration strategy; do not create a separate DB.
The fragment tables use the `domain_` prefix to avoid collision with your tables.
`backend/migrations/001_fatima_domain.sql` is an equivalent PostgreSQL fragment.
Do not apply both incompatible host migrations and this fragment blindly.

Host startup seeds the baseline only on first initialization. Host `/reset`
calls `reset_domain(session, seed)` in the same transaction as its roster/store/
auth/sync reset. Reset must be serialized against API writers and workers by a
host-wide reset gate; the fragment alone cannot coordinate your other services.
It removes only these domain tables and recreates sport data and the reset seed.
The five demo accounts, RBAC IDs, inventory and response body remain your job.

## Service interface

| Function | Arguments | Return |
| --- | --- | --- |
| create_sport | session, body | 201 response dict |
| generate_fixtures | body | 200 response dict, no persistence |
| register_league | session, body | 201 response dict |
| append_event | session, body, sign_record | (HTTP status 201/200, response dict) |
| project_score | session, match_id | exact score response |
| standings | session, league_id | exact standings response |
| get_match_version | session, match_id, lock=False | event count; optional match transaction lock |
| reset_domain | session, seed=42 | no response, no commit |

All raise `DomainError(status, code, details)` for contract failures. Global host
middleware must also handle errors outside these routes and exempt audit/health
from rate limiting. Router body parsing enforces 1 MiB and maps malformed JSON to
400; global input/auth/rate policy still belongs in the host.

No service commits. A caller exception must roll back. For offline replay create
an action savepoint, use `get_match_version(..., lock=True)`, apply your version/
dedup rules, call `append_event` on the same session, and atomically persist your
sync record. Lock ordering matters: normal append takes event-ID advisory lock
then match lock. Offline callers should acquire the event-ID lock first too,
then match/version, to avoid the reverse-order deadlock with normal requests.
Import `lock_key` from scoring for this purpose. Do not treat the version check
as safe without a lock. Replays return the original event's sequence/signature;
sync reports current version separately.

The general NetworkX blossom solver is used only to optimize Swiss pairing.
Tournament construction/seeding/routing remains custom code. This is not a
third-party fixture-generation library. All code runs locally without network.

`domain_outbox` records are transactional notifications; a host worker publishes
them after commit to the agreed WebSocket/Redis channel. Publishing is not yet
wired here. Use idempotent consumption; do not clear records before delivery.
Signed event rows are never updated for compensation; metadata is derived on read.
PostgreSQL advisory locks serialize event IDs, match appends and registration;
SQLite unit tests do not demonstrate those concurrency guarantees.

## Wider scheduling services

`scheduling.py` exposes tenant-scoped configure_competition, reschedule and
change_schedule_status services. Host must perform role/ownership authorization
before calling them and map its mobile/organizer endpoints to them. They provide
season/division/stage configuration, structured venue/team/shared-player/rest/
availability conflicts, product state transitions and transitive postponement
invalidation. Schedule input explicitly contains shared `player_ids`,
`venue_windows`, `min_rest_minutes` and bracket `depends_on`; host must resolve
those from its authoritative registry, not trust an unprivileged client to omit
players/windows. Postponement clears resolved slots, flags downstream matches and
rechecks their conflicts. `advance_season` applies configured promotion/relegation
to finalized rankings while retaining the prior season snapshot;
`hybrid_knockout` seeds qualifiers by finish position then group order;
`resolve_downstream_slot` replaces invalidated bracket winners and rechecks
conflicts. The host must supply authoritative finalized standings/winners,
resolve shared-player memberships and mount organizer-only endpoints. These
functions are tested as services; full product journeys are not yet integrated.

These product services do not change the audit match status contract. Keep the
product lifecycle and score-stream lifecycle coordinated in the host orchestration
layer. They are intentionally not mounted as unauthenticated audit write routes.
`SCHEDULING_CONFLICT` is a product-only code; no new error code is introduced into
the mandatory audit contract.

## Tests and evidence

```sh
python -m pip install -r backend/requirements-domain-test.txt
python -m pytest tests/domain -q --cov=backend.app.domain --cov-report=term-missing --cov-report=json:domain-coverage.json
```

Keep this suite in the host run_tests.sh. Do not declare store/roster/rbac coverage
from this suite. PostgreSQL tests are opt-in through DOMAIN_TEST_DATABASE_URL (with `psycopg[binary]` installed);
use a separate disposable database, never the live judging database.
Final root COVERAGE.json is assembled by the host from all six measured groups.

Remaining host acceptance: clean Compose on Ubuntu, /health, full reset and seeds,
global security, offline sync coordinator/dedup, realtime publishing, production
auth/read routes, Android integration, and complete full-product operations above.
