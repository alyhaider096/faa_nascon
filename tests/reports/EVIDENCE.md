# Day 2 evidence index

## Documentation status update - 18 October 2026, 12:36 PKT

- Latest fetched main: `61efc02593985bc71b57be6806b44c10139c1e07`; no new backend commit at update time.
- User confirmed the team is waiting for Abdullah before integrated execution.
- TRACEABILITY.md now has a current FR/NFR/gate matrix with owners, evidence and next actions. Older baseline mappings and run history preserved.
- No tests or live connectivity probes rerun for this documentation-only update. Existing local failures and skipped/deployed-not-run distinctions remain explicit.
- Salt runtime/CI wiring, direct guest rejection, hosting/reset, media/QR/merge, device/Grid/load readiness and measured Day 2 coverage remain unresolved until evidenced.

## Initial QA checkpoint

- Date: 18 October 2026, Asia/Karachi.
- Source baseline: c9ad86fb44730cb02f3556727596ceec8b4530fa.
- Environment: Windows QA workstation; fresh repository clone. No deployed target configured.
- Candidate supplied by user: `http://10.155.234.142:8080`; read-only `/health` probe timed out after 8 seconds. Target remains unverified; no reset or mutation was attempted.
- Oracle command: `python -m unittest discover -s tests/day2 -v` (bundled Python 3.12).
- Actual result: 5 passed; `day2-oracle.txt`. These check the independent oracle only.
- Domain regression command: `python -m pytest tests/domain --junitxml=tests/reports/domain-regression.xml -q` using isolated QA Python 3.12, pytest 8.3.5, SQLAlchemy 2.0.40 and SQLite fixtures.
- Domain result: 152 passed, 4 skipped, 1 dependency deprecation warning in 3.35 seconds. PostgreSQL opt-in tests skipped; this is not deployed-platform acceptance.
- Test-source revision: the Git commit containing this entry; the baseline SHA above does not contain these tests.
- Docker CLI exists, but daemon inspection failed with access denied; clean-stack execution is not established.
- adb, Appium and k6 were not found on the current PATH. This is not proof they are absent from the machine.
- Day 2 production coverage: not measured. No illustrative percentages copied.
- DAY1_BASE_SHA: organizer confirmation still needed; baseline tip is not assumed to be the locked SHA.
- Private configuration and handbook remain outside the repository.

## Domain integration handoff checkpoint

- Source: first QA commit `86920225642da50e5b1e4f6b82eebe7c7feab1bd` plus the test/docs in the commit containing this entry.
- Environment: same isolated Windows QA Python 3.12, pytest 8.3.5, SQLAlchemy 2.0.40; SQLite fixtures, no deployed target.
- Focused command: `python -m pytest tests/domain/test_day2_handoff.py -q --junitxml=tests/reports/domain-handoff.xml`.
- Result: 3 passed in 0.20s; persistence/replay/compensation/rollback and postponement boundary checked.
- Full command: `python -m pytest tests/domain -q --junitxml=tests/reports/domain-regression.xml`.
- Result: 155 passed, 4 skipped, 1 dependency deprecation warning in 2.46s. The PostgreSQL cases remain skipped.
- Handoff: `backend/DAY2_DOMAIN_HANDOFF.md`. No production logic was changed. No live QR/media/socket claims.

## RBAC and mobile event checkpoint

- Baseline: `40e23bfded60d0f82ec7d937fd47a2cac3d163d7`; new tests/fixes are in the commit containing this entry.
- Date: 18 October 2026, approximately 11:15-11:21 Asia/Karachi.
- Environment: isolated local PostgreSQL 16 and Redis 7 on loopback ports 55432/56379, Windows Python 3.12, pytest 8.3.5, pinned backend dependencies. Shared backend untouched.
- Command: `python -m pytest tests/rbac/test_rbac.py tests/integration/test_platform.py tests/integration/test_domain_tenant_scope.py -q --junitxml=tests/reports/rbac-baseline.xml`.
- Result: 67 passed in 31.78s; two pytest cache permission warnings, no assertion failures.
- Command: `python -m pytest tests/integration/test_mobile_event_roles.py -q -p no:cacheprovider --junitxml=tests/reports/mobile-event-roles.xml`.
- Result: 22 passed in 14.42s. Includes scores and compensation, all roles, both submission paths, replay and foreign-league denial. Earlier exploratory combined run also passed 24 cases; its XML was replaced by this focused final report.
- Mobile: `npm run typecheck` and `CI=1 EXPO_NO_TELEMETRY=1 npm run lint` passed after final changes. Initial lint was blocked by Expo telemetry writing outside workspace; disabling telemetry allowed the normal lint command to pass.
- Review: `tests/reports/RBAC_REVIEW.md`. Device/browser execution and APK rebuild not run; no production coverage inferred.

## QR preparation checkpoint

- Baseline: `96fc133ab788d1da972e0b484ab9bcc20fbd4da8`; new tests/docs are in the commit containing this entry.
- Date: 18 October 2026, Asia/Karachi; local Windows QA workstation.
- Command: `python -m pytest tests/qr -q -p no:cacheprovider --junitxml=tests/reports/qr-preparation.xml`.
- Result: 21 passed, 11 skipped in 0.76s. Passing cases verify independent QA helpers and synthetic SVG/PNG/PDF QR decoding; skipped cases are live acceptance, not passes.
- Command: `python -m pytest tests/integration/test_qr_domain_fixtures.py -q -p no:cacheprovider --junitxml=tests/reports/qr-domain-fixtures.xml`.
- Result: 1 passed in 4.79s against isolated PostgreSQL 16/Redis 7 and an actual in-process HTTP backend. Script creates four unique score-domain fixtures, reads their states and preserves the existing baseline match. No QR service is present or claimed.
- QR tools: Python 3.12, pytest 8.3.5, httpx 0.28.1, Pillow 12.3.0, PyMuPDF 1.28.2, zxing-cpp 3.1.1, qrcode 8.2.
- Salt preflight: both private values supplied in ignored local environment file; all three static Day 2 wiring checks blocked. No CI secret or deployed signing configuration verified. See `tests/qr/SALT_HANDOFF.md`.
- Scope: QA files, domain-fixture integration test, traceability and evidence only; no UI, service, migration, shared configuration or CI edits.
- Exact-value scan found no real salts in tracked/unignored files under 2 MB; private environment file is Git-ignored. No key material printed in reports.

## Scheduled 12:05 PKT checkpoint - 18 October 2026

- Integrated tested source: `c3848bdd0b27163eec6111679f80fdae6a3b7a41`; origin/main fetched and no newer commit was present at start.
- Environment: Windows isolated Python 3.12, pytest 8.3.5; SQLite domain fixtures and synthetic QR export assets. Backend dependencies now match backend/requirements.txt. No deployed target configured for acceptance.
- Command: `python -m pytest tests/domain tests/qr -q -p no:cacheprovider --junitxml=tests/reports/checkpoint-1205.xml`.
- Actual result: 176 passed, 15 skipped, two dependency deprecation warnings in 2.97s. Four skipped cases need PostgreSQL opt-in configuration; eleven skipped QR cases need live target/fixtures and mutation authorization. This command did not start PostgreSQL or establish live QR acceptance.
- Command: `python tests/qr/check_salt_readiness.py --env-file .env.day2.local`.
- Actual result: exit 1; both private values supplied, all three static DAY2_SALT wiring checks BLOCKED. No key material printed; runtime/CI keys are not verified.
- Read-only health probe: candidate `http://10.155.234.142:8080/health` timed out after 5s. No reset, fixture setup or remote mutation attempted.
- Frontend review evidence now retained in `FRONTEND_REVIEW_330d475.md` and `DEMO_REVIEW_c3848bd.md`. Source-level reproductions were described to the user; native/device/live-media acceptance was not claimed.
- Recent review checks: TypeScript and lint passed on c3848bd. On 330d475, web export and Expo Doctor (20/20) passed after a non-lockfile-changing local install; clean npm ci failed and remains open. These were review checks before this heartbeat, not rerun as part of the 176-test command.
- No COVERAGE_DAY2.json generated: no measured five-module production coverage is available. Day 1 mappings and coverage artifacts preserved.
- Checkpoint changes contain evidence/traceability only; Ali's UI and Abdullah's implementation/configuration were not edited.

## Eight-contract verification capture - 18 October 2026, 12:13 PKT

- Tested source: `4ef28e1d595fd3ec0757c053b4501f2611a1b3f8`, fetched origin/main; includes frontend c3848bd.
- Target: real in-process HTTP/WebSocket server on loopback, isolated PostgreSQL 16 / Redis 7. Public test signing environment; no real team key injected. Shared deployed health probe timed out after five seconds.
- Executed command: `python -m pytest tests/integration/test_contract_capture.py -q -p no:cacheprovider --junitxml=tests/reports/integration-contract-capture.xml`.
- Runner was subsequently moved to `tests/diagnostics/capture_integration_contracts.py` to keep diagnostics outside default acceptance-test collection. Invoke explicitly with pytest for future captures.
- Capture result: 1 diagnostic completed in 3.38s, 36 sanitized actual HTTP records and four WebSocket outcomes. This is NOT an all-contracts pass. Actual feature failures/missing routes are detailed in `INTEGRATION_CONTRACT_STATUS.md`.
- Critical observation: guest bearer on valid audit checkout and score event returned 201; required 403 GUEST_WRITE_FORBIDDEN is not implemented. These writes touched only disposable QA data. Member checkout returned 401; chat/session/merge and other missing routes returned 404.
- Existing seeded match is match-001 at 2:1, not required match-m1 at 1:0. Product prod-jersey-001 / var-jersey-001-L exists. Member login and old authenticated score/pin socket frames were captured with tokens redacted.
- Clean npm ci failed EUSAGE (missing emnapi core/runtime lock entries). Export of current frontend succeeded separately with existing node_modules, to an intermediate directory outside the repo. No backend SPA deployment performed.
- Reports: `integration-contract-examples.json`, `integration-contract-capture.xml`, `INTEGRATION_CONTRACT_STATUS.md`. No implementation/config, teammate runtime or frontend source was edited.

## Recording rules

For each run append exact tested SHA, timestamp, target URL/environment, command,
tool versions, device/build identity when applicable, counts, duration, actual
failures and artifact paths. Distinguish unit, integration and live acceptance.
Capture failed and blocked runs as well as passing runs. Never store real salts,
tokens, environment dumps or private handbook contents in reports.

For each push record local SHA, branch, remote SHA verification, timestamp and
available GitHub receipt/workflow. A local commit timestamp is not a push receipt.

## First successful push

18 October 2026, approximately 11:09 PKT: pushed QA checkpoint 86920225642da50e5b1e4f6b82eebe7c7feab1bd to origin/main. Git push reported c9ad86f..8692022 main -> main; git ls-remote origin refs/heads/main returned the identical full SHA. This receipt entry will be included in the next checkpoint; local clock and Git output do not substitute for a GitHub server event timestamp.
