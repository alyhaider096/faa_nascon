# Mobile integration status · 17 Oct 2026

The Android app uses the backend address saved in Settings. Demo mode remains available for UI review. Live mode uses `/api/v1/auth/login`, stores the JWT in Android SecureStore, and sends `Authorization: Bearer` on protected requests. No signing salt is bundled in the app.

## Backend actions needed for the judged live flow

1. The laptop server answered `/api/v1/ping`, but returned `404 Not Found` for `/api/v1/auth/login`, `/api/v1/bootstrap` and `/api/v1/clubs/club-alpha-1` at 13:31 PKT. Rebuild/restart the Docker backend from current `main` and verify these routes before phone testing. A later connection attempt timed out while the backend was likely restarting.
2. `/api/v1/bootstrap` currently returns leagues and clubs without fixtures or match IDs. The app only opens real match IDs supplied by a live response; it does not display `match-001` demo data as live. Add a tenant-scoped `GET /api/v1/fixtures` or include fixtures in bootstrap, with match ID, home/away team names and IDs, time and venue. After `/reset`, a judge needs at least one accessible real match for Task A and scoring.
3. `GET /api/v1/leagues/{id}/standings` reads domain leagues, while `/reset` only seeds `ref_leagues`. It currently returns `LEAGUE_NOT_FOUND` for `league-alpha-1` until the domain league/fixtures are registered. Make reset create a repeatable match/league fixture set or provide a fixture setup step before judging.
4. `GET /api/v1/matches/{id}` projects scores but does not include allowed scoring event types. The app offers an event type field when no list is supplied, without branching on sport names. Returning the active sport's `scoring_events` keys would enable rule-driven choices.
5. `GET /api/v1/clubs/{id}` returns player IDs, but no squad IDs. The app discovers each player's current squad through `/api/v1/roster/history/{player_id}` and derives destination squads from other visible clubs' players. A club with an empty roster cannot provide a destination. Expose tenant/league-scoped squad IDs and names to make transfers reliable after grader setup.
6. No authenticated player-registration route exists. The live “Add player” form explains this; transfer, loan and release use actual IDs from server responses. Demo mode can still add a local preview player.

## Mobile checks

- `npm run typecheck`, `npm run lint` and `node scripts/check-api.cjs` pass.
- The browser preview reaches Fixtures → Match detail → Product → Checkout → Receipt in demo mode.
- Physical Pixel 8 Pro is connected via ADB. APK build/install and airplane-mode sync verification are still pending.
