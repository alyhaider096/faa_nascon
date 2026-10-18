# Requirement Traceability

## Final regression - 18 October 2026, 13:58 PKT

Final source `758d46ce860d4531d843f78160c6a94d8fb0ec8b` (same source as the
working tree when the run began) passed **451 tests, 17 skipped, 8 warnings**
in 200.45 seconds. Command: `python -m pytest tests -q -p no:cacheprovider
--cov=backend/app --cov-report=json:tests/reports/post-integration-coverage.json
--junitxml=tests/reports/post-integration-tests.xml`. Target: isolated local
PostgreSQL `nascon_test` on port 55432 and Redis DB 0 on port 56379.
Measured aggregate line coverage: **90.22%**. The skipped device/Grid/live-QR
gates in this full run retain their meaning; separate actual Grid and selected
QR results are recorded below. Aggregate coverage does not prove five logical
Day 2 module thresholds. Do not fabricate COVERAGE_DAY2.json.

Fresh remote fetch found no unmerged branches. Compose config validation passed;
full clean Compose startup was not run. A private-value scan found neither salt
in tracked files. The hourly automation is paused for the freeze. The failed
load gate and live-media/device/deployment gaps below remain open.


## Integrated checkpoint - 18 October 2026, 13:54 PKT

All fetched branches are integrated on main, pushed and remote-verified at
`a31a2d327d37361693db3436bcbbe1489b6ed518`: backend bundle `4b162ca`, frontend
`d234430`, and adversarial domain tests `9bc9894`. The historical statuses below
describe earlier source and are superseded by this checkpoint for local checks.

| Check | Actual result / evidence |
| --- | --- |
| Full isolated PostgreSQL/Redis suite at a31a2d3 | 451 passed, 17 skipped; `integrated-tests.xml`; raw measured aggregate coverage 90%, `integrated-coverage.json` |
| Frontend pinned install/build | npm ci, TypeScript, lint and web export passed on integrated source |
| Real parallel Selenium Grid | 3 passed; `selenium-report.xml`; hosted exported app, two Chrome sessions and Firefox |
| Independent local QR HTTP/signature/export checks | 6 passed, 5 deselected; `qr-live-local.xml`; private Day 2 key loaded without disclosure; real SVG/PNG/PDF decoded |
| QR read-only lock correction | Inspection no longer locks the mapping row; real scans retain locking; 34 targeted tests passed, `post-qr-lock-tests.xml` |
| Official 500-viewer + 50-poster k6 profile | FAILED. Initial proxy run: zero HTTP failures but p95 2.64s. Proxy rerun unreliable (17.42% failures). Direct native run: 92.83% failed requests; successful-response p95 7.57s. `k6-summary-before-qr-lock.json`, `k6-summary-proxy-after-qr-lock.json`, `k6-summary.json`. No load pass claimed. |
| Salt | Runtime/example/Compose wiring now present; independent local signatures passed. Actual secrets remain ignored. GitHub secret presence and Abdullah's deployed runtime are unverified. |

Target: disposable local API at http://127.0.0.1:8080 using separate `gridqa`
database and Redis DB 1; regression uses `nascon_test` and Redis DB 0.
This does not establish phone-reachable media, full clean Compose startup,
Appium acceptance, 25-client websocket p95, all QR state transitions, or the
deployment on Abdullah's laptop. Five logical module coverage gates remain
unproven; aggregate coverage must not be copied into COVERAGE_DAY2.json.

Commands: `python -m pytest tests -q -p no:cacheprovider --cov=backend/app
--cov-report=json:tests/reports/integrated-coverage.json
--junitxml=tests/reports/integrated-tests.xml`; `python -m pytest -n 3
tests/selenium -q -p no:cacheprovider --junitxml=tests/reports/selenium-report.xml`
with RUN_SELENIUM_GRID=1 and local API/hosted-web targets; QR selected acceptance
via tests/qr/test_qr_live.py using --qr-base-url, --qr-cases and private
QR_DAY2_SALT; native k6 v2.3.0 `run --summary-export=tests/reports/k6-summary.json
tests/k6_load.js`. Full post-correction regression is running; its separate
post-integration reports must be assessed before any pass is claimed.


## Current release status - 18 October 2026, 12:36 PKT

**Waiting for Abdullah's integrated backend and reachable API/media addresses.**
Latest fetched main at this update: `61efc02593985bc71b57be6806b44c10139c1e07`.
Frontend/APK commits `330d475` and `c3848bd` are integrated. No newer backend
commit was present on fetched main. Deployment state has not been established.
This is a documentation update; no tests or health probes were rerun for it.
The latest actual contract capture tested `4ef28e1` on isolated local services;
do not transfer its results to an untested teammate build or deployment.

| Requirement / gate | Current status | Owner / next action | Existing evidence |
| --- | --- | --- | --- |
| FR-3.1 athlete profiles/social graph | Pending integrated backend and live verification | Abdullah supplies agreed reads/follow contract; Ali integrates UI; Fatima verifies | `tests/reports/FRONTEND_REVIEW_330d475.md` |
| FR-3.2 streaming/overlays/VOD | Missing local Day 2 routes; deployed not run | Abdullah supplies real ingest/playback/recording; Ali fixes publisher lifecycle; Fatima verifies real media and timing | `tests/reports/INTEGRATION_CONTRACT_STATUS.md` |
| FR-3.3 co-stream | Missing local commands/public read; deployed not run | Abdullah supplies commands, invitations and authoritative handoff; Ali fixes host gating/playback mapping | Integration status and frontend review reports |
| FR-4.1 QR | Local routes missing; QR acceptance suite prepared; deployed not run | Abdullah supplies mappings/exports/effective status and postponement route; Fatima executes on agreed isolated fixtures | `tests/qr/README.md`, `tests/reports/qr-preparation.xml` |
| FR-4.2 guest access | Frontend routes present; backend public reads/session absent in tested source | Abdullah integrates hosting/public reads/session and exact Day 2 reset seed | `tests/reports/integration-contract-examples.json` |
| FR-4.3 guest write guard | **FAILED on tested local backend**; deployment not run | Abdullah enforces exact 403 GUEST_WRITE_FORBIDDEN for direct guest chat/checkout/events; Fatima retests | Captured audit checkout/events returned 201; member checkout 401 |
| FR-4.4 atomic merge | Local merge/member-cart read absent; frontend cart continuation finding open | Abdullah supplies atomic merge/replay/stock behavior; Ali hydrates checkout cart; Fatima verifies persistence/races | Integration status and frontend review reports |
| FR-5.2 notifications/DLQ | Existing member socket partial; Day 2 frames/retries/durability pending | Abdullah supplies sequenced score/chat/invite/host frames and persistent DLQ | Actual member frames in integration examples JSON |
| FR-5.3 moderation | Day 2 service not found in inspected source; acceptance not run | Abdullah integrates filter/rate/concurrency behavior; Fatima verifies exact audit cases | Planned cases in private QA handbook; independent signing tooling only |
| NFR-1 score latency | Not run | Verify 25-client p95 <500 ms and separate DOM timing on real target | No timing pass claimed |
| NFR-2 load | Not run | Verify exact 500+50 VU profile; runner readiness still to establish | No k6 pass/report claimed |
| NFR-6 observability | Not verified | Parse real metrics and verify transitions | No metrics pass claimed |
| NFR-8 accessibility/Grid | Not run on real hosted guest app | Establish Grid readiness and parallel Chrome/Firefox sessions, then keyboard/contrast/ARIA checks | Source/build checks do not replace browser acceptance |
| NFR-9 privacy | Not run | Verify erase timing/token invalidation and authorized storage inspection | No privacy pass claimed |
| Day 2 salt | **Runtime/CI wiring and live signature verification unresolved** | Abdullah loads/forwards keys privately, preserves Day 1 signing and verifies running Day 2 signatures | `tests/qr/SALT_HANDOFF.md`; real values remain Git-ignored |
| APK/Appium | APK tracked; independent device acceptance pending | Ali supplies identified replacement build after fixes; Fatima runs native links and cross-surface chat | Previous reported Pixel timings are not independent QA evidence |
| Build/ancestry/coverage | Clean npm install issue open; organizer base and production coverage unresolved | Owners resolve build/runtime gates; obtain DAY1_BASE_SHA; measure five modules before generating coverage JSON | Review reports; no fabricated COVERAGE_DAY2.json |

Retained local results: 176 passed / 15 skipped in `checkpoint-1205.xml`, the
earlier 67 RBAC checks and 22 all-role event checks, and separate fixture checks.
These runs have different scopes and must not be summed into one acceptance
count. Demo-only state changes do not satisfy connected requirements. Three demo
findings remain recorded in `tests/reports/DEMO_REVIEW_c3848bd.md`.

When Abdullah's build is available, record its exact SHA, configured API/media
URLs and reset permission, then verify health/reset, Day 2 signatures and guest
rejection before QR/merge/media, browser/device and load acceptance. Recheck
test/tool readiness rather than assuming every planned suite is already runnable.
Earlier sections below are dated evidence/history and do not override this status.

## Integration contract capture - 18 October 2026, 12:13 PKT

Tested SHA: `4ef28e1d595fd3ec0757c053b4501f2611a1b3f8`.
`tests/reports/INTEGRATION_CONTRACT_STATUS.md` and
`integration-contract-examples.json` record actual isolated HTTP/socket probes.
They supersede earlier "not run" labels for these specific local route checks;
deployed acceptance remains not run. Public reads, guest session/staging/merge,
QR, stream-key/media and co-stream routes return 404 in this backend.

**FR-4.3 FAILED locally:** valid audit checkout and score-event requests carrying
the seeded guest bearer token returned 201. Member checkout returns 401 rather
than the required 403/code. This requires Abdullah's guest guard integration;
ordinary five-role RBAC passing does not establish guest enforcement.

**FR-4.1/4.2/4.4 blocked locally:** absent QR/public/merge endpoints; required
match-m1 is not seeded, while existing match-001 is seeded 2:1. The old member
socket is `/ws/v1/matches/{id}` and its score frame lacks direct scores/room
sequence. No successful Day 2 media/QR/signing/latency claim is made. The capture
runner is diagnostic and intentionally outside default test_* collection;
its execution success is not feature acceptance.

## Hourly QA checkpoint - 18 October 2026, 12:05 PKT scheduled run

Integrated source reviewed: `c3848bd` (Ali's interactive demo), including
`330d475` and the previous QA commits. `tests/reports/checkpoint-1205.xml`
records 176 local tests passed, 15 skipped: four opt-in PostgreSQL tests and
eleven live QR cases. No deployed acceptance or Day 2 production coverage is
inferred from these results.

Current UI findings: `tests/reports/FRONTEND_REVIEW_330d475.md` and
`tests/reports/DEMO_REVIEW_c3848bd.md`. Guest login/cart continuation, co-stream
playback mapping, failed-media cleanup and live permission controls remain open.
Demo rehearsal adds visible role actions but has duplicate-name roster identity,
layout-capacity and empty-session termination defects. These are review findings;
no teammate implementation was edited during this checkpoint.

**Release blocker remains open:** the private keys are supplied locally but
`.env.example`, API/worker Compose forwarding and backend DAY2_SALT loading are
still absent. CI secret provisioning and deployed signature verification remain
unverified. See `tests/qr/SALT_HANDOFF.md`; do not mark salt setup complete.
The candidate deployed health URL still timed out, so live QR/media/Grid/Appium
acceptance remains not run. Obtain organizer DAY1_BASE_SHA before ancestry claims.

## Day 2 QA baseline - 18 October 2026

Baseline inspected: `c9ad86fb44730cb02f3556727596ceec8b4530fa`.
The Day 1 records below are preserved historical claims, not new execution results.
No Day 2 live acceptance pass is claimed. Evidence: `tests/reports/EVIDENCE.md`.

| Requirement | Source / implementation status at baseline | Automated verification | Live evidence | Current state |
| --- | --- | --- | --- | --- |
| FR-3.1 Athlete identity and social graph | Day 2 implementation not found | Profile/VOD and concurrent follow suite pending | None | Not run |
| FR-3.2 Solo streaming and overlays | Day 2 stream service not found; existing `backend/app/core/realtime.py` needs integration review | `tests/day2/signing_oracle.py` supplies independent signing; live key/media suite pending | None | Partial QA tooling; acceptance not run |
| FR-3.3 Four-way co-stream and handoff | Day 2 implementation not found | Capacity, layout, replay and real host-drop suite pending | None | Not run |
| FR-4.1 Dynamic cryptographic QR | Day 2 implementation not found in inspected baseline | `tests/qr/test_qr_live.py`: metadata/HMAC, all states/entities, counters, exports, redirects, completion and adapter-driven postponement; `tests/qr/prepare_domain_fixtures.py` | None | QA suite prepared; live acceptance not run |
| FR-4.2 Zero-account guest experience | Guest web implementation not found | Grid initial-load and cart staging suite pending | None | Not run |
| FR-4.3 Guest write boundary | Existing `backend/app/core/security.py` needs Day 2 guest checks | Direct chat/checkout/event rejection and member controls pending | None | Not run |
| FR-4.4 Progressive registration and atomic merge | Day 2 implementation not found | Oracle extracts active-cart signing fields; atomicity/replay/stock suite pending | None | Partial QA tooling; acceptance not run |
| FR-5.2 Notification bus and DLQ | Existing `backend/app/core/queue.py` needs Day 2 contract review | Durable retry, depth and restart/concurrency suite pending | None | Not run |
| FR-5.3 Automated moderation | Day 2 implementation not found | Oracle requires explicit flagged_count; dictionary/flood/race suite pending | None | Partial QA tooling; acceptance not run |
| NFR-1 Score latency | Existing `backend/app/core/realtime.py` | 25-client p95 probe pending | None | Not run |
| NFR-2 Concurrency scale | Deployed target not provided | Exact 550-VU k6 profile pending | None | Not run |
| NFR-6 Observability | Day 2 metrics not found | Prometheus parsing and transition probes pending | None | Not run |
| NFR-8 Guest accessibility | Guest web implementation not found | Grid keyboard/contrast/ARIA/target checks pending | None | Not run |
| NFR-9 Privacy | Day 2 erase/telemetry implementation not found | PII/token deletion timing and telemetry inspection pending | None | Not run |

`COVERAGE_DAY2.json` will be generated only from actual module coverage after
the five Day 2 modules are identified. Missing measurements are not zero or a pass.
Oracle self-checks do not count as production module coverage or live acceptance.

### Domain integration support for FR-3.2 / FR-4.1

`backend/DAY2_DOMAIN_HANDOFF.md` records existing completion, projection,
standings and subscription interfaces. `tests/domain/test_day2_handoff.py`
verifies completion persistence, replay, compensation, rollback and schedule
postponement boundaries; `tests/reports/domain-handoff.xml` has 3 passing local
service cases. Full domain suite: 155 passed, 4 PostgreSQL cases skipped.
QR/VOD acceptance remains not run. Required host work: authorized postponement
route, effective schedule/score status, committed notification delivery, guest
subscription contract and the required Day 2 socket path.

### QR preparation and salt gate

`tests/qr/README.md` contains the all-state/entity acceptance checklist.
`tests/reports/qr-preparation.xml`: 21 local helper checks passed, 11 live tests
skipped (target/fixtures not configured). SVG/PNG/PDF decoder checks use synthetic
assets and do not prove service exports. `tests/reports/qr-domain-fixtures.xml`:
1 real local HTTP/PostgreSQL fixture-setup check passed; shared backend untouched.
Source: `tests/qr/prepare_domain_fixtures.py` and
`tests/integration/test_qr_domain_fixtures.py`.

**Release blocker:** `tests/qr/SALT_HANDOFF.md`. Private keys are preserved in
Git-ignored local configuration. DAY2_SALT example config, API/worker forwarding,
backend loading, CI provisioning and independent deployed signatures are not
complete. The hourly checkpoint retains this gate. No actual key is in Git.

## Preserved Day 1 records

### Current RBAC regression update

See `tests/reports/RBAC_REVIEW.md`: the existing five-role/mobile/tenant suite
passed 67 tests against disposable PostgreSQL/Redis. New
`tests/integration/test_mobile_event_roles.py` passed 22 cases for all-role
score/correction writes, direct/offline replay, persisted readback and league
scope. Evidence: `rbac-baseline.xml` and `mobile-event-roles.xml` under
`tests/reports/`. No backend authorization failure reproduced. Mobile feedback,
correction confirmation and post-sync score refresh fixes in
`mobile/src/app/score.tsx` and `mobile/src/state/AppContext.tsx` pass typecheck/lint;
rebuilt APK/device acceptance remains not run. This updates FR-5.1/NFR-4 evidence,
without claiming Day 2 guest enforcement or deployed acceptance.

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

## Backend platform slice (measured; implemented in this branch)

All checks below ran against real PostgreSQL 16 and Redis via `./run_tests.sh`: 359 passed, 0 failed (platform + domain suites). Measured line coverage in `COVERAGE.json`.

| Requirement | Source | Tests |
| --- | --- | --- |
| Shared HMAC signing (5.x, App. A) | `backend/app/core/signing.py` | `tests/rbac/test_signing.py` |
| Roster 5.11 | `backend/app/domain/roster.py` | `tests/roster/test_roster.py` |
| Store/checkout 5.12, NFR-3 (20-buyer race) | `backend/app/domain/store.py` | `tests/store/test_store.py` |
| RBAC 5.13, tenant isolation, FR-5.1 | `backend/app/core/security.py`, `backend/app/api/audit.py` | `tests/rbac/test_rbac.py` |
| Security NFR-5 (400 not 422, rate limit, 1 MB cap) | `backend/app/core/middleware.py`, `errors.py` | `tests/rbac/test_zz_ratelimit.py`, `test_rbac.py` |
| Offline sync 5.14, NFR-4 (server side) | `backend/app/domain/offline.py` | `tests/integration/test_offline.py` (scoring port stubbed by `tests/fixtures/fake_scoring.py`) |
| Reset/reproducibility 5.5 (in-process) | `backend/app/domain/seed.py` | `tests/integration/test_platform.py` |
| Mobile API, auth, realtime pin, outbox worker | `backend/app/api/mobile.py`, `core/realtime.py`, `worker.py` | `tests/integration/test_platform.py` |

Not yet verified: clean `docker compose up -d --build` timing, restart durability and phone-over-LAN
(no Docker or phone in the build sandbox); mobile desk-check.

## Fatima domain verification boundaries

- Schema fragment: `backend/migrations/001_fatima_domain.sql`; host migration assembly remains Abdullah's responsibility.
- API mounting, injected signing/session/reset hooks and full remaining acceptance: `backend/DOMAIN_INTEGRATION.md`.
- `test_postgres.py` is opt-in against a disposable PostgreSQL database and verifies twenty concurrent distinct events, concurrent identical replay and caller rollback/savepoints.
- No clean Compose, device/UI or host store/roster/RBAC/offline coordinator result is claimed by this branch.
- Coverage for these modules is measured separately; this branch does not fabricate the six-area root COVERAGE.json.

| Fixtures 5.7, scoring 5.9, standings 5.10, leagues 5.8 | `backend/app/domain/{fixtures,scoring,standings,sports}.py` | `tests/domain/*`, `tests/integration/test_domain.py` |
| Domain inside platform transaction, offline sync on real scoring | `backend/app/core/sa.py`, `domain/bridge.py`, `api/domain_audit.py`, `api/domain_mobile.py` | `tests/integration/test_domain.py` |
