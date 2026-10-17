# Mobile integration status · 17 Oct 2026

The Android app uses the backend address saved in Settings. Demo mode remains available for UI review. Live mode uses `/api/v1/auth/login`, stores the JWT in Android SecureStore, and sends `Authorization: Bearer` on protected requests. No signing salt is bundled in the app.

## Backend actions needed for the judged live flow

1. At 14:17 PKT the running laptop server returned 200 for `/health` and demo organizer login, and 401 for bootstrap without a token. The login response has the expected `token`, `user`, and `tenant` fields. Authentication is now reachable.
2. The authenticated `/api/v1/bootstrap` response has `user`, `tenant`, `leagues`, `clubs`, `products`, and `capabilities`, but no fixtures or match IDs. The app only opens real match IDs supplied by a live response; it does not display `match-001` demo data as live. Add a tenant-scoped fixture-list GET or include fixtures in bootstrap, with match ID, home/away team names and IDs, time and venue. The guessed `GET /api/v1/leagues/{id}/fixtures` currently returns 404.
3. The first league and club IDs returned by the organizer bootstrap gave 404 from `GET /api/v1/leagues/{id}/standings` and `GET /api/v1/clubs/{id}` on the running server at 14:17 PKT. Make `/reset` seed corresponding domain records, or adjust bootstrap to return IDs with working detail routes. Without this, live mode cannot complete judge Task A or roster Task C.
4. `GET /api/v1/matches/{id}` projects scores but does not include allowed scoring event types. The app offers an event type field when no list is supplied, without branching on sport names. Returning the active sport's `scoring_events` keys would enable rule-driven choices.
5. `GET /api/v1/clubs/{id}` returns player IDs, but no squad IDs. The app discovers each player's current squad through `/api/v1/roster/history/{player_id}` and derives destination squads from other visible clubs' players. A club with an empty roster cannot provide a destination. Expose tenant/league-scoped squad IDs and names to make transfers reliable after grader setup.
6. No authenticated player-registration route exists. The live “Add player” form explains this; transfer, loan and release use actual IDs from server responses. Demo mode can still add a local preview player.

## Mobile checks

- `npm run typecheck`, `npm run lint` and `node scripts/check-api.cjs` pass.
- The browser preview reaches Fixtures → Match detail → Product → Checkout → Receipt in demo mode.
- An earlier APK was installed and opened on a physical Pixel 8 Pro. Demo login, Fixtures, Store, product detail, and checkout loaded. The final design/API APK and live airplane-mode sync still need device verification.

## Judge UI/HCI checklist (honest status)

| Judge task or criterion | Current status | Remaining proof or dependency |
| --- | --- | --- |
| A: standings, then open a match | Demo browser route works; phone opened Fixtures | Final phone journey; live fixture IDs and working standings from `/reset` |
| B: merchandise, mock payment, receipt | Demo browser route works; phone reached checkout | Final phone receipt/PDF; live product stock, checkout and signed receipt |
| C: manager roster action | Role-gated screen and durable queue implemented | Live seeded player/squad IDs and final phone action |
| Airplane mode, force-close, reconnect | SQLite persists cache and action queue in app code | Physical-device force-close/reopen and server applied/rejected replay |
| Navigation, visual hierarchy, feedback, readability | Shared design system, visible sync bar, labelled tabs, plain-language messages; narrow browser preview checked | Final APK at 360×640 dp and rotated, all five roles |
| Tenant branding | Tenant name, logo URL and brand mark use bootstrap response | Confirm live logo URL and color contrast; full tenant-wide color theming is not yet verified |

The app offers five demo-account shortcuts and a visible sign-out/switch-account action on the Club tab. Self-service sign-up is not in the judged screen list and no registration endpoint has been provided; do not present a fake live sign-up.
