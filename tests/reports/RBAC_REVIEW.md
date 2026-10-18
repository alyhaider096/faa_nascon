# RBAC and event confirmation review

18 October 2026. Reviewed from baseline `40e23bfded60d0f82ec7d937fd47a2cac3d163d7`
plus the changes in the commit containing this report.

## Result

The existing backend passed its five-role authorization matrix and mobile
platform/tenant checks: 67 passed in 31.78s (`rbac-baseline.xml`). Additional real
event-write checks passed: 22 passed in 14.42s (`mobile-event-roles.xml`). No
backend RBAC defect was reproduced in this checkout. This does not establish
which APK/server versions were used yesterday or their runtime configuration.

| Role | Score / correction | Scope |
| --- | --- | --- |
| super_admin | Allowed | Tested own-league writes; existing matrix permits global management |
| league_organizer | Allowed | Own league; other-league direct/offline writes rejected |
| club_manager | Forbidden | No score/correction write |
| player | Forbidden | No score/correction write |
| viewer | Forbidden | No score/correction write |

For each role the new suite exercises both direct mobile writes and offline-sync
actions, then reads the persisted score/version. Allowed identical retries do
not increment the score again. Forbidden actions leave both score and version
unchanged. The existing matrix additionally covers roster/product management,
player editing, tenant reads, platform configuration and token attacks.

## Confirmed mobile defects corrected

1. The score screen always displayed a queue-success message even if the server
   rejected the event. It now displays the returned accepted/rejected/pending
   outcome, including an explicit demo-only explanation.
2. A successful event write followed by a failed score read could relabel the
   accepted event as rejected. Refresh failure now shows a separate warning and
   retains the accepted result.
3. Offline sync updated action statuses without reloading the affected scores.
   It now refreshes affected matches after applied/duplicate acknowledgements.
4. Correction confirmation used a native alert callback. An explicit in-page
   confirmation now provides the same route through the action on native and web.
   Submission controls show progress and avoid normal repeated taps while busy.

Mobile `npm run typecheck` and `npm run lint` both passed after the final change.
The phone APK has not been rebuilt or exercised. No browser click-through result
is claimed. These changes must reach a new APK or development build before they
can fix the installed phone app.

## Reproduce on an isolated workstation

Use disposable PostgreSQL 16 and Redis 7, never the shared judging database:

```powershell
$env:TEST_DATABASE_URL = 'postgresql://USER:PASSWORD@HOST:PORT/THROWAWAY_DB'
$env:TEST_REDIS_URL = 'redis://HOST:PORT/0'
python -m pytest tests/rbac/test_rbac.py tests/integration/test_platform.py tests/integration/test_domain_tenant_scope.py -q -p no:cacheprovider --junitxml=tests/reports/rbac-baseline.xml
python -m pytest tests/integration/test_mobile_event_roles.py -q -p no:cacheprovider --junitxml=tests/reports/mobile-event-roles.xml
```

Runs used Windows Python 3.12, pytest 8.3.5, the repository's pinned backend
dependencies, real local PostgreSQL/Redis, public test signing configuration and
a real in-process HTTP server. The first run had two pytest cache permission
warnings; assertions all passed. Later runs disabled that cache provider.

## Phone acceptance still required

Disable Demo data, configure the reachable backend URL and sign in again with
each test role. Super admin and the owning organizer must add a goal and correct
an existing score event with matching score readback. Manager/player/viewer must
not receive scoring controls; direct API requests must still be rejected. Repeat
an authorized offline action, reconnect, sync and confirm score refresh without
a duplicate event. Repeat with a wrong-role rejection and a lost connection so
the visible feedback matches the actual queue state. Capture APK build identity
and deployed backend SHA alongside the result.
