# Requirement Traceability

Implementation paths and automated test references will be added as features land.
All entries are planned; no implementation or passing checks are claimed yet.

| Requirement | Source files | Planned verification | Status |
| --- | --- | --- | --- |
| FR-1.1 Configurable sports and event-sourced scoring | TBD | New sport configuration, scoring, compensation and signatures | Planned |
| FR-1.2 League and tournament setup | TBD | League creation, season and format validation | Planned |
| FR-1.3 Fixture scheduling | TBD | Round-robin, Swiss, single and double elimination; byes and scheduling conflicts | Planned |
| FR-1.4 Standings | TBD | Points, head-to-head tie-breaks and qualification status | Planned |
| FR-2.1 Club profiles and tenant isolation | TBD | Profile data and cross-tenant access rejection | Planned |
| FR-2.2 Roster and player registry | TBD | Transfer windows, loans, releases, squad rules and immutable history | Planned |
| FR-2.3 Merchandise store | TBD | Variants, discounts, mock payments, inventory and PDF receipts | Planned |
| FR-5.1 Five-tier role-based access | TBD | Positive and negative authorization checks across all five roles | Planned |
| NFR-3 Concurrency correctness | TBD | Twenty simultaneous purchases of the final stock unit; exactly one success | Planned |
| NFR-4 Offline tolerance | TBD | Cached screens, persistent actions after restart, sync and conflict handling | Planned |
| NFR-5 Security | TBD | Token checks, secure mobile storage, input validation and rate limiting | Planned |
| NFR-7 Reproducibility | TBD | Clean Docker Compose build, startup, baseline seed and health probe | Planned |

## Continuous verification plan

- Add pytest API tests as backend endpoints become available, using Section 5 of the competition specification as the contract.
- Check exact HTTP status codes, response fields and error codes, including validation, missing resources, conflicts and idempotent replays.
- Add a k6 concurrency scenario for checkout and an Appium workflow for a required mobile journey.
- Record actual source and test paths in this table when work is implemented.
- Generate COVERAGE.json from measured coverage; do not report estimated results.
- Verify Docker Compose and mobile/backend integration before submission.
- Verify a GitHub push during each required checkpoint window; local commits alone do not satisfy a push checkpoint.
