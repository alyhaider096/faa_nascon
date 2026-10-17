# Architecture decisions

1. **Expo and TypeScript:** use Expo SDK 55 with React Native and Expo Router for a fast Android delivery and type checked screen routes. SDK 55 targets Android compile SDK 36, already installed on the mobile laptop.
2. **One monorepo:** keep mobile, backend, tests and Compose in one GitHub repository so the grader clones one commit.
3. **PostgreSQL as durable source:** persist domain entities, inventory and the append-only match log in a transactional database.
4. **Redis for transient work:** use Redis for internal jobs, rate limiting and event delivery; do not use it as the only store of domain truth.
5. **Event-sourced scoring:** rebuild projections from immutable events; corrections are signed compensation events.
6. **Per-team HMAC salt:** read `DAY1_SALT` from backend environment only; canonicalize JSON and sign events/receipts server-side.
7. **SQLite offline queue:** persist cached read views and pending mobile actions across process termination; reconcile server results per action.
8. **Local Android release:** build the installable APK with Gradle and the Android SDK, then commit it at the required path before the deadline.
