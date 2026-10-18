# Frontend/backend integration contract verification

Tested source: `4ef28e1d595fd3ec0757c053b4501f2611a1b3f8`, including frontend
commit `c3848bd`. Fetched origin/main before capture; no newer backend changes
were present. Captured 18 October 2026 at 12:13 PKT against a real isolated local
HTTP/WebSocket server with PostgreSQL 16 and Redis 7, using public test signing
configuration. These are not responses from Abdullah's machine.

The supplied LAN health URL timed out after five seconds. Shared runtime, CI
secrets and LAN media cannot be confirmed. No shared backend was reset, hosted,
reconfigured or otherwise mutated. No teammate message was sent.

## Status for each requested item

| # | Status | Actual result |
| --- | --- | --- |
| 1 Hosting | **Missing backend hosting; clean-install blocker** | `GET /web/matches/match-m1/live` and `/q/m1-live` both 404. No SPA/static hosting or QR redirect is mounted. `npm ci` fails; web export succeeds using previously installed dependencies. |
| 2 Public reads/reset | **Missing public routes; different seed** | Both public endpoints return 404. Reset seeds `match-001` at 2:1, not `match-m1` at 1:0. The named jersey product and L variant exist. Authenticated Day 1 match/pinned reads are different routes, not equivalent public/media endpoints. |
| 3 Guest authorization | **Missing session/staging and FAILED guard** | Guest session/staging/chat return 404. Valid audit checkout and score writes bearing the seeded guest token return 201. Member checkout rejects that token with 401 UNAUTHENTICATED, not the required 403 GUEST_WRITE_FORBIDDEN. |
| 4 Realtime | **Different route, partial member-only implementation** | Required `/ws/matches/{id}` rejects member and guest handshakes (403). `/ws/v1/matches/{id}` accepts a real member JWT; guest handshake fails. Actual score and merchandise frames lack room sequence numbers and direct score values; chat/invitation/host-change frames are missing. |
| 5 Login/merge/cart | **Login implemented; merge/member cart missing** | Login returns token, token_type, user and tenant. `/audit/v1/guest/cart-merge` and `GET /api/v1/cart` return 404. No actual replay or stock-limit result can be provided for a missing merge route. |
| 6 Media | **Missing** | Generate/rotate/revoke product routes and audit stream-key fallback return 404. No implemented recording/VOD API or verified phone-reachable WHIP/HLS/composite URL is available. |
| 7 Co-stream commands | **Missing** | The current action route returns 404 for create/join/invite/set_layout/mute/spotlight/kick/leave/stop. No implemented replacement route, signed invite format or authoritative host-change frame was found. |
| 8 QR | **Missing** | Metadata, short-link redirect and all three export routes return 404. Stable links, changing destinations/signatures and valid scannable exports cannot be confirmed. |

## Real HTTP examples

Every 404 NOT_FOUND route below returned this actual response body:

```json
{"error":{"code":"NOT_FOUND","message":"Not Found","details":{}}}
```

| Item | Actual request | HTTP response |
| --- | --- | --- |
| 1 | `GET /q/m1-live` | 404 NOT_FOUND, no Location header; not a 302 |
| 2 | `GET /api/v1/public/matches/match-m1` | 404 NOT_FOUND |
| 2 | `GET /api/v1/public/costream/cs-session-101` | 404 NOT_FOUND |
| 3 | `POST /api/v1/guest/session` with `{}` | 404 NOT_FOUND |
| 5 | `POST /audit/v1/guest/cart-merge` with seeded token, user-admin and one L jersey | 404 NOT_FOUND |
| 6 | `POST /api/v1/stream/key` with generate/player-alpha-1/qa-contract | 404 NOT_FOUND |
| 7 | `POST /api/v1/costream/sessions/cs-session-101/actions` with `{"action":"join"}` | 404 NOT_FOUND |
| 8 | `GET /audit/v1/qr/match-m1?inspect=true` | 404 NOT_FOUND |

The adjacent `Integration-Contract-Examples.json` output and repository file
`tests/reports/integration-contract-examples.json` contain all 36 actual HTTP
request/response pairs and socket outcomes, including each export and co-stream
action. Credentials and member/payment tokens are redacted. Missing routes have
real failure examples, not invented success responses.

### Actual login response

`POST /api/v1/auth/login` using the seeded admin account returned HTTP 200:

```json
{
  "token": "<redacted>",
  "token_type": "Bearer",
  "user": {
    "user_id": "user-admin",
    "email": "admin@nascon.test",
    "role": "super_admin",
    "display_name": "Platform Admin",
    "tenant_id": null,
    "league_id": null,
    "club_id": null,
    "player_id": null
  },
  "tenant": null
}
```

### Actual guest error and unsafe acceptance

`POST /api/v1/checkout` bearing the seeded guest token returned HTTP 401:

```json
{"error":{"code":"UNAUTHENTICATED","message":"Invalid, expired or tampered token.","details":{}}}
```

`POST /audit/v1/events` bearing the same guest token and this valid local test
event returned **HTTP 201**, rather than the required guest rejection:

```json
{"event_id":"contract-guest-goal","match_id":"match-001","type":"score","payload":{"team_id":"club-alpha-1","event_type":"goal"}}
```

Actual response:

```json
{"event_id":"contract-guest-goal","match_id":"match-001","type":"score","sequence":5,"match_version":5,"signature":"dce0e4f4029d815fff44fe1b1c9c0ceee4655871860d3c9578c0553ba480c4b2"}
```

The valid local guest audit checkout similarly returned 201 with status paid and
total_minor 450000. Its full response is in the sanitized JSON. These mutations
were confined to disposable QA data. No exact GUEST_WRITE_FORBIDDEN error body
was observed; providing one as if returned would be inaccurate.

## Actual socket frames

Connected as a member to `/ws/v1/matches/match-001?token=<member-token>`:

```json
{"type":"hello","match_id":"match-001"}
```

After a real member score write, following the earlier local guest probe:

```json
{"type":"score_updated","match_id":"match-001","event_id":"contract-member-goal","version":6}
```

After a real merchandise pin request:

```json
{"type":"product_pinned","match_id":"match-001","product_id":"prod-jersey-001","name":"Alpha FC Home Jersey"}
```

There is no sequence field or direct score in these frames. No chat, invitation
or host-change frame is implemented/captured. This member-only Day 1 socket is
not a confirmed replacement for the required guest/co-stream subscriptions.

## Build and runtime handoff

- Node 24.14.0 / npm 11.9.0: `npm ci --no-audit --no-fund` fails EUSAGE, missing
  @emnapi/core@1.11.3 and @emnapi/runtime@1.11.3 lock entries.
- `npm run web:export -- --output-dir ../../../work/integration-web-dist`
  succeeds using the existing installed dependencies (917 modules). This proves
  bundling, not a clean install, static hosting, SPA fallback or functional APIs.
- No backend source/config was edited to serve the export; deployment remains
  Abdullah's integration responsibility. No working 302 is present to confirm.
- Both salts stay outside frontend/source artifacts. Day 2 environment loading,
  API/worker forwarding and CI/runtime provisioning remain open; the ignored
  private environment copy does not configure a teammate's running service.
- Priorities: implement guest rejection immediately; integrate the Day 2 routes
  and exact reset seed; wire Day 2 signing privately; serve the SPA; then verify
  real media/host changes and the full browser/phone flows on one integrated SHA.

The diagnostic capture completed successfully, but **the eight integration
contracts did not pass acceptance**. Its JUnit success means the capture process
ran, not that missing/incorrect feature behavior was accepted.
