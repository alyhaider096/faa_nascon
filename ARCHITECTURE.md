# Architecture

## Responsibilities

| Component | Owner | Responsibility |
| --- | --- | --- |
| React Native mobile app | Mobile team | Role-aware navigation, cached views, offline queue, checkout UI and score/roster entry |
| FastAPI API | Backend team | Authentication, authorization, business rules, exact `/audit/v1/*` contract |
| PostgreSQL | Backend team | Tenants, leagues, fixtures, append-only events, inventory, orders, audit trail |
| Redis and internal worker | Backend team | Internal queue, rate limiting, asynchronous tasks and real-time fanout |
| Docker Compose | Backend team | One-command, clean-machine backend boot on Ubuntu and port 8080 |
| GitHub Actions/grader | Organizers | Checkout final eligible commit, boot Compose, run hidden vectors |

## Mobile boundaries

Expo Router contains screen routes under `mobile/src/app`. Shared UI lives in `mobile/src/components`, mock fixtures and catalogue in `mobile/src/data`, and session, cache, cart and queue state in `mobile/src/state`. SecureStore holds the local demo account indicator; a live JWT must also be stored there when live authentication is connected. SQLite persists cached fixtures, standings, club profile, server address, and offline actions. The server is authoritative for permissions, scores, inventory and payment outcomes.

The current app is a frontend preview with mock data. The live checkout adapter calls `/audit/v1/checkout`, and the sync adapter calls `/audit/v1/offline-sync`; live login and read APIs are pending integration. Turning off Demo data blocks local demo login; it does not claim that live authentication is implemented.

## Security and integrity

- `DAY1_SALT` is passed only to the backend container as an environment variable; no mobile code receives it.
- The backend computes HMAC-SHA256 over `id + "|" + canonical_json(payload)` for events and receipts.
- Mobile role visibility improves usability; backend RBAC remains the enforcement point.
- Demo credentials are public sample accounts and are not production secrets.
- Local hotspot HTTP is enabled for judging; a production deployment should use HTTPS.
- Offline actions retain their client ID and base version so server conflict resolution can be shown without silently overwriting work.
- Sport/event labels in mock fixtures are configuration data. Scoring and standings rules must read sport configuration; backend domain code must not branch on particular names.

## Backend integration contract

The official Part I document is binding for `/audit/v1/*`. For mobile reads and login, the team should expose authenticated `/api/v1/auth/login`, `/api/v1/me`, `/api/v1/fixtures`, `/api/v1/standings/{league_id}`, `/api/v1/clubs/{club_id}`, `/api/v1/products`, `/api/v1/matches/{match_id}` and `/api/v1/orders/{order_id}`. Mobile writes should route through the same domain services as the audit wrappers. Until the backend publishes these routes, the app keeps its visible Demo mode and does not pretend that mock checkout or scoring changed server state.
