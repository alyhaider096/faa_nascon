# Requirement Traceability

Domain implementation and tests are available on the backend/fatima-domain branch.
Status distinguishes tested services from host/mobile integration still pending.

| Requirement | Source files | Planned verification | Status |
| --- | --- | --- | --- |
| FR-1.1 Configurable sports and event-sourced scoring | `backend/app/domain/sports.py`, `scoring.py`, `common.py`, `models.py` | `tests/domain/test_scoring.py`, `test_api.py`, `test_postgres.py`: mystery sports, signatures, compensation, limits, replay and concurrent appends | Domain tested; host mount/realtime pending |
| FR-1.2 League and tournament setup | `backend/app/domain/scoring.py`, `scheduling.py` | `tests/domain/test_scoring.py`, `test_scheduling.py`: league validation, seasons/divisions, promotion/relegation and hybrid advancement | Services tested; organizer endpoints/authoritative registry integration pending |
| FR-1.3 Fixture scheduling | `backend/app/domain/fixtures.py`, `scheduling.py` | `tests/domain/test_fixtures.py`, `test_scheduling.py`: all formats, sizes 2-128 as allowed, byes, withdrawals, Swiss optimality, conflicts, status and downstream invalidation | Domain tested; host rescheduling/realtime integration pending |
| FR-1.4 Standings | `backend/app/domain/standings.py`, `scoring.py` | `tests/domain/test_standings.py`: three-way subgroup restart, NRR/all-out, lots, qualification and compensation recomputation | Domain tested; host read endpoint mount pending |
| FR-2.1 Club profiles and tenant isolation | `mobile/src/app/(tabs)/club.tsx` (display); backend TBD | Profile data and cross-tenant access rejection | Mobile mock; backend planned |
| FR-2.2 Roster and player registry | `mobile/src/app/roster.tsx` (entry UI); backend TBD | Transfer windows, loans, releases, squad rules and immutable history | Mobile mock; backend planned |
| FR-2.3 Merchandise store | `mobile/src/app/(tabs)/store.tsx`, `mobile/src/app/checkout.tsx`, `mobile/src/app/receipt.tsx`; backend TBD | Variants, discounts, mock payments, inventory and PDF receipts | Mobile mock/live checkout adapter; backend planned |
| FR-5.1 Five-tier role-based access | TBD | Positive and negative authorization checks across all five roles | Planned |
| NFR-3 Concurrency correctness | TBD | Twenty simultaneous purchases of the final stock unit; exactly one success | Planned |
| NFR-4 Offline tolerance | `mobile/src/state/AppContext.tsx`, `mobile/src/app/queue.tsx`; backend TBD | Airplane mode, force-close, replay and conflict handling | Mobile implementation; desk test pending |
| NFR-5 Security | `mobile/src/state/AppContext.tsx` (demo identity in SecureStore); backend TBD | Token checks, secure live JWT, input validation and rate limiting | Live auth planned |
| NFR-7 Reproducibility | TBD | Clean Docker Compose build, startup, baseline seed and health probe | Planned |

## Continuous verification plan

- Add pytest API tests as backend endpoints become available, using Section 5 of the competition specification as the contract.
- Check exact HTTP status codes, response fields and error codes, including validation, missing resources, conflicts and idempotent replays.
- Add a k6 concurrency scenario for checkout and an Appium workflow for a required mobile journey.
- Record actual source and test paths in this table when work is implemented.
- Generate COVERAGE.json from measured coverage; do not report estimated results.
- Verify Docker Compose and mobile/backend integration before submission.
- Verify a GitHub push during each required checkpoint window; local commits alone do not satisfy a push checkpoint.

## Fatima domain verification boundaries

- Schema fragment: `backend/migrations/001_fatima_domain.sql`; host migration assembly remains Abdullah's responsibility.
- API mounting, injected signing/session/reset hooks and full remaining acceptance: `backend/DOMAIN_INTEGRATION.md`.
- `test_postgres.py` is opt-in against a disposable PostgreSQL database and verifies twenty concurrent distinct events, concurrent identical replay and caller rollback/savepoints.
- No clean Compose, device/UI or host store/roster/RBAC/offline coordinator result is claimed by this branch.
- Coverage for these modules is measured separately; this branch does not fabricate the six-area root COVERAGE.json.
