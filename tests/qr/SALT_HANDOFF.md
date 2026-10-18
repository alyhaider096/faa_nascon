# Day 2 signing integration update - 18 October 2026, 13:54 PKT

## Extended-deadline checkpoint - 18 October 2026, 14:10 PKT

The user explicitly extended code/push authorization to **14:20 PKT**. This
checkpoint supersedes the earlier freeze and failed-load/low-coverage statuses
for the verified local targets, while retaining those runs as history.

Application optimization source: `75f24268c30ae334b6e7396bb22de717f651b725`.
Additional resilience tests / coverage generator: `ad49d49`.

| Gate | Actual measured result |
| --- | --- |
| Official unchanged k6 profile | **PASS**, 500 viewers + 50 posters for 15s, 14,757 requests, zero failed requests, p95 **693.66 ms**; `tests/reports/k6-summary.json` |
| Four screenshot adversarial scenarios | **7 passed**, including two QR status variants and two inspection concurrency safeguards; `grading-scenarios.xml` |
| Complete regression after application change | **458 passed, 17 skipped, 8 warnings in 223.97s**; `extended-tests.xml` |
| Additional resilience / invitation lifecycle | **5 passed**, 2 warnings in 8.90s; `resilience-tests.xml` |
| Measured functional-region coverage | streaming 95.92%, costream 90.78%, qr_guest 93.61%, moderation_dlq 96.90%, observability 90.00%; COVERAGE_DAY2.json with reproducible per-function denominators in day2-coverage-mapping.json |
| GitHub Actions salts | User explicitly approved exact keys/destination. Both encrypted secret PUTs returned 201 and both repository secret names were verified present; values never printed/committed. |

The prior native k6 failures were confounded by an ADB forward owning
127.0.0.1:8080 to the Pixel's port 18080. The old proxy run also had transport
issues. Preserved as `k6-summary-adb-collision.json` and earlier proxy reports.
An exclusive Linux API using the pinned backend requirements and mounted source,
with k6 sharing its network namespace, removed both ambiguities. Before read
coalescing that isolated target had zero failures but p95 2.07s, preserved as
`k6-summary-linux-before-coalescing.json`. After optimization both gates passed.

QR inspection now shares only overlapping in-flight reads. Completed results
are removed immediately, errors can be retried, and cancellation of one viewer
does not cancel other viewers. Actual scans retain per-request transactional
increments. Tests verify the next read sees changed state immediately.

Load command: `docker run --rm --network container:fatima-load-api --mount
<repo>:/scripts grafana/k6:latest run --quiet
--summary-export=/scripts/tests/reports/k6-summary.json /scripts/tests/k6_load.js`.
Target: owned isolated Linux API, PostgreSQL gridqa, Redis DB 1; no Windows
localhost or socat proxy. Full regression uses separate nascon_test / Redis DB 0.
Regression command: `python -m pytest tests -q -p no:cacheprovider --cov=backend/app
--cov-report=json:tests/reports/extended-coverage.json
--junitxml=tests/reports/extended-tests.xml`. Additional resilience command uses
tests/integration/test_day2_resilience.py with --cov-append and its separate XML.
Coverage reproduction: `python tests/day2/measure_coverage.py
tests/reports/extended-coverage.json`. Scope excludes module initialization and
external source dependencies; all functions in the selected API/domain/worker
files are mapped, shared worker functions counted transparently in both groups.
Media probe/recovery tests use simulated external service responses and do not
replace live media acceptance.

The four-way host-drop state preserves the composite URL and chat room; actual
continuous playback and zero zombie FFmpeg/WebRTC processes are **NOT VERIFIED**
without a real publisher. Cross-surface chat remains skipped. Abdullah's deployed
keys/media and the full clean Compose startup remain unverified. Earlier latest
CI failed solely at missing-secret validation; keys are now provisioned, but the
next workflow must be observed before claiming a CI pass. Existing actual Grid
3-pass and Pixel 2-pass/1-skip reports remain applicable to unchanged frontend.


The integrated backend now declares, forwards and loads DAY2_SALT. The readiness
checker passes all static wiring checks using the ignored local env file.
Six selected independent HTTP QR checks passed against the isolated local API,
including private-key signature validation and real SVG/PNG/PDF decoding.
No literal key was pushed. Teammates must provision both supplied keys privately
in their own backend runtime. GitHub secrets and Abdullah's deployed runtime
remain UNVERIFIED. The preparation checklist below is retained as history;
its earlier missing-wiring statements are superseded by this update.

# Release blocker: Day 2 signing configuration

Current status at QR preparation: **NOT COMPLETE**. Private values are available
on Fatima's workstation, but Day 2 runtime/CI wiring and live verification are
not established. A pushed test oracle cannot configure the backend's key.

The real keys were supplied in the private handbook. A Git-ignored
`.env.day2.local` containing both exact values has now been preserved in the local
checkout. It is not a Git artifact and will not appear in a teammate's clone.
Fatima also has a private output copy for transfer to the intended teammates.
Share that configuration through the team's private channel; do not put it into
source, APKs, reports, issue comments or public logs.

## Abdullah's integration checklist

- [ ] Add an empty `DAY2_SALT=` entry to `.env.example`.
- [ ] Forward `DAY2_SALT` to API and worker in root Compose, alongside DAY1_SALT.
- [ ] Read DAY2_SALT from the runtime environment; keep it out of object repr/logs.
- [ ] Fail clearly when Day 2 signing is requested without a configured key.
- [ ] Explicitly select the Day 2 key for stream, co-stream, QR, cart merge and
  moderation signatures. `sign_record()` currently defaults to DAY1_SALT.
- [ ] Preserve Day 1 event/receipt signatures and JWT behavior using DAY1_SALT.
- [ ] Transfer the real values privately to the deployed backend runtime. A local
  `.env` file alone is insufficient unless the chosen launch mechanism loads it.
- [ ] Set repository Actions secrets `DAY1_SALT` and `DAY2_SALT` if CI uses them,
  and map them explicitly into the workflow environment and containers. Secret
  presence and environment forwarding are separate checks.
- [ ] Commit and push the non-secret wiring and tests to the integrated branch.
- [ ] Restart/rebuild the intended service and verify a real QR signature using
  Fatima's independent oracle, without fetching or printing the key through APIs.

For Compose environment blocks the required forwarding is structurally:

```yaml
environment:
  DAY1_SALT: ${DAY1_SALT}
  DAY2_SALT: ${DAY2_SALT}
```

Actual values belong in the private environment, not this YAML. An env file with
DAY2_SALT does not inject it into a container whose environment is never wired.
CI secrets also do not configure Abdullah's laptop automatically.

## Verification without revealing the key

```powershell
python tests/qr/check_salt_readiness.py --env-file .env.day2.local
```

The script reports only supplied/missing flags and static wiring checks. At
preparation it reports both private values supplied and all three Day 2 wiring
checks blocked. It does not prove CI secrets exist or that a running service
loaded the values. Do not use resolved Compose/environment dumps as public
evidence. Load DAY2_SALT privately into the QA process and run QR acceptance once
the service is available; never pass the literal key as a CLI argument.

## If Fatima's session or usage ends

The hourly checkpoint prompt names this blocker and this file. Keep the blocker
open until non-secret wiring is pushed and a deployed independent signature
passes. The local secret copy and original private handbook survive this chat;
they do not depend on the assistant recalling the value. No GitHub secret or
teammate runtime configuration has been set by this QA preparation.
