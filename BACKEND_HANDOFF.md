# Backend handoff: high-risk scoring gates

The official Part I specification is the binding contract. This note is a short implementation gate, not a replacement for Sections 5.2, 5.4, 5.5, 5.9, 5.11, 5.12 and 5.14.

## Clean startup and deterministic reset

- From a fresh Ubuntu clone with only Docker installed, `DAY1_SALT=<team slip value> docker compose up -d --build` must start the API on host port **8080** in under 10 minutes. `/health` must return 200 within 120 seconds. No manual migrations, local Postgres, extra files, or network access after the build step.
- Pass `DAY1_SALT: ${DAY1_SALT}` into the API/worker containers. Never commit the actual salt or generate signatures on the phone.
- `POST /audit/v1/reset` must recreate the exact same seeded IDs, five demo accounts, stock, rule configurations and fixture data every time. Call it twice and compare the resulting public state, including account login and inventory. Use fixed seed data, not random IDs or wall-clock-dependent values.
- Test the exact clean-start command on a machine or CI runner with empty Docker volumes. A successful local `docker compose restart` is not evidence of clean startup.

## No sport-name branches

- Store scoring events, points, innings/round rules, roster constraints and tie-break order as sport configuration data. The grader creates a mystery sport through `POST /audit/v1/sports`.
- Domain code must not special-case strings such as `football`, `goal`, `cricket`, or `wicket`. Those strings are fine in seed fixtures and UI labels, but not in branches that calculate scores or validate events.
- A test should create an unknown sport with arbitrary event names, start a match, score, compensate, and read the projection without code edits.

## Merchandise and mock gateway

- `POST /audit/v1/checkout` is the payment contract. Accept the client `order_id`, `customer_id`, variant IDs, optional `WELCOME10`, and `payment.token` (`tok_success`, `tok_declined`, `tok_capture_fail`). The gateway is team-owned mock code—not Stripe or a live payment processor.
- Reserve all requested variants atomically; release reservations on either payment failure; commit stock on capture. Twenty simultaneous purchases of the final unit must yield exactly one 201 and nineteen 409 responses, with stock and reserved counts both zero at the end.
- Generate the signed receipt and server-side PDF. `receipt.signature` is HMAC-SHA256 of `order_id + "|" + canonical_json(receipt.payload)` using `DAY1_SALT`. Include `pdf_base64` in the exact response shape. The mobile checkout sends this route in live mode and shares the returned PDF.
- Mobile catalogue, pinned product and cart need read APIs backed by the same products and inventory. A hard-coded demo catalogue does not prove backend stock correctness.

## Offline mobile boundary

- `POST /audit/v1/offline-sync` receives 1–100 actions with `action_id`, `type`, `queued_at` (UTC, second precision), `base_version`, and the original audit request body as `payload`.
- Only `score_event` and `roster_transfer` are valid queue types. The latter wraps transfer/loan/release bodies from `/audit/v1/roster/transfer`; add-player UI needs a separate normal API because it is not a Section 5.14 queue action.
- Return per-action applied, duplicate or rejected status with exact resolution/error fields; conflicts must not turn the whole envelope into a failure. The mobile app must show plain-language reasons and leave rejected results visible.

## Before submission

Run the reference signature vector, reset-twice comparison, mystery-sport test, and 20-buyer checkout burst. Add the actual implementation/test paths to `TRACEABILITY.md`; generate `COVERAGE.json` from measured coverage only. Commit the clean-start Compose files and the built `mobile/release/app-release.apk` before the final push deadline.
