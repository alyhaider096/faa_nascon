# Day 2 evidence index

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
