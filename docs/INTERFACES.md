# Platform <-> domain integration (implemented)

The domain owner's services (`app.domain.{sports,scoring,fixtures,standings,scheduling,seeds}`) take a
SQLAlchemy `Session`. The platform owns one psycopg transaction per request, so:

- `app/core/sa.py` binds a Session to that very connection through a DBAPI proxy (SQLAlchemy never
  commits/rolls back/closes it). Everything in a request - events, offline sync records, reset - is one
  atomic transaction.
- `app/domain/bridge.py` is the single adapter: it implements the conn-based port used by the offline
  coordinator (`get_match_version`, `find_event`, `append_event`, `match_league_id`, `reset`) and the
  HTTP-facing calls. Domain `DomainError`s are translated to the platform error shape.
- Routes: `app/api/domain_audit.py` (`/audit/v1/{sports,fixtures,leagues,events,score,standings}`) and
  `app/api/domain_mobile.py` (`/api/v1/{matches/{id},matches/{id}/events,leagues/{id}/standings,fixtures/preview}`),
  auto-mounted by `app/main.py`. Realtime `score_updated` is pushed to `/ws/v1/matches/{id}` after commit.
- Migrations: `001_platform.sql` (platform) then `101_fatima_domain.sql` (domain tables, `domain_` prefix).
  Reset truncates platform tables, then `bridge.reset` -> `seeds.reset_domain` re-creates the sports.

Known gaps: `domain_outbox` rows are written but not relayed (score realtime is pushed inline instead);
`scheduling.py` product services (conflicts, rescheduling, promotion/relegation) are tested as services
but have no mounted HTTP endpoints.
