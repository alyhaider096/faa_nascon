# LeagueOps · NaSCon '26

Multi-sport league and club operations platform. This repository is being built during the Part I sprint. The mobile application currently runs with clearly labelled mock data; the backend team owns the Docker Compose stack and the binding `/audit/v1/*` implementation.

## Mobile app

Requirements: Node 20.19+, Android phone or emulator, Android SDK 36 for local APK builds. This project uses [Expo SDK 55](https://docs.expo.dev/versions/v55.0.0/).

```bash
cd mobile
npm ci
npx expo start
```

The app's Settings screen stores the backend laptop address, for example `http://192.168.1.20:8080`. A physical phone and backend laptop must be on the same hotspot. Demo mode previews the UI without the backend. The red/green status bar and sync queue show offline state. Demo purchases are marked as demo receipts and are not signed by the backend.

Demo accounts all use `Nascon@26`: `admin@nascon.test`, `organizer@nascon.test`, `manager@nascon.test`, `player@nascon.test`, and `viewer@nascon.test`.

## Run the backend

```bash
cp .env.example .env            # then put the organizer-supplied value after DAY1_SALT= (file is git-ignored)
DAY1_SALT=<secret> docker compose up -d --build
curl http://localhost:8080/health
```

The API listens on host port 8080 (`http://<laptop-LAN-IP>:8080` from a phone, `http://10.0.2.2:8080` from an Android emulator). The service refuses to start if `DAY1_SALT` is missing. Postgres 16 and Redis 7 run in the stack; a worker relays the transactional outbox to a Redis Stream. MinIO is optional: `docker compose --profile objectstore up -d`.

Services: `db`, `redis`, `api` (FastAPI, single worker so the in-memory rate limiter is exact), `worker`. Data persists in named volumes across `docker compose restart`.

Demo users (published, password `Nascon@26`): `admin@nascon.test` (super_admin), `organizer@nascon.test` (league_organizer, league-alpha-1), `manager@nascon.test` (club_manager, club-alpha-1), `player@nascon.test` (player, player-alpha-1), `viewer@nascon.test` (viewer).

Mobile API: `POST /api/v1/auth/login`, then `Authorization: Bearer <token>` on `/api/v1/{me,bootstrap,clubs/{id},products,checkout,orders/{id},orders/{id}/status,matches/{id}/pin,matches/{id}/pinned,roster/transfer,roster/history/{player},offline-sync}`; realtime at `ws://<host>:8080/ws/v1/matches/{match_id}?token=<jwt>`. Domain reads/writes: `GET /api/v1/matches/{id}`, `POST /api/v1/matches/{id}/events` (organizer/admin), `GET /api/v1/leagues/{id}/standings`, `POST /api/v1/fixtures/preview`. See [docs/INTERFACES.md](docs/INTERFACES.md). Audit routes live under `/audit/v1/*`.

## Tests

```bash
TEST_DATABASE_URL=postgresql://user:pw@127.0.0.1:5432/throwaway ./run_tests.sh
```

Needs a throwaway PostgreSQL 16 and a Redis (`TEST_REDIS_URL`); optionally `DOMAIN_TEST_DATABASE_URL=postgresql+psycopg://.../other_db` enables the domain concurrency tests. Tests use only the public salt `demo-salt`. The script exits non-zero on failure and rewrites `COVERAGE.json` from measured line coverage; areas whose source does not exist are reported as 0.0.

## Backend handoff

The official contract is the supplied Part I specification. The backend must expose port 8080, boot through `DAY1_SALT=<value> docker compose up -d --build`, and implement the exact audit routes, status codes, and signatures. Never commit the real salt. The mobile team will replace mock reads with authenticated `/api/v1/*` adapters and retain the audit-compatible offline action envelope.

See [ARCHITECTURE.md](ARCHITECTURE.md), [SYSTEM_DESIGN.md](SYSTEM_DESIGN.md), and [BACKEND_HANDOFF.md](BACKEND_HANDOFF.md). The release artifact required for Android judging is `mobile/release/app-release.apk`; it must be built and committed before the deadline.
