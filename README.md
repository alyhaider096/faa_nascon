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

## Backend handoff

The official contract is the supplied Part I specification. The backend must expose port 8080, boot through `DAY1_SALT=<value> docker compose up -d --build`, and implement the exact audit routes, status codes, and signatures. Never commit the real salt. The mobile team will replace mock reads with authenticated `/api/v1/*` adapters and retain the audit-compatible offline action envelope.

See [ARCHITECTURE.md](ARCHITECTURE.md), [SYSTEM_DESIGN.md](SYSTEM_DESIGN.md), and [BACKEND_HANDOFF.md](BACKEND_HANDOFF.md). The release artifact required for Android judging is `mobile/release/app-release.apk`; it must be built and committed before the deadline.
