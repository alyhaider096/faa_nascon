# Platform ↔ domain interfaces (frozen)

The platform (entrypoint, middleware, migrations, store, roster, RBAC, offline coordinator, mobile API,
worker) calls the sports/scoring/standings modules only through these hooks. Define them in
`backend/app/domain/<module>.py`; nothing else needs to change.

## Modules the entrypoint looks for
`app.domain.sports`, `scoring`, `fixtures`, `leagues`, `standings`. Optional routers
`app.api.domain_audit` (audit routes) and `app.api.domain_mobile` (`/api/v1` routes) export `router`
and are mounted automatically when present. A missing scoring module yields 501 `NOT_IMPLEMENTED`.

## `app.domain.scoring` (used by the offline coordinator and reset)
| function | contract |
| --- | --- |
| `get_match_version(conn, match_id) -> int \| None` | event count; `None` if the match is unknown |
| `find_event(conn, event_id) -> dict \| None` | the originally stored request body, for duplicate vs conflict |
| `append_event(conn, body) -> ("new"\|"replay", response)` | raises `DomainError` for rule failures; no commit inside |
| `match_league_id(conn, match_id)` (optional) | tenant scoping of production offline sync |
| `reset(conn, seed)` (optional) | clear your tables; called inside the reset transaction |

All functions take the caller's open psycopg connection (`dict_row`); never commit. Signatures come from
`app.core.signing.sign_record(id, payload)`. Errors: `app.core.errors.DomainError(status, code, message, details)`.

## Migrations
Platform owns `001_platform.sql` (creates the shared `sports` table). Domain owner adds `1xx_*.sql` files
in `backend/migrations/`; they run in filename order once. `TRUNCATE ... CASCADE` in reset also clears
dependent domain tables.
